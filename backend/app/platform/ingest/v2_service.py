"""
新入库服务 (v2) - Step 4
解析文件 -> 分片 -> 写入 DocStore + PG FTS + Milvus
"""
import hashlib
import logging
import uuid
from typing import Dict, List, Optional

from psycopg_pool import ConnectionPool

from app.platform.ingest.parser import parse_document
from app.services.segmenter.chunker import chunk_document
from app.services.embedding.http_embedding_client import embed_texts
from app.services.embedding_provider_store import EmbeddingProviderStored, get_embedding_store
from app.platform.docstore.service import DocStoreService
from app.platform.vectorstore.milvus_docseg_store import milvus_docseg_store

logger = logging.getLogger(__name__)


class IngestV2Result:
    """入库结果"""
    def __init__(self, doc_version_id: str, segment_count: int, milvus_count: int = 0):
        self.doc_version_id = doc_version_id
        self.segment_count = segment_count
        self.milvus_count = milvus_count

    def to_dict(self) -> Dict:
        return {
            "doc_version_id": self.doc_version_id,
            "segment_count": self.segment_count,
            "milvus_count": self.milvus_count,
        }


class IngestV2Service:
    """新入库服务"""
    
    def __init__(self, pool: ConnectionPool):
        self.pool = pool
        self.docstore = DocStoreService(pool)
    
    async def ingest_asset_v2(
        self,
        project_id: str,
        asset_id: str,
        file_bytes: bytes,
        filename: str,
        doc_type: str,
        owner_id: Optional[str] = None,
        storage_path: Optional[str] = None,
    ) -> IngestV2Result:
        """
        新入库流程
        
        Args:
            project_id: 项目 ID
            asset_id: 资产 ID
            file_bytes: 文件内容
            filename: 文件名
            doc_type: 文档类型 (tender/bid/etc)
            owner_id: 所有者 ID
            storage_path: 存储路径
            
        Returns:
            IngestV2Result
        """
        logger.info(f"IngestV2 start asset_id={asset_id} filename={filename} doc_type={doc_type}")
        
        # 1. 确保 DocStore document/version 存在
        doc_version_id = await self._ensure_doc_version(
            asset_id, file_bytes, filename, doc_type, owner_id, storage_path
        )
        
        # 2. 解析文件
        parsed_doc = await parse_document(filename, file_bytes)
        logger.info(f"IngestV2 parsed asset_id={asset_id} chars={len(parsed_doc.text)}")
        
        # 检查解析是否出错
        if parsed_doc.metadata.get("error"):
            error_msg = parsed_doc.metadata["error"]
            logger.error(f"IngestV2 parse failed asset_id={asset_id} error={error_msg}")
            raise ValueError(f"文件解析失败: {error_msg}")
        
        # 记录警告信息（如果有）
        if parsed_doc.metadata.get("warning"):
            warning_msg = parsed_doc.metadata["warning"]
            logger.warning(f"IngestV2 parse warning asset_id={asset_id} warning={warning_msg}")
        
        # 检查是否解析出文本
        if not parsed_doc.text or len(parsed_doc.text.strip()) == 0:
            logger.warning(f"IngestV2 empty text asset_id={asset_id}")
            raise ValueError(f"文件解析成功但未提取到文本内容，文件可能为空或格式不支持")
        
        # 3. 分片
        chunks = chunk_document(
            url=asset_id,
            title=parsed_doc.title,
            text=parsed_doc.text,
            target_chars=1200,
            overlap_chars=150,
        )
        logger.info(f"IngestV2 chunked asset_id={asset_id} chunks={len(chunks)}")
        
        if not chunks:
            logger.warning(f"IngestV2 no chunks asset_id={asset_id}")
            return IngestV2Result(doc_version_id=doc_version_id, segment_count=0)
        
        # 4. 写 doc_segments（传递 pages 信息用于计算页码）
        segment_ids = await self._write_segments(
            doc_version_id, chunks, parsed_doc.metadata, parsed_doc.pages
        )
        logger.info(f"IngestV2 segments written asset_id={asset_id} count={len(segment_ids)}")
        
        # 5. 获取 embedding provider
        embedding_provider = self._get_embedding_provider()
        if not embedding_provider:
            logger.warning("IngestV2 no embedding provider, skip milvus")
            return IngestV2Result(doc_version_id=doc_version_id, segment_count=len(segment_ids))
        
        # 6. embedding 并写入 Milvus
        milvus_count = await self._write_milvus(
            segment_ids, chunks, doc_version_id, project_id, doc_type, embedding_provider
        )
        logger.info(f"IngestV2 milvus written asset_id={asset_id} count={milvus_count}")
        
        return IngestV2Result(
            doc_version_id=doc_version_id,
            segment_count=len(segment_ids),
            milvus_count=milvus_count,
        )
    
    async def _ensure_doc_version(
        self,
        asset_id: str,
        file_bytes: bytes,
        filename: str,
        doc_type: str,
        owner_id: Optional[str],
        storage_path: Optional[str],
    ) -> str:
        """确保 document 和 version 存在，返回 doc_version_id"""
        # 幂等创建 document
        document_id = self.docstore.create_document(
            namespace="tender",
            doc_type=doc_type,
            owner_id=owner_id,
        )
        
        # 幂等创建 version
        doc_version_id = self.docstore.create_document_version(
            document_id=document_id,
            filename=filename,
            file_content=file_bytes,
            storage_path=storage_path,
        )
        
        return doc_version_id
    
    async def _write_segments(
        self,
        doc_version_id: str,
        chunks: List,
        metadata: Dict,
        pages: Optional[List] = None,
    ) -> List[str]:
        """
        写入 doc_segments（带 PG FTS + 位置信息）
        
        Args:
            doc_version_id: 文档版本 ID
            chunks: 分片列表
            metadata: 文档元数据
            pages: 页面/段落信息（用于计算页码）
        """
        segments = []
        
        for idx, chunk in enumerate(chunks):
            meta_json = {
                "chunk_position": chunk.position,
                "chunk_hash": chunk.chunk_id,
                **metadata,
            }
            
            # 尝试推断页码和段落类型
            page_start, page_end, segment_type = self._infer_location(chunk, pages, metadata)
            
            segments.append({
                "segment_no": idx,
                "content_text": chunk.text,
                "meta_json": meta_json,
                "page_start": page_start,
                "page_end": page_end,
                "segment_type": segment_type,
                # heading_path 暂时留空，后续可通过 LLM 或规则推断
                "heading_path": None,
            })
        
        # 批量插入（幂等：先删除再插入）
        segment_ids = self.docstore.create_segments(doc_version_id, segments)
        return segment_ids
    
    def _infer_location(self, chunk, pages: Optional[List], metadata: Dict) -> tuple:
        """
        推断 chunk 的位置信息
        
        Returns:
            (page_start, page_end, segment_type) 元组
        """
        # 默认值
        page_start = None
        page_end = None
        segment_type = "paragraph"  # 默认为段落
        
        # 如果没有 pages 信息，返回默认值
        if not pages:
            return page_start, page_end, segment_type
        
        # 对于 PDF：pages 是页面列表，每个包含 page_no 和 text
        if "pages" in metadata and isinstance(pages, list) and len(pages) > 0:
            # 简单策略：根据 chunk.position 估算页码
            # 假设 chunks 按顺序分布在各页中
            total_pages = len(pages)
            total_chunks_estimate = metadata.get("chars", 0) / 1200  # 估算总 chunk 数
            
            if total_chunks_estimate > 0:
                # 估算此 chunk 所在的页码
                estimated_page_ratio = chunk.position / max(total_chunks_estimate, 1)
                estimated_page = int(estimated_page_ratio * total_pages) + 1
                page_start = max(1, min(estimated_page, total_pages))
                page_end = page_start  # 简化：假设不跨页
        
        # 检测是否为表格（简单启发式）
        if "|" in chunk.text and chunk.text.count("|") >= 3:
            segment_type = "table"
        elif chunk.text.strip().startswith(("1.", "2.", "一、", "二、", "·", "-", "*")):
            segment_type = "list"
        
        return page_start, page_end, segment_type
    
    def _get_embedding_provider(self) -> Optional[EmbeddingProviderStored]:
        """获取 embedding provider"""
        try:
            store = get_embedding_store()
            return store.get_default()
        except Exception as e:
            logger.warning(f"Failed to get embedding provider: {e}")
            return None
    
    async def _write_milvus(
        self,
        segment_ids: List[str],
        chunks: List,
        doc_version_id: str,
        project_id: str,
        doc_type: str,
        embedding_provider: EmbeddingProviderStored,
    ) -> int:
        """写入 Milvus 向量索引"""
        try:
            # 获取所有 chunk 文本
            texts = [chunk.text for chunk in chunks]
            
            # 批量 embedding
            vectors = await embed_texts(texts, provider=embedding_provider)
            if not vectors or len(vectors) != len(texts):
                logger.error(f"Embedding mismatch: expected {len(texts)}, got {len(vectors)}")
                return 0
            
            # 准备 Milvus 数据
            milvus_data = []
            for segment_id, chunk, vec in zip(segment_ids, chunks, vectors):
                dense = vec.get("dense")
                if not dense:
                    logger.warning(f"No dense vector for segment {segment_id}")
                    continue
                milvus_data.append({
                    "segment_id": segment_id,
                    "doc_version_id": doc_version_id,
                    "project_id": project_id,
                    "doc_type": doc_type,
                    "dense": dense,
                })
            
            if not milvus_data:
                logger.warning("No valid vectors to write to Milvus")
                return 0
            
            # 获取维度
            dense_dim = len(milvus_data[0]["dense"])
            
            # 写入 Milvus
            count = milvus_docseg_store.upsert_segments(milvus_data, dense_dim)
            return count
        except Exception as e:
            logger.error(f"Failed to write Milvus: {e}", exc_info=True)
            return 0

