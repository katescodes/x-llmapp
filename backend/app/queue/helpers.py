"""
异步任务辅助函数 - Step 10
简化异步任务的提交和状态检查
"""
import logging
import os
import uuid
from typing import Any, Dict, Optional

from rq.job import Job

from app.queue.connection import get_queue, is_redis_available

logger = logging.getLogger(__name__)


def is_async_enabled(feature: str) -> bool:
    """
    检查异步功能是否启用
    
    Args:
        feature: 功能名称 (ingest/extract/review)
        
    Returns:
        是否启用异步
    """
    if feature == "ingest":
        return os.getenv("ASYNC_INGEST_ENABLED", "false").lower() == "true"
    elif feature == "extract":
        return os.getenv("ASYNC_EXTRACT_ENABLED", "false").lower() == "true"
    elif feature == "review":
        return os.getenv("ASYNC_REVIEW_ENABLED", "false").lower() == "true"
    else:
        return False


def enqueue_task(
    task_func: str,
    queue_name: str,
    *args,
    job_id: Optional[str] = None,
    **kwargs
) -> str:
    """
    提交异步任务到队列
    
    Args:
        task_func: 任务函数路径 (e.g., "app.queue.tasks.async_ingest_asset_v2")
        queue_name: 队列名称 (default/ingest/extract/review)
        *args: 任务参数
        job_id: 任务ID（可选）
        **kwargs: 任务关键字参数
        
    Returns:
        任务ID (job.id)
    """
    if not is_redis_available():
        raise RuntimeError("Redis is not available, cannot enqueue task")
    
    if job_id is None:
        job_id = f"job_{uuid.uuid4().hex}"
    
    queue = get_queue(queue_name)
    
    job = queue.enqueue(
        task_func,
        *args,
        job_id=job_id,
        job_timeout='30m',  # 30 分钟超时
        result_ttl=86400,   # 结果保留 24 小时
        failure_ttl=604800, # 失败任务保留 7 天
        **kwargs
    )
    
    logger.info(f"Task enqueued: {task_func}, job_id={job.id}, queue={queue_name}")
    
    return job.id


def get_job_status(job_id: str) -> Dict[str, Any]:
    """
    获取任务状态
    
    Args:
        job_id: 任务ID
        
    Returns:
        任务状态字典:
        {
            "status": "queued|started|finished|failed",
            "result": ...,  # 如果完成
            "error": ...,   # 如果失败
        }
    """
    if not is_redis_available():
        return {"status": "unknown", "error": "Redis not available"}
    
    try:
        from app.queue.connection import get_redis_connection
        conn = get_redis_connection()
        job = Job.fetch(job_id, connection=conn)
        
        status_map = {
            "queued": "queued",
            "started": "running",
            "finished": "succeeded",
            "failed": "failed",
            "deferred": "queued",
            "scheduled": "queued",
        }
        
        status = status_map.get(job.get_status(), "unknown")
        
        result = {
            "status": status,
            "job_id": job_id,
        }
        
        if status == "succeeded" and job.result is not None:
            result["result"] = job.result
        
        if status == "failed" and job.exc_info:
            result["error"] = str(job.exc_info)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to fetch job {job_id}: {e}")
        return {"status": "unknown", "error": str(e)}


def create_platform_job(
    namespace: str,
    biz_type: str,
    biz_id: str,
    owner_id: Optional[str] = None,
) -> str:
    """
    创建 platform_jobs 记录
    
    Args:
        namespace: 命名空间 (e.g., "tender")
        biz_type: 业务类型 (e.g., "ingest_asset_v2")
        biz_id: 业务ID (e.g., asset_id)
        owner_id: 用户ID
        
    Returns:
        job_id
    """
    from app.services.db.postgres import _get_pool
    import json
    
    job_id = f"pj_{uuid.uuid4().hex}"
    
    pool = _get_pool()
    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO platform_jobs (id, namespace, biz_type, biz_id, status, progress, owner_id)
                VALUES (%s, %s, %s, %s, 'queued', 0, %s)
                """,
                (job_id, namespace, biz_type, biz_id, owner_id)
            )
            conn.commit()
    
    logger.info(f"Platform job created: {job_id}, type={biz_type}, biz_id={biz_id}")
    
    return job_id

