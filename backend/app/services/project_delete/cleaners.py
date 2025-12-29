"""
项目资源清理器
每个清理器负责清理一类资源
"""
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)


class ProjectResourceCleaner(ABC):
    """资源清理器基类"""
    
    @abstractmethod
    def type(self) -> str:
        """资源类型"""
        pass
    
    @abstractmethod
    def plan(self, project_id: str) -> Dict[str, Any]:
        """生成删除计划（不执行删除）"""
        pass
    
    @abstractmethod
    def delete(self, project_id: str) -> None:
        """执行删除"""
        pass


class AssetResourceCleaner(ProjectResourceCleaner):
    """资产资源清理器（tender_project_assets）"""
    
    def __init__(self, pool: ConnectionPool):
        self.pool = pool
    
    def type(self) -> str:
        return "ASSET"
    
    def plan(self, project_id: str) -> Dict[str, Any]:
        """计划删除资产"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, kind, filename, storage_path
                    FROM tender_project_assets
                    WHERE project_id=%s
                    ORDER BY created_at ASC
                    """,
                    (project_id,)
                )
                rows = cur.fetchall()
        
        count = len(rows)
        samples = [row.get('title') or f"{row.get('filename')}_{row.get('id', '')[:8]}" for row in rows[:5]]
        physical_targets = [row.get('storage_path') for row in rows if row.get('storage_path')]  # storage_path
        
        return {
            "type": self.type(),
            "count": count,
            "samples": samples,
            "physical_targets": physical_targets[:10],  # 只显示前10个
        }
    
    def delete(self, project_id: str) -> None:
        """删除资产记录和物理文件"""
        # 1. 查询所有资产
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, storage_path FROM tender_project_assets WHERE project_id=%s",
                    (project_id,)
                )
                rows = cur.fetchall()
        
        # 2. 删除物理文件（仅 template 类型有 storage_path）
        for asset_id, storage_path in rows:
            if storage_path and os.path.exists(storage_path):
                try:
                    os.remove(storage_path)
                    logger.info(f"Deleted file: {storage_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete file {storage_path}: {e}")
        
        # 3. 删除数据库记录
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM tender_project_assets WHERE project_id=%s",
                    (project_id,)
                )
            conn.commit()
        
        logger.info(f"Deleted {len(rows)} assets for project {project_id}")


