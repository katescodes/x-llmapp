from __future__ import annotations

import hashlib
import logging
from typing import List, Optional

from .dao import kb_dao
from ..platform.ingest.parser import parse_document
from .embedding.http_embedding_client import embed_texts
from .embedding_provider_store import get_embedding_store
from .segmenter.chunker import chunk_document
from .vectorstore.milvus_lite_store import get_milvus_store
from .asr_service import transcribe_audio
from app.schemas.types import KbCategory

logger = logging.getLogger(__name__)


def _resolve_dense_dim(vectors: List[dict], fallback: Optional[int]) -> int:
    for vec in vectors:
        dense = vec.get("dense")
        if isinstance(dense, list) and dense:
            return len(dense)
    if fallback:
        return fallback
    raise ValueError("Embedding dense_dim 未配置，且服务未返回 dense 向量")


def list_kbs():
    return kb_dao.list_kbs()


def get_kb_or_raise(kb_id: str):
    kb = kb_dao.get_kb(kb_id)
    if not kb:
        raise ValueError("知识库不存在")
    return kb


def create_kb(name: str, description: str = "", category_id: Optional[str] = None):
    return kb_dao.create_kb(name, description or "", category_id)


def update_kb(kb_id: str, name: Optional[str], description: Optional[str], category_id: Optional[str] = None):
    kb = get_kb_or_raise(kb_id)
    kb_dao.update_kb(
        kb_id,
        name or kb["name"],
        description if description is not None else kb.get("description", ""),
        category_id if category_id is not None else kb.get("category_id")
    )


def delete_kb(kb_id: str):
    get_kb_or_raise(kb_id)
    try:
        get_milvus_store().delete_by_kb(kb_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("删除知识库向量失败 kb=%s: %s", kb_id, exc)
        raise
    kb_dao.delete_kb(kb_id)


def list_documents(kb_id: str):
    get_kb_or_raise(kb_id)
    return kb_dao.list_documents(kb_id)


def delete_document(kb_id: str, doc_id: str, skip_asset_cleanup: bool = False):
    """
    删除知识库文档
    - 删除向量数据
    - 删除chunks
    - 删除文档记录
    - 删除关联的项目资产（除非 skip_asset_cleanup=True）
    
    Args:
        kb_id: 知识库ID
        doc_id: 文档ID
        skip_asset_cleanup: 是否跳过清理关联的项目资产（当从项目资产删除时设为True）
    """
    doc = kb_dao.get_document(doc_id)
    if not doc or doc["kb_id"] != kb_id:
        raise ValueError("文档不存在")
    previous_status = doc["status"]
    kb_dao.update_document_status(doc_id, "deleting", doc.get("meta"))
    try:
        get_milvus_store().delete_by_doc(kb_id, doc_id)
    except Exception as exc:  # noqa: BLE001
        kb_dao.update_document_status(doc_id, previous_status, doc.get("meta"))
        logger.exception("删除文档向量失败 kb=%s doc=%s: %s", kb_id, doc_id, exc)
        raise
    kb_dao.delete_chunks_by_doc(doc_id)
    
    # 删除关联的项目资产（除非调用者已经处理了）
    if not skip_asset_cleanup:
        try:
            from app.services.dao.tender_dao import TenderDAO
            from app.services.db.postgres import _get_pool
            
            tender_dao = TenderDAO(_get_pool())
            assets = tender_dao.get_assets_by_kb_doc_id(doc_id)
            
            for asset in assets:
                try:
                    # 删除磁盘文件（如果是模板文件）
                    if asset.get("storage_path"):
                        import os
                        storage_path = asset["storage_path"]
                        if os.path.exists(storage_path):
                            os.remove(storage_path)
                            logger.info(f"Deleted file {storage_path} for asset {asset['id']}")
                    
                    # 删除项目文档绑定记录（兼容旧API）
                    tender_dao._execute(
                        "DELETE FROM tender_project_documents WHERE kb_doc_id=%s",
                        (doc_id,)
                    )
                    
                    # 删除asset记录（直接删除数据库记录，不调用 service 层避免循环）
                    tender_dao.delete_asset(asset["id"])
                    logger.info(f"Deleted tender asset {asset['id']} associated with kb document {doc_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete tender asset {asset.get('id')}: {e}")
        except Exception as exc:
            # 记录错误但不影响文档删除
            logger.warning(f"Failed to delete associated tender assets for doc {doc_id}: {exc}")
    
    kb_dao.delete_document(doc_id)


async def import_document(kb_id: str, filename: str, data: bytes, kb_category: KbCategory = "general_doc"):
    kb = kb_dao.get_kb(kb_id)
    if not kb:
        raise ValueError("知识库不存在")
    file_hash = hashlib.sha1(data).hexdigest()
    if kb_dao.document_exists(kb_id, file_hash):
        return {
            "filename": filename,
            "status": "skipped",
            "error": "文档已存在",
        }
    doc_id = kb_dao.create_document(
        kb_id=kb_id,
        filename=filename,
        source="upload",
        status="processing",
        meta={"size": len(data)},
        content_hash=file_hash,
        kb_category=kb_category,
    )

    try:
        parsed = await parse_document(filename, data, transcribe_audio_func=transcribe_audio)
        if not parsed.text.strip():
            raise ValueError("文档内容为空或无法解析")
        chunks = chunk_document(
            url=f"kb://{kb_id}/{doc_id}",
            title=parsed.title or filename,
            text=parsed.text,
        )
        if not chunks:
            raise ValueError("文档未生成有效分片")
        store = get_embedding_store()
        provider = store.get_default()
        if not provider:
            raise ValueError("未配置默认 Embedding 服务，请先在设置中添加")
        vectors = await embed_texts([chunk.text for chunk in chunks], provider=provider)
        if not vectors or len(vectors) != len(chunks):
            raise ValueError("未获取到有效的嵌入向量")
        for chunk in chunks:
            kb_dao.upsert_chunk(
                chunk_id=chunk.chunk_id,
                kb_id=kb_id,
                doc_id=doc_id,
                title=chunk.title,
                url=chunk.url,
                position=chunk.position,
                content=chunk.text,
                kb_category=kb_category,
            )
        dense_dim = _resolve_dense_dim(vectors, provider.dense_dim)
        try:
            get_milvus_store().upsert_chunks(
                [
                    {
                        "chunk_id": chunk.chunk_id,
                        "kb_id": kb_id,
                        "doc_id": doc_id,
                        "kb_category": kb_category,
                        "dense": vec.get("dense"),
                    }
                    for chunk, vec in zip(chunks, vectors)
                ],
                dense_dim=dense_dim,
            )
        except RuntimeError as exc:
            raise ValueError(str(exc)) from exc
        kb_dao.update_document_status(
            doc_id,
            "ready",
            {
                **parsed.metadata,
                "chunks": len(chunks),
            },
        )
        return {
            "filename": filename,
            "status": "ready",
            "doc_id": doc_id,
            "chunks": len(chunks),
        }
    except Exception as exc:  # noqa: BLE001
        kb_dao.update_document_status(doc_id, "failed", {"error": str(exc)})
        kb_dao.delete_chunks_by_doc(doc_id)
        get_milvus_store().delete_by_doc(kb_id, doc_id)
        return {
            "filename": filename,
            "status": "failed",
            "doc_id": doc_id,
            "error": str(exc),
        }

