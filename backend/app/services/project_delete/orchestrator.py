"""
项目删除编排器
负责协调所有资源清理器、生成删除计划、执行删除操作
"""
import hashlib
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from psycopg_pool import ConnectionPool

from app.schemas.project_delete import DeletePlanItem, ProjectDeletePlanResponse
from .cleaners import (
    AssetResourceCleaner,
    DocumentResourceCleaner,
    KnowledgeBaseResourceCleaner,
    MetadataResourceCleaner,
    ProjectResourceCleaner,
)

logger = logging.getLogger(__name__)


class ProjectDeletionOrchestrator:
    """项目删除编排器"""
    
    def __init__(self, pool: ConnectionPool):
        self.pool = pool
        self.cleaners: List[ProjectResourceCleaner] = [
            AssetResourceCleaner(pool),
            DocumentResourceCleaner(pool),
            KnowledgeBaseResourceCleaner(pool),
            MetadataResourceCleaner(pool),
        ]
    
    def build_plan(self, project_id: str) -> ProjectDeletePlanResponse:
        """
        生成删除计划
        
        Args:
            project_id: 项目ID
            
        Returns:
            删除计划响应
        """
        # 1. 查询项目信息
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT project_id, name FROM tender_projects WHERE project_id=%s",
                    (project_id,)
                )
                row = cur.fetchone()
        
        if not row:
            raise ValueError(f"Project {project_id} not found")
        
        project_name = row['name']
        
        # 2. 收集各类资源的删除计划
        items: List[DeletePlanItem] = []
        for cleaner in self.cleaners:
            try:
                plan_dict = cleaner.plan(project_id)
                if plan_dict["count"] > 0:
                    items.append(DeletePlanItem(**plan_dict))
            except Exception as e:
                logger.error(f"Failed to build plan for {cleaner.type()}: {e}")
                # 继续处理其他清理器
        
        # 3. 生成确认令牌（基于 project_id + project_name + 计划内容）
        plan_json = json.dumps(
            {
                "project_id": project_id,
                "project_name": project_name,
                "items": [item.dict() for item in items],
            },
            sort_keys=True,
        )
        confirm_token = hashlib.sha256(plan_json.encode()).hexdigest()[:16]
        
        return ProjectDeletePlanResponse(
            project_id=project_id,
            project_name=project_name,
            items=items,
            confirm_token=confirm_token,
            warning="删除后无法恢复！将删除所有关联的文档、知识库、风险、目录、审核记录等。",
        )
    
    def delete(self, project_id: str) -> None:
        """
        执行删除操作
        
        Args:
            project_id: 项目ID
        """
        # 1. 创建删除审计记录
        audit_id = self._create_audit(project_id, "RUNNING")
        
        try:
            # 2. 按顺序执行清理器（KB → 文档 → 资产 → 元数据）
            for cleaner in self.cleaners:
                try:
                    logger.info(f"Cleaning {cleaner.type()} for project {project_id}")
                    cleaner.delete(project_id)
                except Exception as e:
                    logger.error(f"Failed to clean {cleaner.type()}: {e}")
                    # 继续清理其他资源
            
            # 3. 最后删除项目本身
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM tender_projects WHERE project_id=%s",
                        (project_id,)
                    )
                conn.commit()
            
            logger.info(f"Successfully deleted project {project_id}")
            
            # 4. 更新审计记录为成功
            self._update_audit(audit_id, "SUCCESS")
            
        except Exception as e:
            # 更新审计记录为失败
            self._update_audit(audit_id, "FAILED", error_message=str(e))
            raise
    
    def _create_audit(self, project_id: str, status: str) -> str:
        """创建删除审计记录"""
        # 查询项目名称
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT name FROM tender_projects WHERE project_id=%s",
                    (project_id,)
                )
                row = cur.fetchone()
        
        project_name = list(row.values())[0] if row else "Unknown"
        audit_id = f"audit_{uuid.uuid4().hex}"
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tender_project_delete_audit
                      (id, project_id, project_name, status, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    """,
                    (audit_id, project_id, project_name, status)
                )
            conn.commit()
        
        return audit_id
    
    def _update_audit(self, audit_id: str, status: str, error_message: Optional[str] = None):
        """更新删除审计记录"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tender_project_delete_audit
                    SET status=%s, error_message=%s, finished_at=NOW()
                    WHERE id=%s
                    """,
                    (status, error_message, audit_id)
                )
            conn.commit()
