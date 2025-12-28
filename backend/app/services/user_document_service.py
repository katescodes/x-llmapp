"""
用户文档服务
负责用户文档的上传、管理、分析和检索
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import UploadFile

from app.services.llm_client import llm_json
from app.platform.ingest.v2_service import IngestV2Service

logger = logging.getLogger(__name__)


class UserDocumentService:
    """用户文档服务"""
    
    def __init__(self, pool):
        self.pool = pool
        self.storage_dir = os.getenv("TENDER_USER_DOCS_DIR", "./data/tender/user_documents")
        os.makedirs(self.storage_dir, exist_ok=True)
    
    # ==================== 分类管理 ====================
    
    def create_category(
        self,
        project_id: str,
        category_name: str,
        category_desc: Optional[str] = None,
        display_order: int = 0,
    ) -> Dict[str, Any]:
        """创建文档分类"""
        logger.info(f"创建文档分类: {category_name} (project_id={project_id})")
        
        category_id = str(uuid.uuid4())
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tender_user_doc_categories (
                        id, project_id, category_name, category_desc, display_order
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, project_id, category_name, category_desc, display_order, created_at, updated_at
                    """,
                    (category_id, project_id, category_name, category_desc, display_order),
                )
                row = cur.fetchone()
        
        return self._row_to_category(row)
    
    def list_categories(
        self,
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        列出文档分类
        
        Args:
            project_id: 项目ID（可选，为空则列出所有分类）
        """
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                # 查询分类及其文档数量
                if project_id:
                    cur.execute(
                        """
                        SELECT 
                            c.id,
                            c.project_id,
                            c.category_name,
                            c.category_desc,
                            c.display_order,
                            c.created_at,
                            c.updated_at,
                            COUNT(d.id) as doc_count
                        FROM tender_user_doc_categories c
                        LEFT JOIN tender_user_documents d ON c.id = d.category_id
                        WHERE c.project_id = %s
                        GROUP BY c.id, c.project_id, c.category_name, c.category_desc, 
                                 c.display_order, c.created_at, c.updated_at
                        ORDER BY c.display_order, c.created_at
                        """,
                        (project_id,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT 
                            c.id,
                            c.project_id,
                            c.category_name,
                            c.category_desc,
                            c.display_order,
                            c.created_at,
                            c.updated_at,
                            COUNT(d.id) as doc_count
                        FROM tender_user_doc_categories c
                        LEFT JOIN tender_user_documents d ON c.id = d.category_id
                        GROUP BY c.id, c.project_id, c.category_name, c.category_desc, 
                                 c.display_order, c.created_at, c.updated_at
                        ORDER BY c.display_order, c.created_at
                        """
                    )
                rows = cur.fetchall()
        
        return [self._row_to_category(row) for row in rows]
    
    def update_category(
        self,
        category_id: str,
        category_name: Optional[str] = None,
        category_desc: Optional[str] = None,
        display_order: Optional[int] = None,
    ) -> Dict[str, Any]:
        """更新文档分类"""
        updates = []
        params = []
        
        if category_name is not None:
            updates.append("category_name = %s")
            params.append(category_name)
        
        if category_desc is not None:
            updates.append("category_desc = %s")
            params.append(category_desc)
        
        if display_order is not None:
            updates.append("display_order = %s")
            params.append(display_order)
        
        if not updates:
            # 没有更新，返回当前数据
            return self.get_category(category_id)
        
        updates.append("updated_at = NOW()")
        params.append(category_id)
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE tender_user_doc_categories
                    SET {', '.join(updates)}
                    WHERE id = %s
                    RETURNING id, project_id, category_name, category_desc, display_order, created_at, updated_at
                    """,
                    params,
                )
                row = cur.fetchone()
        
        return self._row_to_category(row)
    
    def delete_category(self, category_id: str):
        """删除文档分类（文档的 category_id 会被设置为 NULL）"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM tender_user_doc_categories WHERE id = %s",
                    (category_id,),
                )
        
        logger.info(f"删除文档分类: {category_id}")
    
    def get_category(self, category_id: str) -> Optional[Dict[str, Any]]:
        """获取单个分类"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 
                        c.id,
                        c.project_id,
                        c.category_name,
                        c.category_desc,
                        c.display_order,
                        c.created_at,
                        c.updated_at,
                        COUNT(d.id) as doc_count
                    FROM tender_user_doc_categories c
                    LEFT JOIN tender_user_documents d ON c.id = d.category_id
                    WHERE c.id = %s
                    GROUP BY c.id, c.project_id, c.category_name, c.category_desc, 
                             c.display_order, c.created_at, c.updated_at
                    """,
                    (category_id,),
                )
                row = cur.fetchone()
        
        return self._row_to_category(row) if row else None
    
    # ==================== 文档管理 ====================
    
    async def upload_document(
        self,
        project_id: str,
        file: UploadFile,
        doc_name: str,
        category_id: Optional[str] = None,
        description: Optional[str] = None,
        doc_tags: Optional[List[str]] = None,
        owner_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        上传用户文档
        
        1. 保存文件到磁盘
        2. 入库到知识库（用于检索）
        3. 创建文档记录
        """
        logger.info(f"上传用户文档: {doc_name} (project_id={project_id})")
        
        # 1. 读取文件
        file_bytes = await file.read()
        filename = file.filename or "file"
        mime_type = getattr(file, "content_type", "application/octet-stream")
        file_size = len(file_bytes)
        
        # 2. 确定文件类型
        file_type = self._get_file_type(filename, mime_type)
        
        # 3. 保存文件到磁盘
        doc_id = str(uuid.uuid4())
        storage_path = self._save_file(project_id, doc_id, filename, file_bytes)
        
        # 4. 入库到知识库（异步调用）
        kb_doc_id = None
        try:
            ingest_service = IngestV2Service()
            
            # 根据分类映射文档类型
            from app.utils.doc_type_mapper import map_doc_type_to_kb_category
            
            # 尝试根据分类ID获取分类名称来推断类型
            kb_category = "technical_material"  # 默认为技术资料
            if category_id:
                category = self.get_category(category_id)
                if category:
                    category_name = category.get("category_name", "").lower()
                    kb_category = map_doc_type_to_kb_category("tender_user_doc", context=category_name)
            else:
                kb_category = map_doc_type_to_kb_category("tender_user_doc")
            
            ingest_result = await ingest_service.ingest_asset_v2(
                project_id=project_id,
                asset_id=doc_id,
                file_bytes=file_bytes,
                filename=filename,
                doc_type=kb_category,  # 使用映射后的知识库分类
                owner_id=owner_id,
                storage_path=storage_path,
            )
            # IngestV2Result 返回的是 doc_version_id，我们用它作为 kb_doc_id
            kb_doc_id = ingest_result.doc_version_id
            logger.info(f"文档入库成功: kb_doc_id={kb_doc_id}, segments={ingest_result.segment_count}")
        except Exception as e:
            logger.warning(f"文档入库失败: {e}，文档仍会被保存但无法检索")
        
        # 5. 创建文档记录
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tender_user_documents (
                        id, project_id, category_id, doc_name, filename, file_type, mime_type,
                        file_size, storage_path, kb_doc_id, doc_tags, description, owner_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, project_id, category_id, doc_name, filename, file_type, mime_type,
                              file_size, storage_path, kb_doc_id, doc_tags, description,
                              is_analyzed, analysis_json, meta_json, owner_id, created_at, updated_at
                    """,
                    (
                        doc_id, project_id, category_id, doc_name, filename, file_type, mime_type,
                        file_size, storage_path, kb_doc_id, doc_tags or [], description, owner_id
                    ),
                )
                row = cur.fetchone()
        
        logger.info(f"用户文档创建成功: {doc_id}")
        
        return self._row_to_document(row)
    
    def list_documents(
        self,
        project_id: Optional[str] = None,
        category_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        列出用户文档
        
        Args:
            project_id: 项目ID（可选，为空则列出所有文档）
            category_id: 分类ID（可选）
        """
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                # 构建WHERE条件
                where_clauses = []
                params = []
                
                if project_id:
                    where_clauses.append("d.project_id = %s")
                    params.append(project_id)
                
                if category_id:
                    where_clauses.append("d.category_id = %s")
                    params.append(category_id)
                
                where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
                
                cur.execute(
                    f"""
                    SELECT 
                        d.id, d.project_id, d.category_id, d.doc_name, d.filename, d.file_type,
                        d.mime_type, d.file_size, d.storage_path, d.kb_doc_id, d.doc_tags,
                        d.description, d.is_analyzed, d.analysis_json, d.meta_json, d.owner_id,
                        d.created_at, d.updated_at,
                        c.category_name
                    FROM tender_user_documents d
                    LEFT JOIN tender_user_doc_categories c ON d.category_id = c.id
                    {where_sql}
                    ORDER BY d.created_at DESC
                    """,
                    tuple(params),
                )
                rows = cur.fetchall()
        
        return [self._row_to_document(row) for row in rows]
    
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """获取单个文档"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 
                        d.id, d.project_id, d.category_id, d.doc_name, d.filename, d.file_type,
                        d.mime_type, d.file_size, d.storage_path, d.kb_doc_id, d.doc_tags,
                        d.description, d.is_analyzed, d.analysis_json, d.meta_json, d.owner_id,
                        d.created_at, d.updated_at,
                        c.category_name
                    FROM tender_user_documents d
                    LEFT JOIN tender_user_doc_categories c ON d.category_id = c.id
                    WHERE d.id = %s
                    """,
                    (doc_id,),
                )
                row = cur.fetchone()
        
        return self._row_to_document(row) if row else None
    
    def update_document(
        self,
        doc_id: str,
        doc_name: Optional[str] = None,
        category_id: Optional[str] = None,
        description: Optional[str] = None,
        doc_tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """更新文档信息"""
        updates = []
        params = []
        
        if doc_name is not None:
            updates.append("doc_name = %s")
            params.append(doc_name)
        
        if category_id is not None:
            updates.append("category_id = %s")
            params.append(category_id)
        
        if description is not None:
            updates.append("description = %s")
            params.append(description)
        
        if doc_tags is not None:
            updates.append("doc_tags = %s")
            params.append(doc_tags)
        
        if not updates:
            return self.get_document(doc_id)
        
        updates.append("updated_at = NOW()")
        params.append(doc_id)
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE tender_user_documents
                    SET {', '.join(updates)}
                    WHERE id = %s
                    """,
                    params,
                )
        
        return self.get_document(doc_id)
    
    def delete_document(self, doc_id: str):
        """删除文档"""
        # 获取文档信息
        doc = self.get_document(doc_id)
        if not doc:
            return
        
        # 删除磁盘文件
        storage_path = doc.get("storage_path")
        if storage_path and os.path.exists(storage_path):
            try:
                os.remove(storage_path)
                logger.info(f"删除文件: {storage_path}")
            except Exception as e:
                logger.error(f"删除文件失败: {e}")
        
        # 删除数据库记录
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM tender_user_documents WHERE id = %s",
                    (doc_id,),
                )
        
        logger.info(f"删除用户文档: {doc_id}")
    
    def analyze_document(
        self,
        doc_id: str,
        model_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        使用 AI 分析文档，提取关键信息
        """
        logger.info(f"开始分析文档: {doc_id}")
        
        doc = self.get_document(doc_id)
        if not doc:
            raise ValueError(f"Document not found: {doc_id}")
        
        # TODO: 实现 AI 分析逻辑
        # 1. 读取文档内容
        # 2. 使用 LLM 分析文档，提取摘要、关键信息、适用场景等
        # 3. 保存分析结果
        
        analysis_result = {
            "summary": "文档摘要（待实现）",
            "key_points": ["关键点1", "关键点2"],
            "applicable_scenarios": ["场景1", "场景2"],
        }
        
        # 更新文档记录
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tender_user_documents
                    SET is_analyzed = true, analysis_json = %s, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (json.dumps(analysis_result, ensure_ascii=False), doc_id),
                )
        
        logger.info(f"文档分析完成: {doc_id}")
        
        return self.get_document(doc_id)
    
    # ==================== 辅助方法 ====================
    
    def _save_file(self, project_id: str, doc_id: str, filename: str, file_bytes: bytes) -> str:
        """保存文件到磁盘"""
        # 创建项目目录
        project_dir = os.path.join(self.storage_dir, project_id)
        os.makedirs(project_dir, exist_ok=True)
        
        # 生成文件路径
        ext = Path(filename).suffix
        safe_filename = f"{doc_id}{ext}"
        storage_path = os.path.join(project_dir, safe_filename)
        
        # 保存文件
        with open(storage_path, "wb") as f:
            f.write(file_bytes)
        
        logger.info(f"文件已保存: {storage_path}")
        
        return storage_path
    
    def _get_file_type(self, filename: str, mime_type: str) -> str:
        """根据文件名和 MIME 类型确定文件类型"""
        ext = Path(filename).suffix.lower()
        
        # 图片类型
        if ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"]:
            return "image"
        
        # 文档类型
        if ext == ".pdf":
            return "pdf"
        if ext in [".doc", ".docx"]:
            return "docx"
        if ext in [".xls", ".xlsx"]:
            return "xlsx"
        if ext in [".ppt", ".pptx"]:
            return "pptx"
        if ext in [".txt", ".md"]:
            return "txt"
        
        # 默认为文件扩展名（去掉点）
        return ext[1:] if ext else "unknown"
    
    def _row_to_category(self, row) -> Dict[str, Any]:
        """将数据库行转换为分类字典"""
        if not row:
            return {}
        
        return {
            "id": row[0],
            "project_id": row[1],
            "category_name": row[2],
            "category_desc": row[3],
            "display_order": row[4],
            "created_at": row[5].isoformat() if row[5] else None,
            "updated_at": row[6].isoformat() if row[6] else None,
            "doc_count": row[7] if len(row) > 7 else 0,
        }
    
    def _row_to_document(self, row) -> Dict[str, Any]:
        """将数据库行转换为文档字典"""
        if not row:
            return {}
        
        return {
            "id": row[0],
            "project_id": row[1],
            "category_id": row[2],
            "doc_name": row[3],
            "filename": row[4],
            "file_type": row[5],
            "mime_type": row[6],
            "file_size": row[7],
            "storage_path": row[8],
            "kb_doc_id": row[9],
            "doc_tags": row[10] or [],
            "description": row[11],
            "is_analyzed": row[12],
            "analysis_json": row[13] or {},
            "meta_json": row[14] or {},
            "owner_id": row[15],
            "created_at": row[16].isoformat() if row[16] else None,
            "updated_at": row[17].isoformat() if row[17] else None,
            "category_name": row[18] if len(row) > 18 else None,
        }

