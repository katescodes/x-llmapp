"""
平台任务服务 - 统一任务运行状态管理
提供跨业务系统的任务创建、进度更新、结果记录等功能
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def _job_id(prefix: str = "pj") -> str:
    """生成任务 ID"""
    return f"{prefix}_{uuid.uuid4().hex}"


class JobsService:
    """平台任务服务"""

    def __init__(self, pool: ConnectionPool):
        """
        初始化服务
        
        Args:
            pool: PostgreSQL 连接池
        """
        self.pool = pool

    def create_job(
        self,
        namespace: str,
        biz_type: str,
        biz_id: str,
        owner_id: Optional[str] = None,
        initial_status: str = "queued",
        initial_message: Optional[str] = None
    ) -> str:
        """
        创建新任务
        
        Args:
            namespace: 业务命名空间，如 "tender"
            biz_type: 业务类型，如 "extract_project_info", "extract_risks", "review_run"
            biz_id: 业务ID，如 project_id, run_id
            owner_id: 任务所有者ID
            initial_status: 初始状态，默认 "queued"
            initial_message: 初始消息
            
        Returns:
            job_id: 创建的任务ID
        """
        job_id = _job_id()
        
        sql = """
            INSERT INTO platform_jobs (
                id, namespace, biz_type, biz_id, status, progress, message, owner_id, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, now(), now()
            )
        """
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    job_id,
                    namespace,
                    biz_type,
                    biz_id,
                    initial_status,
                    0,  # initial progress
                    initial_message,
                    owner_id
                ))
        
        return job_id

    def update_job_progress(
        self,
        job_id: str,
        progress: int,
        status: Optional[str] = None,
        message: Optional[str] = None
    ) -> None:
        """
        更新任务进度
        
        Args:
            job_id: 任务ID
            progress: 进度值 (0-100)
            status: 状态（可选），如 "running"
            message: 状态消息（可选）
        """
        # 确保进度在有效范围
        progress = max(0, min(100, progress))
        
        sql = """
            UPDATE platform_jobs
            SET progress = %s,
                updated_at = now()
        """
        params = [progress]
        
        if status is not None:
            sql += ", status = %s"
            params.append(status)
        
        if message is not None:
            sql += ", message = %s"
            params.append(message)
        
        sql += " WHERE id = %s"
        params.append(job_id)
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))

    def finish_job_success(
        self,
        job_id: str,
        result: Optional[Dict[str, Any]] = None,
        message: Optional[str] = None
    ) -> None:
        """
        标记任务成功完成
        
        Args:
            job_id: 任务ID
            result: 结果数据（可选）
            message: 完成消息（可选）
        """
        result_json = json.dumps(result or {})
        
        sql = """
            UPDATE platform_jobs
            SET status = 'succeeded',
                progress = 100,
                message = %s,
                result_json = %s::jsonb,
                updated_at = now()
            WHERE id = %s
        """
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (message, result_json, job_id))

    def finish_job_fail(
        self,
        job_id: str,
        error: str,
        progress: Optional[int] = None
    ) -> None:
        """
        标记任务失败
        
        Args:
            job_id: 任务ID
            error: 错误消息
            progress: 失败时的进度（可选，不提供则保持当前进度）
        """
        sql = """
            UPDATE platform_jobs
            SET status = 'failed',
                message = %s,
                updated_at = now()
        """
        params = [error]
        
        if progress is not None:
            sql += ", progress = %s"
            params.append(max(0, min(100, progress)))
        
        sql += " WHERE id = %s"
        params.append(job_id)
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        获取单个任务信息
        
        Args:
            job_id: 任务ID
            
        Returns:
            任务信息字典或 None
        """
        sql = """
            SELECT id, namespace, biz_type, biz_id, status, progress, message,
                   result_json, owner_id, created_at, updated_at
            FROM platform_jobs
            WHERE id = %s
        """
        
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, (job_id,))
                return cur.fetchone()

    def list_jobs_by_biz_id(
        self,
        namespace: str,
        biz_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        根据业务ID查询所有相关任务
        
        Args:
            namespace: 业务命名空间
            biz_id: 业务ID
            limit: 最大返回数量
            
        Returns:
            任务列表
        """
        sql = """
            SELECT id, namespace, biz_type, biz_id, status, progress, message,
                   result_json, owner_id, created_at, updated_at
            FROM platform_jobs
            WHERE namespace = %s AND biz_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """
        
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, (namespace, biz_id, limit))
                return list(cur.fetchall())

    def list_jobs_by_project(
        self,
        project_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        查询项目的所有任务（快捷方法）
        
        Args:
            project_id: 项目ID
            limit: 最大返回数量
            
        Returns:
            任务列表
        """
        return self.list_jobs_by_biz_id("tender", project_id, limit)

    def list_all_jobs(
        self,
        namespace: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        查询所有任务（支持过滤）
        
        Args:
            namespace: 命名空间过滤（可选）
            status: 状态过滤（可选）
            limit: 最大返回数量
            offset: 偏移量
            
        Returns:
            任务列表
        """
        sql = """
            SELECT id, namespace, biz_type, biz_id, status, progress, message,
                   result_json, owner_id, created_at, updated_at
            FROM platform_jobs
            WHERE 1=1
        """
        params = []
        
        if namespace:
            sql += " AND namespace = %s"
            params.append(namespace)
        
        if status:
            sql += " AND status = %s"
            params.append(status)
        
        sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, tuple(params))
                return list(cur.fetchall())

