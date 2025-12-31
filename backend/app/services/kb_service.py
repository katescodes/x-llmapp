from __future__ import annotations

import hashlib
import logging
from typing import List, Optional

from .dao import kb_dao
from ..platform.ingest.parser import parse_document
from .asr_service import transcribe_audio
from app.schemas.types import KbCategory

logger = logging.getLogger(__name__)


def list_kbs():
    return kb_dao.list_kbs()


def list_kbs_by_owner(owner_id: str):
    """获取指定用户创建的知识库列表"""
    from app.services.db.postgres import _get_pool
    
    pool = _get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, description, category_id, created_at, updated_at, owner_id
                FROM knowledge_bases
                WHERE owner_id = %s
                ORDER BY created_at DESC
            """, (owner_id,))
            
            rows = cur.fetchall()
            return [
                {
                    "id": row['id'],
                    "name": row['name'],
                    "description": row['description'],
                    "category_id": row['category_id'],
                    "created_at": row['created_at'],
                    "updated_at": row['updated_at'],
                    "owner_id": row['owner_id'],
                }
                for row in rows
            ]


def get_kb_or_raise(kb_id: str):
    kb = kb_dao.get_kb(kb_id)
    if not kb:
        raise ValueError("知识库不存在")
    return kb


def create_kb(name: str, description: str = "", category_id: Optional[str] = None, owner_id: Optional[str] = None):
    """创建知识库，设置owner_id"""
    return kb_dao.create_kb(name, description or "", category_id, owner_id)


def update_kb(kb_id: str, name: Optional[str], description: Optional[str], category_id: Optional[str] = None):
    kb = get_kb_or_raise(kb_id)
    kb_dao.update_kb(
        kb_id,
        name or kb["name"],
        description if description is not None else kb.get("description", ""),
        category_id if category_id is not None else kb.get("category_id")
    )


def delete_kb(kb_id: str):
    """删除知识库（新逻辑）"""
    get_kb_or_raise(kb_id)
    
    from app.services.db.postgres import _get_pool
    from app.platform.vectorstore.milvus_docseg_store import milvus_docseg_store
    
    pool = _get_pool()
    
    # 删除所有文档的 Milvus 向量（通过 project_id）
    try:
        # 注意：使用 project_ids 参数过滤并删除
        # 由于没有直接的 delete_by_kb 方法，我们需要先查找文档再删除
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # 查找所有使用此知识库的文档版本
                cur.execute(
                    """
                    SELECT DISTINCT dv.id FROM document_versions dv
                    JOIN documents d ON d.id = dv.document_id
                    WHERE d.namespace IN (
                        SELECT 'tender' FROM tender_projects WHERE kb_id=%s
                        UNION
                        SELECT 'declare' FROM declare_projects WHERE kb_id=%s
                    )
                    """,
                    (kb_id, kb_id)
                )
                doc_version_ids = [row[list(row.keys())[0]] for row in cur.fetchall()]
        
        # 删除每个文档版本的向量
        for doc_version_id in doc_version_ids:
            try:
                milvus_docseg_store.delete_by_version(doc_version_id)
            except Exception as exc:
                logger.warning(f"Failed to delete Milvus vectors for doc_version {doc_version_id}: {exc}")
    except Exception as exc:
        logger.warning(f"Failed to delete Milvus vectors for kb {kb_id}: {exc}")
    
    kb_dao.delete_kb(kb_id)


def list_documents(kb_id: str):
    """
    列出知识库的文档（新系统：从 documents 表读取）
    
    支持：
    - 项目关联的文档（tender/declare）
    - 独立上传的文档
    """
    get_kb_or_raise(kb_id)
    
    from app.services.db.postgres import _get_pool
    
    # 从 documents 表读取（新系统）
    pool = _get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    d.id,
                    dv.filename,
                    'upload' as source,
                    'ready' as status,
                    d.created_at,
                    d.created_at as updated_at,
                    d.meta_json,
                    d.meta_json->>'kb_category' as kb_category
                FROM documents d
                JOIN document_versions dv ON d.id = dv.document_id
                WHERE d.meta_json->>'kb_id' = %s
                ORDER BY d.created_at DESC
            """, (kb_id,))
            
            rows = cur.fetchall()
            
            documents = []
            for row in rows:
                doc_id, filename, source, status, created_at, updated_at, meta_json, kb_category = row
                documents.append({
                    'id': doc_id,
                    'filename': filename,
                    'source': source,
                    'status': status,
                    'created_at': created_at.isoformat() if created_at else None,
                    'updated_at': updated_at.isoformat() if updated_at else None,
                    'meta': meta_json or {},
                    'kb_category': kb_category or 'general_doc',
                })
            
            return documents




