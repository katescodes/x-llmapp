"""
新检索服务 - Step 4
使用 doc_segments (PG FTS + Milvus) 进行混合检索
"""
import logging
from typing import Dict, List, Optional

from psycopg_pool import ConnectionPool

from app.services.embedding.http_embedding_client import embed_texts
from app.services.embedding_provider_store import EmbeddingProviderStored
from app.platform.vectorstore.milvus_docseg_store import milvus_docseg_store
from app.platform.retrieval.providers.legacy.rrf import rrf_fuse

logger = logging.getLogger(__name__)


class RetrievedChunk:
    """检索结果块"""
    def __init__(
        self,
        chunk_id: str,
        text: str,
        score: float,
        meta: Optional[Dict] = None,
    ):
        self.chunk_id = chunk_id
        self.text = text
        self.score = score
        self.meta = meta or {}
    
    def to_dict(self) -> Dict:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "score": self.score,
            "meta": self.meta,
        }


class NewRetriever:
    """新检索器 - 使用 DocStore + 新索引"""
    
    def __init__(self, pool: ConnectionPool):
        self.pool = pool
    
    async def retrieve(
        self,
        query: str,
        project_id: str,
        doc_types: Optional[List[str]] = None,
        embedding_provider: Optional[EmbeddingProviderStored] = None,
        top_k: int = 12,
        dense_limit: int = 40,
        lexical_limit: int = 40,
        **kwargs  # 接受额外参数（如 run_id, bidder_name 等）但忽略它们
    ) -> List[RetrievedChunk]:
        """
        混合检索
        
        Args:
            query: 查询文本
            project_id: 项目 ID
            doc_types: 文档类型过滤 (tender/bid/etc)
            embedding_provider: Embedding 提供者
            top_k: 最终返回数量
            dense_limit: 向量检索数量
            lexical_limit: 全文检索数量
            
        Returns:
            检索结果列表
        """
        import time
        logger.info(f"[NewRetriever] START query={query[:100]} project_id={project_id} doc_types={doc_types} top_k={top_k}")
        overall_start = time.time()
        
        # 1. 获取项目下的 doc_version_ids - 在线程池中执行
        import asyncio
        doc_version_ids = await asyncio.to_thread(
            self._get_project_doc_versions, project_id, doc_types
        )
        if not doc_version_ids:
            logger.warning(f"[NewRetriever] NO_DOC_VERSIONS project_id={project_id} doc_types={doc_types}")
            return []
        
        logger.info(f"[NewRetriever] found {len(doc_version_ids)} doc_versions")
        
        # 2. 向量检索 (Milvus) - with fallback
        dense_start = time.time()
        dense_hits = []
        dense_error = None
        if embedding_provider:
            dense_hits, dense_error = await self._search_dense(
                query, doc_version_ids, embedding_provider, dense_limit, project_id, doc_types
            )
        dense_ms = int((time.time() - dense_start) * 1000)
        if dense_error:
            logger.warning(f"[NewRetriever] DENSE_FAILED error={dense_error} fallback_to_lexical_only ms={dense_ms}")
        else:
            logger.info(f"[NewRetriever] DENSE_DONE count={len(dense_hits)} ms={dense_ms}")
        
        # 3. 全文检索 (PG tsvector) - 在线程池中执行，避免阻塞事件循环
        import asyncio
        lexical_start = time.time()
        lexical_hits = await asyncio.to_thread(
            self._search_lexical, query, doc_version_ids, lexical_limit
        )
        lexical_ms = int((time.time() - lexical_start) * 1000)
        logger.info(f"[NewRetriever] LEXICAL_DONE count={len(lexical_hits)} ms={lexical_ms}")
        
        # 4. RRF 融合 (如果 dense 失败，只用 lexical)
        if dense_error and lexical_hits:
            # Dense 失败降级：直接返回 top_k 个 lexical 结果
            fused = lexical_hits[:top_k]
            logger.info(f"[NewRetriever] FALLBACK_MODE using_lexical_only top_k={len(fused)}")
        else:
            # 正常融合
            fused = rrf_fuse(dense_hits, lexical_hits, k=60, topn=top_k)
        
        # 5. 加载完整文本 - 在线程池中执行，避免阻塞事件循环
        results = await asyncio.to_thread(self._load_chunks, fused)  # ✅ 传递完整的 fused 列表
        
        overall_ms = int((time.time() - overall_start) * 1000)
        logger.info(
            f"[NewRetriever] DONE project_id={project_id} dense={len(dense_hits)} lexical={len(lexical_hits)} fused={len(results)} total_ms={overall_ms} dense_error={dense_error is not None}"
        )
        
        return results
    
    def _get_project_doc_versions(
        self, project_id: str, doc_types: Optional[List[str]]
    ) -> List[str]:
        """从项目资产表获取 doc_version_ids，支持 tender 和 declare 项目"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                # 根据 project_id 前缀判断使用哪个表
                if project_id.startswith("declare_proj_"):
                    # 申报书项目：使用 declare_assets 表
                    # 注意：declare_assets 的 kind 字段存储的是 'notice', 'company', 'tech'
                    # 而 extraction specs 传入的是 'declare_notice', 'declare_company' 等
                    # 需要去除 'declare_' 前缀
                    mapped_kinds = None
                    if doc_types:
                        mapped_kinds = [
                            dt.replace("declare_", "") if dt.startswith("declare_") else dt
                            for dt in doc_types
                        ]
                    
                    sql = """
                        SELECT DISTINCT doc_version_id
                        FROM declare_assets
                        WHERE project_id = %s
                          AND doc_version_id IS NOT NULL
                    """
                    params = [project_id]
                    
                    if mapped_kinds:
                        sql += " AND kind = ANY(%s)"
                        params.append(mapped_kinds)
                    
                    cur.execute(sql, params)
                    rows = cur.fetchall()
                    return [list(row.values())[0] for row in rows if list(row.values())[0]]
                else:
                    # 招投标项目：使用 tender_project_assets 表
                    sql = """
                        SELECT DISTINCT meta_json->>'doc_version_id' as doc_version_id
                        FROM tender_project_assets
                        WHERE project_id = %s
                          AND meta_json->>'doc_version_id' IS NOT NULL
                    """
                    params = [project_id]
                    
                    if doc_types:
                        sql += " AND kind = ANY(%s)"
                        params.append(doc_types)
                    
                    cur.execute(sql, params)
                    rows = cur.fetchall()
                    return [list(row.values())[0] for row in rows if list(row.values())[0]]
    
    async def _search_dense(
        self,
        query: str,
        doc_version_ids: List[str],
        embedding_provider: EmbeddingProviderStored,
        limit: int,
        project_id: str,
        doc_types: Optional[List[str]],
    ) -> tuple[List[Dict], Optional[str]]:
        """
        Milvus 向量检索
        
        Returns:
            (hits, error_msg) - error_msg is None on success
        """
        try:
            # 快速检查：如果 Milvus 客户端未初始化，直接跳过
            from app.platform.vectorstore.milvus_docseg_store import get_milvus_docseg_store
            milvus_store = get_milvus_docseg_store()
            if not milvus_store.client:
                return [], f"Milvus client not available: {milvus_store.connection_error}"
            
            # 获取查询向量
            vectors = await embed_texts([query], provider=embedding_provider)
            if not vectors or not vectors[0].get("dense"):
                logger.warning("NewRetriever no query vector")
                return [], "No query vector generated"
            
            query_dense = vectors[0]["dense"]
            
            # Milvus 检索（在线程池中执行，避免阻塞事件循环）
            import asyncio
            hits = await asyncio.to_thread(
                milvus_docseg_store.search_dense,
                query_dense=query_dense,
                limit=limit,
                doc_version_ids=doc_version_ids,
                project_ids=[project_id],
                doc_types=doc_types,
            )
            
            # 转换为统一格式
            result = [
                {
                    "chunk_id": hit["segment_id"],
                    "score": hit["score"],
                    "rank": hit["rank"],
                }
                for hit in hits
            ]
            return result, None
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.exception(
                "NewRetriever dense search failed; fallback to lexical only",
                extra={
                    "project_id": project_id,
                    "doc_types": doc_types,
                    "error": error_msg,
                }
            )
            return [], error_msg
    
    def _search_lexical(
        self, query: str, doc_version_ids: List[str], limit: int
    ) -> List[Dict]:
        """PG 全文检索：优先使用LIKE（中文友好），TSV作为备用"""
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    # 方案1: LIKE 模糊匹配（中文友好，直接使用）
                    import re
                    # 简单分词：提取2-4字的中文词组 + 英文单词
                    # 先按空格和标点分割
                    segments = re.split(r'[，。？！、\s]+', query)
                    search_words = []
                    
                    for seg in segments:
                        if not seg:
                            continue
                        # 中文：提取2-4字的词组
                        chinese_chars = re.findall(r'[\u4e00-\u9fff]', seg)
                        if chinese_chars:
                            # 生成2字词组
                            for i in range(len(chinese_chars) - 1):
                                word = ''.join(chinese_chars[i:i+2])
                                if word and word not in search_words:
                                    search_words.append(word)
                            # 也加入3字词组（如果有）
                            for i in range(len(chinese_chars) - 2):
                                word = ''.join(chinese_chars[i:i+3])
                                if word and word not in search_words:
                                    search_words.append(word)
                        
                        # 英文：直接加入
                        english_words = re.findall(r'[a-zA-Z]{2,}', seg)
                        for word in english_words:
                            if word not in search_words:
                                search_words.append(word)
                    
                    if not search_words:
                        logger.warning(f"No valid words extracted from query: {query}")
                        return []
                    
                    # 使用最多前5个词
                    search_words = search_words[:5]
                    print(f"[LEXICAL DEBUG] Extracted words: {search_words}", flush=True)
                    
                    # 构建 LIKE 条件（OR逻辑，而非AND）
                    like_conditions = " OR ".join([f"content_text LIKE %s" for _ in search_words])
                    like_params = [f"%{word}%" for word in search_words]
                    
                    # 计算匹配得分：匹配的词越多，得分越高
                    score_expr = " + ".join([
                        f"(CASE WHEN content_text LIKE %s THEN 1 ELSE 0 END)"
                        for _ in search_words
                    ])
                    score_params = [f"%{word}%" for word in search_words]
                    
                    sql_like = f"""
                        SELECT id, 
                               ({score_expr})::float as rank
                        FROM doc_segments
                        WHERE doc_version_id = ANY(%s)
                          AND ({like_conditions})
                        ORDER BY rank DESC, LENGTH(content_text) ASC
                        LIMIT %s
                    """
                    
                    params = score_params + [doc_version_ids] + like_params + [limit]
                    cur.execute(sql_like, params)
                    rows = cur.fetchall()
                    
                    logger.info(f"Lexical search (LIKE fallback) found {len(rows)} results")
                    
                    return [
                        {
                            "chunk_id": row['id'],
                            "score": float(row['rank']) if row['rank'] else 0.1,
                            "rank": idx,
                        }
                        for idx, row in enumerate(rows)
                    ]
        except Exception as e:
            logger.error(f"NewRetriever lexical search failed: {e}", exc_info=True)
            return []
    
    def _load_chunks(self, fused_hits: List[Dict]) -> List[RetrievedChunk]:
        """
        批量加载分片内容并赋值分数
        
        Args:
            fused_hits: RRF 融合后的结果列表，每项包含 chunk_id 和 score
            
        Returns:
            RetrievedChunk 列表，按原始顺序返回
        """
        if not fused_hits:
            return []
        
        # 提取 chunk_ids 和分数映射
        chunk_ids = [hit["chunk_id"] for hit in fused_hits]
        score_map = {hit["chunk_id"]: hit["score"] for hit in fused_hits}
        
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    sql = """
                        SELECT id, content_text, meta_json, doc_version_id
                        FROM doc_segments
                        WHERE id = ANY(%s)
                    """
                    cur.execute(sql, [chunk_ids])
                    rows = cur.fetchall()
                    
                    # 按原始顺序返回，并赋值正确的分数
                    chunk_map = {
                        row['id']: RetrievedChunk(
                            chunk_id=row['id'],
                            text=row['content_text'],
                            score=score_map.get(row['id'], 0.0),  # ✅ 使用 RRF 融合后的分数
                            meta={
                                "doc_version_id": row['doc_version_id'],
                                **row['meta_json'],
                            },
                        )
                        for row in rows
                    }
                    
                    return [chunk_map[cid] for cid in chunk_ids if cid in chunk_map]
        except Exception as e:
            logger.error(f"NewRetriever load chunks failed: {e}", exc_info=True)
            return []

