from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from pymilvus import CollectionSchema, DataType, FieldSchema, MilvusClient
from pymilvus.exceptions import MilvusException

from app.config import get_settings
from app.services.logging.request_logger import get_request_logger

settings = get_settings()
os.makedirs(os.path.dirname(settings.MILVUS_LITE_PATH), exist_ok=True)

logger = logging.getLogger(__name__)

COLLECTION_NAME = "chunks_dense_v1"
WEB_KB_ID = "__web__"


def _ensure_dense_vector(vector: Optional[List[float]], dense_dim: int) -> List[float]:
    if dense_dim <= 0:
        raise ValueError("dense_dim 必须大于 0")
    if isinstance(vector, list) and vector:
        floats = [float(v) for v in vector[:dense_dim]]
        if len(floats) < dense_dim:
            floats.extend([0.0] * (dense_dim - len(floats)))
        return floats
    return [0.0] * dense_dim


class MilvusLiteStore:
    def __init__(self) -> None:
        logger.info("Initializing Milvus Lite client path=%s", settings.MILVUS_LITE_PATH)
        self.client = MilvusClient(uri=settings.MILVUS_LITE_PATH)
        self.collection_dim: Optional[int] = None

    def _ensure_collection(self, dense_dim: int) -> None:
        if (
            self.collection_dim
            and self.collection_dim == dense_dim
            and self.client.has_collection(COLLECTION_NAME)
        ):
            return

        if self.client.has_collection(COLLECTION_NAME):
            needs_rebuild = False
            try:
                schema = self.client.describe_collection(COLLECTION_NAME)
                field_names = {
                    field.get("name")
                    for field in schema.get("schema", {}).get("fields", [])
                    if isinstance(field, dict)
                }
                if "kb_category" not in field_names:
                    logger.info("Milvus collection missing kb_category field, recreating")
                    needs_rebuild = True
            except MilvusException as exc:  # noqa: BLE001
                logger.warning("Describe collection failed, recreating: %s", exc)
                needs_rebuild = True

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

        schema = CollectionSchema(
            fields=[
                FieldSchema(name="pk", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=512),
                FieldSchema(name="kb_id", dtype=DataType.VARCHAR, max_length=128),
                FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=512),
                FieldSchema(name="kb_category", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="dense", dtype=DataType.FLOAT_VECTOR, dim=dense_dim),
            ],
            description="Dense embeddings for knowledge chunks",
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

    def upsert_chunks(
        self,
        chunks: List[Dict[str, any]],
        dense_dim: int,
        request_id: Optional[str] = None,
    ) -> None:
        req_logger = get_request_logger(logger, request_id)
        if not chunks:
            return
        if not dense_dim:
            raise ValueError("缺少 dense_dim，无法写入向量")

        self._ensure_collection(dense_dim)
        chunk_ids = [c["chunk_id"] for c in chunks if c.get("chunk_id")]
        if chunk_ids:
            expr = ",".join(f'"{cid}"' for cid in chunk_ids)
            try:
                self.client.delete(collection_name=COLLECTION_NAME, filter=f"chunk_id in [{expr}]")
            except MilvusException as exc:  # noqa: BLE001
                logger.warning("Milvus delete before upsert failed: %s", exc)

        rows = [
            {
                "chunk_id": item["chunk_id"],
                "kb_id": item["kb_id"],
                "doc_id": item["doc_id"],
                "kb_category": item.get("kb_category") or "general_doc",
                "dense": _ensure_dense_vector(item.get("dense"), dense_dim),
            }
            for item in chunks
        ]
        try:
            req_logger.info(
                "Milvus upsert start collection=%s chunks=%s dim=%s",
                COLLECTION_NAME,
                len(chunks),
                dense_dim,
            )
            self.client.insert(COLLECTION_NAME, data=rows)
            req_logger.info(
                "Milvus upsert done collection=%s chunks=%s",
                COLLECTION_NAME,
                len(rows),
            )
        except MilvusException as exc:  # noqa: BLE001
            req_logger.error(
                "Milvus insert failed collection=%s error=%s first_chunk=%s",
                COLLECTION_NAME,
                exc,
                chunk_ids[:3],
            )
            raise RuntimeError(f"Milvus 写入失败: {exc}") from exc

    def delete_by_doc(self, kb_id: str, doc_id: str) -> int:
        if not self.client.has_collection(COLLECTION_NAME):
            return 0
        expr = f'kb_id == "{kb_id}" && doc_id == "{doc_id}"'
        try:
            result = self.client.delete(collection_name=COLLECTION_NAME, filter=expr)
            return int(getattr(result, "delete_count", 0) or 0)
        except MilvusException as exc:  # noqa: BLE001
            logger.error("Milvus delete_by_doc failed: %s", exc)
            raise RuntimeError(f"Milvus 删除失败: {exc}") from exc

    def delete_by_kb(self, kb_id: str) -> int:
        if not self.client.has_collection(COLLECTION_NAME):
            return 0
        expr = f'kb_id == "{kb_id}"'
        try:
            result = self.client.delete(collection_name=COLLECTION_NAME, filter=expr)
            return int(getattr(result, "delete_count", 0) or 0)
        except MilvusException as exc:  # noqa: BLE001
            logger.error("Milvus delete_by_kb failed: %s", exc)
            raise RuntimeError(f"Milvus 删除失败: {exc}") from exc

    def _build_filter(
        self,
        kb_ids: Optional[List[str]],
        kb_categories: Optional[List[str]],
    ) -> Optional[str]:
        clauses: List[str] = []
        if kb_ids:
            clean_ids = sorted({kb for kb in kb_ids if kb})
            if clean_ids:
                quoted = ",".join(f'"{kb}"' for kb in clean_ids)
                clauses.append(f"kb_id in [{quoted}]")
        if kb_categories:
            clean_cats = sorted({cat for cat in kb_categories if cat})
            if clean_cats:
                quoted = ",".join(f'"{cat}"' for cat in clean_cats)
                clauses.append(f"kb_category in [{quoted}]")
        if not clauses:
            return None
        return " && ".join(clauses)

    def search_dense(
        self,
        query_dense: List[float],
        limit: int,
        kb_ids: Optional[List[str]] = None,
        kb_categories: Optional[List[str]] = None,
        request_id: Optional[str] = None,
    ) -> List[Dict[str, any]]:
        req_logger = get_request_logger(logger, request_id)
        if not query_dense or not self.client.has_collection(COLLECTION_NAME):
            return []
        filter_expr = self._build_filter(kb_ids, kb_categories)
        try:
            results = self.client.search(
                collection_name=COLLECTION_NAME,
                data=[query_dense],
                anns_field="dense",
                limit=limit,
                search_params={"metric_type": "COSINE"},
                output_fields=["chunk_id", "kb_id", "doc_id"],
                filter=filter_expr,
            )[0]
            req_logger.info(
                "Milvus search done collection=%s kb_filter=%s hits=%s",
                COLLECTION_NAME,
                kb_ids,
                len(results),
            )
        except MilvusException as exc:  # noqa: BLE001
            req_logger.error("Milvus dense search failed: %s", exc)
            raise RuntimeError(f"Milvus 检索失败: {exc}") from exc

        hits: List[Dict[str, any]] = []
        for rank, hit in enumerate(results):
            entity = hit["entity"]
            cid = entity.get("chunk_id")
            if not cid:
                continue
            hits.append(
                {
                    "chunk_id": cid,
                    "kb_id": entity.get("kb_id"),
                    "doc_id": entity.get("doc_id"),
                    "score": 1.0 - hit["distance"],
                    "rank": rank,
                }
            )
        return hits


# 延迟初始化：避免在导入时就连接数据库
_milvus_store_instance: Optional[MilvusLiteStore] = None


def get_milvus_store() -> MilvusLiteStore:
    """
    获取 Milvus Store 单例（延迟初始化）
    
    使用延迟初始化避免在模块导入时就尝试连接数据库，
    这样可以防止容器启动时的文件锁冲突问题。
    
    Returns:
        MilvusLiteStore 实例
    """
    global _milvus_store_instance
    if _milvus_store_instance is None:
        _milvus_store_instance = MilvusLiteStore()
    return _milvus_store_instance


# 保留向后兼容性：但使用时会触发延迟初始化
@property
def milvus_store() -> MilvusLiteStore:
    """向后兼容的属性访问器"""
    return get_milvus_store()


# 为了完全向后兼容，也提供模块级变量（但实际是函数调用）
def __getattr__(name):
    if name == "milvus_store":
        return get_milvus_store()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

