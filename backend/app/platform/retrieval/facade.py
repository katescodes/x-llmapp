"""
Retrieval Facade - 统一检索入口，支持 cutover 控制
"""
import logging
from typing import List, Optional

from psycopg_pool import ConnectionPool

from app.core.cutover import get_cutover_config, CutoverMode
from app.platform.retrieval.new_retriever import NewRetriever, RetrievedChunk
from app.services.embedding_provider_store import EmbeddingProviderStored

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
        - OLD: 使用 legacy retriever (未实现，返回空)
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
                # TODO: 实现 legacy retriever 回退
                logger.warning("Legacy retriever not implemented, returning empty")
                return []
        
        # SHADOW 模式：运行新旧，对比，返回旧
        elif mode == CutoverMode.SHADOW:
            # 先运行 legacy (未实现，返回空)
            legacy_results = []
            logger.warning("SHADOW mode: legacy retriever not implemented")
            
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
        
        # OLD 模式：仅使用 legacy
        else:  # mode == CutoverMode.OLD
            logger.warning("OLD mode: legacy retriever not implemented, returning empty")
            # TODO: 实现 legacy retriever
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

