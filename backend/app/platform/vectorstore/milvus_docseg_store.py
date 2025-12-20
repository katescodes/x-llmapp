"""
Milvus DocSegments Store - 新文档索引存储
用于 Step 4: 新的 ingest pipeline
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from pymilvus import CollectionSchema, DataType, FieldSchema, MilvusClient
from pymilvus.exceptions import MilvusException

from app.config import get_settings

settings = get_settings()
os.makedirs(os.path.dirname(settings.MILVUS_LITE_PATH), exist_ok=True)

logger = logging.getLogger(__name__)


def _get_request_logger(base_logger, request_id: Optional[str] = None):
    """简化的请求日志记录器"""
    if request_id:
        return logging.LoggerAdapter(base_logger, {"request_id": request_id})
    return base_logger

# 新集合名称
COLLECTION_NAME = "doc_segments_v1"


def _ensure_dense_vector(vector: Optional[List[float]], dense_dim: int) -> List[float]:
    """确保向量维度正确"""
    if dense_dim <= 0:
        raise ValueError("dense_dim 必须大于 0")
    if isinstance(vector, list) and vector:
        floats = [float(v) for v in vector[:dense_dim]]
        if len(floats) < dense_dim:
            floats.extend([0.0] * (dense_dim - len(floats)))
        return floats
    return [0.0] * dense_dim


class MilvusDocSegStore:
    """新文档分片向量存储"""
    
    def __init__(self) -> None:
        logger.info("Initializing Milvus DocSeg client path=%s", settings.MILVUS_LITE_PATH)
        self.client = MilvusClient(uri=settings.MILVUS_LITE_PATH)
        self.collection_dim: Optional[int] = None

    def _ensure_collection(self, dense_dim: int) -> None:
        """确保集合存在且维度正确"""
        if (
            self.collection_dim
            and self.collection_dim == dense_dim
            and self.client.has_collection(COLLECTION_NAME)
        ):
            return

        if self.client.has_collection(COLLECTION_NAME):
            needs_rebuild = False
            
            if self.collection_dim and self.collection_dim != dense_dim:
                logger.warning(
                    "Milvus collection dimension changed (%s -> %s), rebuilding",
                    self.collection_dim,
                    dense_dim,
                )
                needs_rebuild = True

            if needs_rebuild:
                self.client.drop_collection(COLLECTION_NAME)
            else:
                self.collection_dim = dense_dim
                return

        # 创建新集合
        schema = CollectionSchema(
            fields=[
                FieldSchema(name="pk", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="segment_id", dtype=DataType.VARCHAR, max_length=512),  # doc_segments.id
                FieldSchema(name="doc_version_id", dtype=DataType.VARCHAR, max_length=512),
                FieldSchema(name="project_id", dtype=DataType.VARCHAR, max_length=128),
                FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=64),  # tender/bid/etc
                FieldSchema(name="dense", dtype=DataType.FLOAT_VECTOR, dim=dense_dim),
            ],
            description="Dense embeddings for doc_segments",
        )
        
        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="dense",
            index_type="HNSW",
            metric_type="COSINE",
            params={"M": 8, "efConstruction": 64},
        )
        
        self.client.create_collection(
            collection_name=COLLECTION_NAME,
            schema=schema,
            index_params=index_params,
        )
        self.collection_dim = dense_dim
        logger.info("Created Milvus collection=%s dim=%s", COLLECTION_NAME, dense_dim)

    def upsert_segments(
        self,
        segments: List[Dict[str, any]],
        dense_dim: int,
        request_id: Optional[str] = None,
    ) -> int:
        """
        插入/更新文档分片向量
        
        Args:
            segments: 包含 segment_id, doc_version_id, project_id, doc_type, dense
            dense_dim: 向量维度
            request_id: 请求ID
            
        Returns:
            写入的数量
        """
        req_logger = _get_request_logger(logger, request_id)
        if not segments:
            return 0
        if not dense_dim:
            raise ValueError("缺少 dense_dim，无法写入向量")

        self._ensure_collection(dense_dim)
        
        # 先删除已存在的 segment_id
        segment_ids = [s["segment_id"] for s in segments if s.get("segment_id")]
        if segment_ids:
            expr = ",".join(f'"{sid}"' for sid in segment_ids)
            try:
                self.client.delete(collection_name=COLLECTION_NAME, filter=f"segment_id in [{expr}]")
            except MilvusException as exc:  # noqa: BLE001
                logger.warning("Milvus delete before upsert failed: %s", exc)

        # 准备数据
        rows = [
            {
                "segment_id": item["segment_id"],
                "doc_version_id": item["doc_version_id"],
                "project_id": item.get("project_id", ""),
                "doc_type": item.get("doc_type", ""),
                "dense": _ensure_dense_vector(item.get("dense"), dense_dim),
            }
            for item in segments
        ]
        
        try:
            req_logger.info(
                "Milvus upsert segments collection=%s count=%s dim=%s",
                COLLECTION_NAME,
                len(segments),
                dense_dim,
            )
            self.client.insert(COLLECTION_NAME, data=rows)
            req_logger.info("Milvus upsert segments done count=%s", len(rows))
            return len(rows)
        except MilvusException as exc:  # noqa: BLE001
            req_logger.error(
                "Milvus insert segments failed error=%s first_ids=%s",
                exc,
                segment_ids[:3],
            )
            raise RuntimeError(f"Milvus 写入失败: {exc}") from exc

    def delete_by_version(self, doc_version_id: str) -> int:
        """删除指定版本的所有分片"""
        if not self.client.has_collection(COLLECTION_NAME):
            return 0
        expr = f'doc_version_id == "{doc_version_id}"'
        try:
            result = self.client.delete(collection_name=COLLECTION_NAME, filter=expr)
            return int(getattr(result, "delete_count", 0) or 0)
        except MilvusException as exc:  # noqa: BLE001
            logger.error("Milvus delete_by_version failed: %s", exc)
            raise RuntimeError(f"Milvus 删除失败: {exc}") from exc

    def search_dense(
        self,
        query_dense: List[float],
        limit: int,
        doc_version_ids: Optional[List[str]] = None,
        project_ids: Optional[List[str]] = None,
        doc_types: Optional[List[str]] = None,
        request_id: Optional[str] = None,
    ) -> List[Dict[str, any]]:
        """
        向量检索
        
        Args:
            query_dense: 查询向量
            limit: 返回数量
            doc_version_ids: 限制文档版本
            project_ids: 限制项目
            doc_types: 限制文档类型 (tender/bid/etc)
            request_id: 请求ID
            
        Returns:
            匹配的分片列表
        """
        req_logger = _get_request_logger(logger, request_id)
        if not query_dense or not self.client.has_collection(COLLECTION_NAME):
            return []
        
        # 构建过滤条件
        clauses: List[str] = []
        if doc_version_ids:
            clean_ids = sorted({vid for vid in doc_version_ids if vid})
            if clean_ids:
                quoted = ",".join(f'"{vid}"' for vid in clean_ids)
                clauses.append(f"doc_version_id in [{quoted}]")
        if project_ids:
            clean_ids = sorted({pid for pid in project_ids if pid})
            if clean_ids:
                quoted = ",".join(f'"{pid}"' for pid in clean_ids)
                clauses.append(f"project_id in [{quoted}]")
        if doc_types:
            clean_types = sorted({dt for dt in doc_types if dt})
            if clean_types:
                quoted = ",".join(f'"{dt}"' for dt in clean_types)
                clauses.append(f"doc_type in [{quoted}]")
        
        filter_expr = " && ".join(clauses) if clauses else None
        
        try:
            results = self.client.search(
                collection_name=COLLECTION_NAME,
                data=[query_dense],
                anns_field="dense",
                limit=limit,
                search_params={"metric_type": "COSINE"},
                output_fields=["segment_id", "doc_version_id", "project_id", "doc_type"],
                filter=filter_expr,
            )[0]
            req_logger.info(
                "Milvus search done collection=%s filter=%s hits=%s",
                COLLECTION_NAME,
                filter_expr,
                len(results),
            )
        except MilvusException as exc:  # noqa: BLE001
            req_logger.error("Milvus dense search failed: %s", exc)
            raise RuntimeError(f"Milvus 检索失败: {exc}") from exc

        hits: List[Dict[str, any]] = []
        for rank, hit in enumerate(results):
            entity = hit["entity"]
            sid = entity.get("segment_id")
            if not sid:
                continue
            hits.append(
                {
                    "segment_id": sid,
                    "doc_version_id": entity.get("doc_version_id"),
                    "project_id": entity.get("project_id"),
                    "doc_type": entity.get("doc_type"),
                    "score": 1.0 - hit["distance"],
                    "rank": rank,
                }
            )
        return hits


# 全局实例
milvus_docseg_store = MilvusDocSegStore()

