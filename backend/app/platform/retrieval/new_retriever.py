"""
新检索服务 - Step 4
使用 doc_segments (PG FTS + Milvus) 进行混合检索
"""
import logging
from typing import Dict, List, Optional

from psycopg_pool import ConnectionPool

from app.services.embedding.http_embedding_client import embed_texts
from app.services.embedding_provider_store import EmbeddingProviderStored
from app.services.vectorstore.milvus_docseg_store import milvus_docseg_store
from app.services.retrieval.rrf import rrf_fuse

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
        
        # 1. 获取项目下的 doc_version_ids
        doc_version_ids = self._get_project_doc_versions(project_id, doc_types)
        if not doc_version_ids:
            logger.warning(f"[NewRetriever] NO_DOC_VERSIONS project_id={project_id} doc_types={doc_types}")
            return []
        
        logger.info(f"[NewRetriever] found {len(doc_version_ids)} doc_versions")
        
        # 2. 向量检索 (Milvus)
        dense_start = time.time()
        dense_hits = []
        if embedding_provider:
            dense_hits = await self._search_dense(
                query, doc_version_ids, embedding_provider, dense_limit, project_id, doc_types
            )
        dense_ms = int((time.time() - dense_start) * 1000)
        logger.info(f"[NewRetriever] DENSE_DONE count={len(dense_hits)} ms={dense_ms}")
        
        # 3. 全文检索 (PG tsvector)
        lexical_start = time.time()
        lexical_hits = self._search_lexical(query, doc_version_ids, lexical_limit)
        lexical_ms = int((time.time() - lexical_start) * 1000)
        logger.info(f"[NewRetriever] LEXICAL_DONE count={len(lexical_hits)} ms={lexical_ms}")
        
        # 4. RRF 融合
        fused = rrf_fuse(dense_hits, lexical_hits, k=60, topn=top_k)
        
        # 5. 加载完整文本
        chunk_ids = [hit["chunk_id"] for hit in fused]
        results = self._load_chunks(chunk_ids)
        
        overall_ms = int((time.time() - overall_start) * 1000)
        logger.info(
            f"[NewRetriever] DONE project_id={project_id} dense={len(dense_hits)} lexical={len(lexical_hits)} fused={len(results)} total_ms={overall_ms}"
        )
        
        return results
    
    def _get_project_doc_versions(
        self, project_id: str, doc_types: Optional[List[str]]
    ) -> List[str]:
        """从 tender_project_assets 获取 doc_version_ids"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                # 构建 SQL 查询
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
                return [row[0] for row in rows if row[0]]
    
    async def _search_dense(
        self,
        query: str,
        doc_version_ids: List[str],
        embedding_provider: EmbeddingProviderStored,
        limit: int,
        project_id: str,
        doc_types: Optional[List[str]],
    ) -> List[Dict]:
        """Milvus 向量检索"""
        try:
            # 获取查询向量
            vectors = await embed_texts([query], provider=embedding_provider)
            if not vectors or not vectors[0].get("dense"):
                logger.warning("NewRetriever no query vector")
                return []
            
            query_dense = vectors[0]["dense"]
            
            # Milvus 检索
            hits = milvus_docseg_store.search_dense(
                query_dense=query_dense,
                limit=limit,
                doc_version_ids=doc_version_ids,
                project_ids=[project_id],
                doc_types=doc_types,
            )
            
            # 转换为统一格式
            return [
                {
                    "chunk_id": hit["segment_id"],
                    "score": hit["score"],
                    "rank": hit["rank"],
                }
                for hit in hits
            ]
        except Exception as e:
            logger.error(f"NewRetriever dense search failed: {e}", exc_info=True)
            return []
    
    def _search_lexical(
        self, query: str, doc_version_ids: List[str], limit: int
    ) -> List[Dict]:
        """PG tsvector 全文检索"""
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    # 使用 tsvector 检索
                    sql = """
                        SELECT id, ts_rank(tsv, query) as rank
                        FROM doc_segments, to_tsquery('english', %s) query
                        WHERE doc_version_id = ANY(%s)
                          AND tsv @@ query
                        ORDER BY rank DESC
                        LIMIT %s
                    """
                    # 简单处理查询词：用 OR 连接
                    query_terms = " | ".join(query.split())
                    
                    cur.execute(sql, [query_terms, doc_version_ids, limit])
                    rows = cur.fetchall()
                    
                    return [
                        {
                            "chunk_id": row[0],
                            "score": float(row[1]),
                            "rank": idx,
                        }
                        for idx, row in enumerate(rows)
                    ]
        except Exception as e:
            logger.error(f"NewRetriever lexical search failed: {e}", exc_info=True)
            return []
    
    def _load_chunks(self, chunk_ids: List[str]) -> List[RetrievedChunk]:
        """批量加载分片内容"""
        if not chunk_ids:
            return []
        
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
                    
                    # 按原始顺序返回
                    chunk_map = {
                        row[0]: RetrievedChunk(
                            chunk_id=row[0],
                            text=row[1],
                            score=0.0,  # 这里 score 会被后续 RRF 覆盖
                            meta={
                                "doc_version_id": row[3],
                                **row[2],
                            },
                        )
                        for row in rows
                    }
                    
                    return [chunk_map[cid] for cid in chunk_ids if cid in chunk_map]
        except Exception as e:
            logger.error(f"NewRetriever load chunks failed: {e}", exc_info=True)
            return []