def delete_document(kb_id: str, doc_id: str, skip_asset_cleanup: bool = False):
    """
    删除知识库文档（新逻辑：从 DocStore 删除）
    
    Args:
        kb_id: 知识库ID
        doc_id: 文档版本ID (doc_version_id)
        skip_asset_cleanup: 是否跳过清理关联的项目资产（当从项目资产删除时设为True）
    """
    get_kb_or_raise(kb_id)
    
    from app.services.db.postgres import _get_pool
    from app.platform.docstore.service import DocStoreService
    from app.platform.vectorstore.milvus_docseg_store import milvus_docseg_store
    
    pool = _get_pool()
    docstore = DocStoreService(pool)
    
    # 验证文档版本是否存在
    version_info = docstore.get_document_version(doc_id)
    if not version_info:
        raise ValueError("文档不存在")
    
    try:
        # 1. 删除 Milvus 向量
        milvus_docseg_store.delete_by_version(doc_id)
        logger.info(f"Deleted Milvus vectors for doc_version_id={doc_id}")
    except Exception as exc:
        logger.warning(f"Failed to delete Milvus vectors for doc {doc_id}: {exc}")
    
    # 2. 删除 doc_segments
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM doc_segments WHERE doc_version_id=%s", (doc_id,))
            cur.execute("DELETE FROM document_versions WHERE id=%s", (doc_id,))
    
    logger.info(f"Deleted doc_segments and document_version for doc_version_id={doc_id}")
    
    # 3. 删除关联的项目资产（除非调用者已经处理了）
    if not skip_asset_cleanup:
        try:
            # 查找使用此文档版本的资产
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    # 招投标资产
                    cur.execute(
                        "SELECT id, storage_path FROM tender_project_assets "
                        "WHERE meta_json->>'doc_version_id'=%s",
                        (doc_id,)
                    )
                    tender_assets = cur.fetchall()
                    
                    # 申报资产
                    cur.execute(
                        "SELECT asset_id, storage_path FROM declare_assets "
                        "WHERE meta_json->>'doc_version_id'=%s",
                        (doc_id,)
                    )
                    declare_assets = cur.fetchall()
            
            # 删除招投标资产
            for asset_id, storage_path in tender_assets:
                try:
                    # 删除磁盘文件
                    if storage_path:
                        import os
                        if os.path.exists(storage_path):
                            os.remove(storage_path)
                            logger.info(f"Deleted file {storage_path} for tender asset {asset_id}")
                    
                    # 删除asset记录
                    with pool.connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("DELETE FROM tender_project_assets WHERE id=%s", (asset_id,))
                    
                    logger.info(f"Deleted tender asset {asset_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete tender asset {asset_id}: {e}")
            
            # 删除申报资产
            for asset_id, storage_path in declare_assets:
                try:
                    # 删除磁盘文件
                    if storage_path:
                        import os
                        if os.path.exists(storage_path):
                            os.remove(storage_path)
                            logger.info(f"Deleted file {storage_path} for declare asset {asset_id}")
                    
                    # 删除asset记录
                    with pool.connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("DELETE FROM declare_assets WHERE asset_id=%s", (asset_id,))
                    
                    logger.info(f"Deleted declare asset {asset_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete declare asset {asset_id}: {e}")
        except Exception as exc:
            # 记录错误但不影响文档删除
            logger.warning(f"Failed to delete associated assets for doc {doc_id}: {exc}")


async def import_document(kb_id: str, filename: str, data: bytes, kb_category: KbCategory = "general_doc"):
    """
    导入文档到知识库（新逻辑：使用 IngestV2Service）
    
    注意：直接上传的文档不创建项目，仅作为通用知识库文档存储
    """
    kb = kb_dao.get_kb(kb_id)
    if not kb:
        raise ValueError("知识库不存在")
    
    # 检查文档是否已存在
    file_hash = hashlib.sha1(data).hexdigest()
    
    from app.services.db.postgres import _get_pool
    from app.platform.ingest.v2_service import IngestV2Service
    import uuid
    
    pool = _get_pool()
    
    # 检查是否已存在相同哈希的文档
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT dv.id FROM document_versions dv "
                "WHERE dv.sha256=%s LIMIT 1",
                (hashlib.sha256(data).hexdigest(),)
            )
            existing = cur.fetchone()
            if existing:
                return {
                    "filename": filename,
                    "status": "skipped",
                    "error": "文档已存在",
                }
    
    try:
        # 使用 IngestV2Service 处理文档
        ingest_v2 = IngestV2Service(pool)
        
        # 生成临时资产ID
        temp_asset_id = f"kb_{uuid.uuid4().hex}"
        
        # 调用入库服务
        result = await ingest_v2.ingest_asset_v2(
            project_id=kb_id,  # 使用 kb_id 作为 project_id
            asset_id=temp_asset_id,
            file_bytes=data,
            filename=filename,
            doc_type="general_doc",
            owner_id=kb.get("owner_id"),
            storage_path=None,
        )
        
        logger.info(f"Imported document {filename} to kb {kb_id}: doc_version_id={result.doc_version_id}, segments={result.segment_count}")
        
        return {
            "filename": filename,
            "status": "ready",
            "doc_id": result.doc_version_id,
            "chunks": result.segment_count,
            "milvus_count": result.milvus_count,
        }
    except Exception as e:
        logger.error(f"Failed to import document {filename}: {e}", exc_info=True)
        return {
            "filename": filename,
            "status": "failed",
            "error": str(e),
        }

