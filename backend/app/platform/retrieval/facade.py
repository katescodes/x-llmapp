"""
Retrieval Facade - 统一检索入口，支持 cutover 控制
"""
import logging
from typing import List, Optional

from psycopg_pool import ConnectionPool

from app.core.cutover import get_cutover_config, CutoverMode
from app.platform.retrieval.new_retriever import NewRetriever, RetrievedChunk
from app.platform.retrieval.providers.legacy import retrieve as legacy_retrieve
from app.services.embedding_provider_store import EmbeddingProviderStored
from app.schemas.intent import Anchor

logger = logging.getLogger(__name__)


class RetrievalResult:
    """检索结果封装，包含 provider 信息"""
    def __init__(self, chunks: List[RetrievedChunk], provider: str, mode: str):
        self.chunks = chunks
        self.provider = provider  # "new" or "legacy"
        self.mode = mode  # 实际使用的模式


class RetrievalFacade:
    """检索门面，根据 cutover 模式选择检索器"""
    
    def __init__(self, pool: ConnectionPool):
        self.pool = pool
        self.new_retriever = NewRetriever(pool)
    
    async def _call_legacy_retriever(
        self,
        query: str,
        embedding_provider: EmbeddingProviderStored,
        top_k: int = 12,
    ) -> List[RetrievedChunk]:
        """
        调用 legacy retriever (来自 platform/retrieval/providers/legacy)
        
        注意：legacy retriever 使用 kb-based retrieval，与 new retriever 的 project-based 不同
        这里暂时返回空结果，因为需要适配参数
        """
        # Legacy retriever 使用的参数格式不同（kb_ids, kb_categories, anchors）
        # 而 new retriever 使用 project_id + doc_types
        # 这里需要做参数转换或保持向后兼容
        logger.warning(
            "Legacy retriever called but parameter adaptation not implemented. "
            "Returning empty results."
        )
        return []
    
    async def retrieve(
        self,
        query: str,
        project_id: str,
        doc_types: Optional[List[str]] = None,
        embedding_provider: Optional[EmbeddingProviderStored] = None,
        top_k: int = 12,
        **kwargs
    ) -> List[RetrievedChunk]:
        """
        统一检索接口
        
        根据 RETRIEVAL_MODE 决定使用哪个检索器：
        - OLD: 使用 legacy retriever (platform/retrieval/providers/legacy)
        - SHADOW: 运行 new + legacy，对比，返回 legacy
        - PREFER_NEW: 尝试 new，失败回退 legacy
        - NEW_ONLY: 仅使用 new，失败抛错
        """
        cutover = get_cutover_config()
        mode = cutover.get_mode("retrieval", project_id)
        
        logger.info(
            f"RetrievalFacade: mode={mode.value} project_id={project_id} "
            f"query={query[:50]} doc_types={doc_types}"
        )
        
        # NEW_ONLY 模式：仅使用新检索器，失败抛错
        if mode == CutoverMode.NEW_ONLY:
            try:
                results = await self.new_retriever.retrieve(
                    query=query,
                    project_id=project_id,
                    doc_types=doc_types,
                    embedding_provider=embedding_provider,
                    top_k=top_k,
                    **kwargs
                )
                logger.info(
                    f"NEW_ONLY retrieval succeeded: {len(results)} results, "
                    f"provider=new, project_id={project_id}"
                )
                return results
            except Exception as e:
                error_msg = (
                    f"RETRIEVAL_MODE=NEW_ONLY failed: {str(e)} "
                    f"(mode=NEW_ONLY, provider=new, query={query[:50]}, "
                    f"doc_types={doc_types}, project_id={project_id})"
                )
                logger.error(error_msg, exc_info=True)
                raise ValueError(error_msg) from e
        
        # PREFER_NEW 模式：尝试新检索器，失败回退
        elif mode == CutoverMode.PREFER_NEW:
            try:
                results = await self.new_retriever.retrieve(
                    query=query,
                    project_id=project_id,
                    doc_types=doc_types,
                    embedding_provider=embedding_provider,
                    top_k=top_k,
                    **kwargs
                )
                logger.info(
                    f"PREFER_NEW retrieval succeeded with new: {len(results)} results"
                )
                return results
            except Exception as e:
                logger.warning(
                    f"PREFER_NEW retrieval failed with new, falling back to legacy: {e}"
                )
                # 回退到 legacy retriever
                return await self._call_legacy_retriever(
                    query=query,
                    embedding_provider=embedding_provider,
                    top_k=top_k
                )
        
        # SHADOW 模式：运行新旧，对比，返回旧
        elif mode == CutoverMode.SHADOW:
            # 先运行 legacy
            legacy_results = await self._call_legacy_retriever(
                query=query,
                embedding_provider=embedding_provider,
                top_k=top_k
            )
            
            # 运行 new 并对比
            try:
                new_results = await self.new_retriever.retrieve(
                    query=query,
                    project_id=project_id,
                    doc_types=doc_types,
                    embedding_provider=embedding_provider,
                    top_k=top_k,
                    **kwargs
                )
                logger.info(
                    f"SHADOW retrieval: legacy={len(legacy_results)}, "
                    f"new={len(new_results)}"
                )
                # TODO: 记录差异到 shadow_diff
            except Exception as e:
                logger.error(f"SHADOW mode: new retriever failed: {e}")
            
            return legacy_results
        
        # OLD 模式：仅使用 legacy (来自 platform/retrieval/providers/legacy)
        else:  # mode == CutoverMode.OLD
            logger.info("OLD mode: using legacy retriever from platform/retrieval/providers/legacy")
            return await self._call_legacy_retriever(
                query=query,
                embedding_provider=embedding_provider,
                top_k=top_k
            )
    
    async def retrieve_from_kb(
        self,
        query: str,
        kb_ids: List[str],
        kb_categories: Optional[List[str]] = None,
        embedding_provider: Optional[EmbeddingProviderStored] = None,
        top_k: int = 12,
        dense_limit: int = 40,
        lexical_limit: int = 40,
        request_id: Optional[str] = None,
        **kwargs
    ) -> List[RetrievedChunk]:
        """
        从知识库检索（完全基于知识库，不依赖项目）
        
        对话框专用接口，逻辑：
        1. 从 kb_documents 获取 doc_version_ids → doc_segments 检索（新系统）
        2. 从 kb_chunks 检索（旧系统，兼容独立导入的文档）
        3. 合并结果
        
        Args:
            query: 查询文本
            kb_ids: 知识库ID列表
            kb_categories: 知识库分类过滤（可选）
            embedding_provider: Embedding提供者
            top_k: 最终返回数量
            dense_limit: 向量检索数量
            lexical_limit: 全文检索数量
            request_id: 请求ID（用于日志）
            
        Returns:
            检索结果列表
        """
        logger.info(
            f"retrieve_from_kb: kb_ids={kb_ids}, kb_categories={kb_categories}, "
            f"query={query[:50]}..."
        )
        
        all_results = []
        
        # 策略1: 从 kb_documents 获取 doc_version_ids，直接检索 doc_segments
        doc_version_ids = self._get_doc_version_ids_from_kb(kb_ids, kb_categories)
        print(f"[FACADE DEBUG] _get_doc_version_ids_from_kb returned: {doc_version_ids}", flush=True)
        logger.info(f"[DEBUG] _get_doc_version_ids_from_kb returned: {doc_version_ids}")
        
        if doc_version_ids:
            logger.info(f"Found {len(doc_version_ids)} doc_versions for kb_ids={kb_ids}")
            
            try:
                # 直接用 doc_version_ids 检索（不需要 project_id）
                chunks = await self._retrieve_by_doc_versions(
                    query=query,
                    doc_version_ids=doc_version_ids,
                    embedding_provider=embedding_provider,
                    top_k=top_k,
                    dense_limit=dense_limit,
                    lexical_limit=lexical_limit,
                )
                all_results.extend(chunks)
                logger.info(
                    f"Retrieved {len(chunks)} chunks from doc_segments (by doc_version_ids)"
                )
            except Exception as e:
                logger.warning(f"doc_segments retrieval failed: {e}", exc_info=True)
        else:
            logger.info(f"No doc_versions found for kb_ids={kb_ids}")
        
        # 策略2: 从 kb_chunks 检索（兼容旧系统/独立导入的文档）
        try:
            legacy_chunks = await self._retrieve_from_kb_chunks(
                query=query,
                kb_ids=kb_ids,
                kb_categories=kb_categories,
                embedding_provider=embedding_provider,
                dense_limit=dense_limit,
                lexical_limit=lexical_limit,
                final_topk=top_k,
            )
            
            if legacy_chunks:
                all_results.extend(legacy_chunks)
                logger.info(
                    f"Retrieved {len(legacy_chunks)} chunks from kb_chunks (legacy)"
                )
        except Exception as e:
            logger.warning(f"kb_chunks retrieval failed: {e}", exc_info=True)
        
        # 策略3: 合并、去重、排序
        if not all_results:
            logger.warning(f"No results found for kb_ids={kb_ids}")
            return []
        
        # 去重（按 chunk_id）
        seen = set()
        unique_results = []
        for chunk in all_results:
            if chunk.chunk_id not in seen:
                seen.add(chunk.chunk_id)
                unique_results.append(chunk)
        
        # 按分数排序并截取
        unique_results.sort(key=lambda x: x.score, reverse=True)
        final_results = unique_results[:top_k]
        
        logger.info(
            f"retrieve_from_kb done: total={len(all_results)}, "
            f"unique={len(unique_results)}, final={len(final_results)}"
        )
        
        return final_results
    
    def _get_doc_version_ids_from_kb(
        self, 
        kb_ids: List[str], 
        kb_categories: Optional[List[str]] = None
    ) -> List[str]:
        """
        从 kb_documents 表直接获取 doc_version_ids
        
        Args:
            kb_ids: 知识库ID列表
            kb_categories: 分类过滤（可选）
            
        Returns:
            doc_version_id 列表
        """
        if not kb_ids:
            return []
        
        doc_version_ids = []
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                placeholders = ",".join(["%s"] * len(kb_ids))
                
                # 从 kb_documents 的 meta_json 中提取 doc_version_id
                sql = f"""
                    SELECT DISTINCT meta_json->>'doc_version_id' as doc_version_id
                    FROM kb_documents
                    WHERE kb_id IN ({placeholders})
                      AND meta_json->>'doc_version_id' IS NOT NULL
                """
                params = list(kb_ids)
                
                # 可选：按分类过滤
                if kb_categories:
                    cat_placeholders = ",".join(["%s"] * len(kb_categories))
                    sql += f" AND kb_category IN ({cat_placeholders})"
                    params.extend(kb_categories)
                
                cur.execute(sql, params)
                rows = cur.fetchall()
                
                for row in rows:
                    doc_version_id = row['doc_version_id']
                    if doc_version_id:
                        doc_version_ids.append(doc_version_id)
        
        return doc_version_ids
    
    async def _retrieve_by_doc_versions(
        self,
        query: str,
        doc_version_ids: List[str],
        embedding_provider: Optional[EmbeddingProviderStored],
        top_k: int,
        dense_limit: int,
        lexical_limit: int,
    ) -> List[RetrievedChunk]:
        """
        用 doc_version_ids 直接检索（复用 NewRetriever 的核心逻辑）
        
        Args:
            query: 查询文本
            doc_version_ids: 文档版本ID列表
            embedding_provider: Embedding提供者
            top_k: 最终返回数量
            dense_limit: 向量检索数量
            lexical_limit: 全文检索数量
            
        Returns:
            检索结果列表
        """
        import asyncio
        from app.platform.retrieval.providers.legacy.rrf import rrf_fuse
        
        # 1. 向量检索 (Milvus) - KB检索模式，不传project_id过滤
        dense_hits = []
        if embedding_provider:
            try:
                # 直接调用Milvus，不通过_search_dense（避免project_id过滤）
                from app.platform.vectorstore.milvus_docseg_store import get_milvus_docseg_store
                from app.services.embedding.http_embedding_client import embed_texts
                import asyncio
                
                # 获取查询向量
                vectors = await embed_texts([query], provider=embedding_provider)
                if vectors and vectors[0].get("dense"):
                    query_dense = vectors[0]["dense"]
                    
                    # Milvus检索（只用doc_version_ids过滤，不用project_ids）
                    milvus_store = get_milvus_docseg_store()
                    hits = await asyncio.to_thread(
                        milvus_store.search_dense,
                        query_dense=query_dense,
                        limit=dense_limit,
                        doc_version_ids=doc_version_ids,
                        project_ids=None,  # ✅ 不传project_ids，避免过滤失败
                        doc_types=None,
                    )
                    
                    # 转换为统一格式
                    dense_hits = [
                        {
                            "chunk_id": hit["segment_id"],
                            "score": hit["score"],
                            "rank": hit["rank"],
                        }
                        for hit in hits
                    ]
                    print(f"[MILVUS DEBUG] Dense search found {len(dense_hits)} results", flush=True)
                else:
                    print(f"[MILVUS DEBUG] No query vector generated", flush=True)
            except Exception as e:
                print(f"[MILVUS DEBUG] Dense search failed: {e}", flush=True)
                logger.warning(f"Dense search failed: {e}")
        
        # 2. 全文检索 (PG tsvector)
        print(f"[FACADE DEBUG] Calling _search_lexical with doc_version_ids={doc_version_ids[:3]}... (total: {len(doc_version_ids)})", flush=True)
        logger.info(f"[DEBUG] Calling _search_lexical with doc_version_ids={doc_version_ids[:3]}... (total: {len(doc_version_ids)})")
        lexical_hits = await asyncio.to_thread(
            self.new_retriever._search_lexical,
            query,
            doc_version_ids,
            lexical_limit
        )
        print(f"[FACADE DEBUG] _search_lexical returned {len(lexical_hits)} hits", flush=True)
        logger.info(f"[DEBUG] _search_lexical returned {len(lexical_hits)} hits")
        
        # 3. RRF 融合
        fused = rrf_fuse(dense_hits, lexical_hits, k=60, topn=top_k)
        
        # 4. 加载完整文本
        chunk_ids = [hit["chunk_id"] for hit in fused]
        results = await asyncio.to_thread(
            self.new_retriever._load_chunks,
            chunk_ids
        )
        
        logger.info(
            f"_retrieve_by_doc_versions: dense={len(dense_hits)}, "
            f"lexical={len(lexical_hits)}, fused={len(results)}"
        )
        
        return results
    
    def _find_projects_by_kb_ids(self, kb_ids: List[str]) -> List[str]:
        """
        根据 kb_ids 查找对应的项目 ID（支持多种项目类型）
        
        Args:
            kb_ids: 知识库 ID 列表
            
        Returns:
            项目 ID 列表
        """
        if not kb_ids:
            return []
        
        project_ids = []
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                placeholders = ",".join(["%s"] * len(kb_ids))
                
                # 查询招投标项目
                cur.execute(
                    f"""
                    SELECT id FROM tender_projects 
                    WHERE kb_id IN ({placeholders})
                    """,
                    kb_ids
                )
                rows = cur.fetchall()
                project_ids.extend([row[list(row.keys())[0]] for row in rows])
                
                # 未来可以扩展：查询其他类型项目
                # cur.execute(f"SELECT id FROM declare_projects WHERE kb_id IN ({placeholders})", kb_ids)
                # ...
        
        return project_ids
    
    async def _retrieve_from_kb_chunks(
        self,
        query: str,
        kb_ids: List[str],
        kb_categories: Optional[List[str]],
        embedding_provider: EmbeddingProviderStored,
        dense_limit: int,
        lexical_limit: int,
        final_topk: int,
    ) -> List[RetrievedChunk]:
        """
        从 kb_chunks 表检索（独立知识库）
        
        使用 legacy retriever
        """
        if not embedding_provider:
            logger.warning("No embedding provider, skipping kb_chunks retrieval")
            return []
        
        try:
            # 调用 legacy retriever
            hits, stats = await legacy_retrieve(
                query=query,
                kb_ids=kb_ids,
                kb_categories=kb_categories,
                anchors=[],  # 对话框不需要 anchors
                embedding_provider=embedding_provider,
                dense_topk=dense_limit,
                lexical_topk=lexical_limit,
                final_topk=final_topk,
            )
            
            # 转换为 RetrievedChunk 格式
            chunks = []
            for hit in hits:
                chunk = RetrievedChunk(
                    chunk_id=hit.get("chunk_id", ""),
                    text=hit.get("text", ""),
                    score=hit.get("score", 0.0),
                    meta={
                        "kb_id": hit.get("kb_id"),
                        "doc_id": hit.get("doc_id"),
                        "title": hit.get("title"),
                        "url": hit.get("url"),
                        "position": hit.get("position"),
                        "kb_category": hit.get("kb_category"),
                    }
                )
                chunks.append(chunk)
            
            return chunks
            
        except Exception as e:
            logger.error(f"kb_chunks retrieval failed: {e}", exc_info=True)
            return []


async def retrieve(
    query: str,
    project_id: str,
    doc_types: Optional[List[str]] = None,
    embedding_provider: Optional[EmbeddingProviderStored] = None,
    top_k: int = 12,
    pool: Optional[ConnectionPool] = None,
    **kwargs
) -> List[RetrievedChunk]:
    """
    便捷函数：统一检索入口
    """
    if pool is None:
        from app.services.db.postgres import _get_pool
        pool = _get_pool()
    
    facade = RetrievalFacade(pool)
    return await facade.retrieve(
        query=query,
        project_id=project_id,
        doc_types=doc_types,
        embedding_provider=embedding_provider,
        top_k=top_k,
        **kwargs
    )