class DocumentResourceCleaner(ProjectResourceCleaner):
    """文档资源清理器（tender_project_documents）"""
    
    def __init__(self, pool: ConnectionPool):
        self.pool = pool
    
    def type(self) -> str:
        return "DOCUMENT"
    
    def plan(self, project_id: str) -> Dict[str, Any]:
        """计划删除文档绑定"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, doc_role, kb_doc_id
                    FROM tender_project_documents
                    WHERE project_id=%s
                    ORDER BY created_at ASC
                    """,
                    (project_id,)
                )
                rows = cur.fetchall()
        
        count = len(rows)
        samples = [f"{list(row.values())[1]}_{list(row.values())[2][:8]}" for row in rows[:5]]
        
        return {
            "type": self.type(),
            "count": count,
            "samples": samples,
            "physical_targets": [],
        }
    
    def delete(self, project_id: str) -> None:
        """删除文档绑定记录"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM tender_project_documents WHERE project_id=%s",
                    (project_id,)
                )
            conn.commit()
        
        logger.info(f"Deleted document bindings for project {project_id}")


class KnowledgeBaseResourceCleaner(ProjectResourceCleaner):
    """知识库资源清理器（kb_documents + kb_chunks）"""
    
    def __init__(self, pool: ConnectionPool):
        self.pool = pool
    
    def type(self) -> str:
        return "KB"
    
    def plan(self, project_id: str) -> Dict[str, Any]:
        """计划删除知识库资源"""
        # 1. 获取项目的 kb_id
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT kb_id FROM tender_projects WHERE id=%s",
                    (project_id,)
                )
                row = cur.fetchone()
        
        if not row:
            return {
                "type": self.type(),
                "count": 0,
                "samples": [],
                "physical_targets": [],
            }
        
        kb_id = list(row.values())[0]
        
        # 2. 统计 kb_documents
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, filename
                    FROM kb_documents
                    WHERE kb_id=%s
                    ORDER BY created_at ASC
                    """,
                    (kb_id,)
                )
                docs = cur.fetchall()
                
                cur.execute(
                    "SELECT COUNT(*) FROM kb_chunks WHERE kb_id=%s",
                    (kb_id,)
                )
                chunk_count = list(cur.fetchone().values())[0]
        
        doc_count = len(docs)
        # 优化：避免多次调用list(row.values())
        samples = []
        for row in docs[:5]:
            values = list(row.values())
            if len(values) > 1 and values[1]:
                sample = values[1]
            elif len(values) > 0:
                sample = str(values[0])[:12]
            else:
                sample = ""
            samples.append(sample)
        
        physical_targets = [f"kb_collection: {kb_id}", f"chunks: {chunk_count}"]
        
        return {
            "type": self.type(),
            "count": doc_count,
            "samples": samples,
            "physical_targets": physical_targets,
        }
    
    def delete(self, project_id: str) -> None:
        """删除知识库资源（文档、分块、向量）"""
        # 1. 获取项目的 kb_id
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT kb_id FROM tender_projects WHERE id=%s",
                    (project_id,)
                )
                row = cur.fetchone()
        
        if not row:
            logger.warning(f"Project {project_id} not found, skipping KB cleanup")
            return
        
        kb_id = list(row.values())[0]
        
        # 2. 删除 kb_chunks
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM kb_chunks WHERE kb_id=%s", (kb_id,))
                chunk_count = cur.rowcount
            conn.commit()
        
        logger.info(f"Deleted {chunk_count} chunks for kb_id {kb_id}")
        
        # 3. 删除 kb_documents
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM kb_documents WHERE kb_id=%s", (kb_id,))
                doc_count = cur.rowcount
            conn.commit()
        
        logger.info(f"Deleted {doc_count} documents for kb_id {kb_id}")
        
        # 4. 删除知识库本身（如果有 kb 表）
        # 注意：根据你的系统设计，可能还需要删除向量索引等
        # 这里假设 kb_service.delete_kb() 会处理这些
        try:
            from app.services import kb_service
            kb_service.delete_kb(kb_id)
            logger.info(f"Deleted knowledge base {kb_id}")
        except Exception as e:
            logger.warning(f"Failed to delete KB {kb_id} via kb_service: {e}")


class MetadataResourceCleaner(ProjectResourceCleaner):
    """项目元数据清理器（risks, directory, review, runs, project_info）"""
    
    def __init__(self, pool: ConnectionPool):
        self.pool = pool
    
    def type(self) -> str:
        return "METADATA"
    
    def plan(self, project_id: str) -> Dict[str, Any]:
        """计划删除项目元数据"""
        counts = {}
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                # 统计各类资源
                cur.execute("SELECT COUNT(*) as count FROM tender_risks WHERE project_id=%s", (project_id,))
                counts["risks"] = cur.fetchone()['count']
                
                cur.execute("SELECT COUNT(*) as count FROM tender_directory_nodes WHERE project_id=%s", (project_id,))
                counts["directory"] = cur.fetchone()['count']
                
                cur.execute("SELECT COUNT(*) as count FROM tender_review_items WHERE project_id=%s", (project_id,))
                counts["review"] = cur.fetchone()['count']
                
                cur.execute("SELECT COUNT(*) as count FROM tender_runs WHERE project_id=%s", (project_id,))
                counts["runs"] = cur.fetchone()['count']
                
                cur.execute("SELECT COUNT(*) as count FROM tender_project_info WHERE project_id=%s", (project_id,))
                counts["project_info"] = cur.fetchone()['count']
        
        total = sum(counts.values())
        samples = [f"{k}: {v}" for k, v in counts.items() if v > 0]
        
        return {
            "type": self.type(),
            "count": total,
            "samples": samples,
            "physical_targets": [],
        }
    
    def delete(self, project_id: str) -> None:
        """删除项目元数据（CASCADE 会自动删除）"""
        # 由于外键 ON DELETE CASCADE，删除项目时会自动删除这些
        # 这里显式删除以确保清理完整
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tender_risks WHERE project_id=%s", (project_id,))
                cur.execute("DELETE FROM tender_directory_nodes WHERE project_id=%s", (project_id,))
                cur.execute("DELETE FROM tender_review_items WHERE project_id=%s", (project_id,))
                cur.execute("DELETE FROM tender_runs WHERE project_id=%s", (project_id,))
                cur.execute("DELETE FROM tender_project_info WHERE project_id=%s", (project_id,))
            conn.commit()
        
        logger.info(f"Deleted metadata for project {project_id}")
