"""
异步任务定义 - Step 10
支持 ingest, extract, review 的异步执行
"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ==================== Ingest v2 异步任务 ====================

def async_ingest_asset_v2(
    project_id: str,
    asset_id: str,
    owner_id: Optional[str] = None,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    异步执行资产入库 v2
    
    Args:
        project_id: 项目ID
        asset_id: 资产ID
        owner_id: 用户ID
        job_id: 任务ID (platform_jobs.id)
        
    Returns:
        入库结果
    """
    from app.services.db.postgres import _get_pool
    from app.platform.ingest.v2_service import IngestV2Service
    from app.services.embedding.http_embedding_client import HttpEmbeddingClient
    
    logger.info(f"[Worker] async_ingest_asset_v2 start: project={project_id}, asset={asset_id}")
    
    pool = _get_pool()
    
    # 更新 job 状态为 running
    if job_id:
        _update_job_status(job_id, "running", 10, "正在入库...")
    
    try:
        # 获取 asset 信息
        from app.services.dao.tender_dao import TenderDAO
        dao = TenderDAO(pool)
        asset = dao.get_asset(asset_id)
        if not asset:
            raise ValueError(f"Asset not found: {asset_id}")
        
        storage_path = asset.get("storage_path")
        doc_type = asset.get("kind", "tender")  # tender / bid / custom_rule
        
        if not storage_path:
            raise ValueError(f"Asset {asset_id} has no storage_path")
        
        # 执行 v2 入库
        embedding_client = HttpEmbeddingClient()
        ingest_service = IngestV2Service(pool, embedding_client)
        
        result = ingest_service.ingest_asset_v2(
            project_id=project_id,
            asset_id=asset_id,
            file_path=storage_path,
            doc_type=doc_type,
            owner_id=owner_id,
        )
        
        # 更新 job 状态为 succeeded
        if job_id:
            _update_job_status(job_id, "succeeded", 100, "入库完成", result)
        
        logger.info(f"[Worker] async_ingest_asset_v2 done: asset={asset_id}, segments={result.get('segment_count', 0)}")
        return result
        
    except Exception as e:
        logger.error(f"[Worker] async_ingest_asset_v2 failed: {e}", exc_info=True)
        
        # 更新 job 状态为 failed
        if job_id:
            _update_job_status(job_id, "failed", 0, f"入库失败: {str(e)}")
        
        raise


# ==================== Extract v2 异步任务 ====================

def async_extract_project_info_v2(
    project_id: str,
    model_id: Optional[str],
    run_id: Optional[str] = None,
    owner_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    异步执行项目信息抽取 v2
    
    Args:
        project_id: 项目ID
        model_id: 模型ID
        run_id: tender_runs.id
        owner_id: 用户ID
        
    Returns:
        抽取结果
    """
    from app.services.db.postgres import _get_pool
    from app.works.tender.extract_v2_service import ExtractV2Service
    from app.services.llm.llm_client import LLMClient
    from app.services.dao.tender_dao import TenderDAO
    
    logger.info(f"[Worker] async_extract_project_info_v2 start: project={project_id}")
    
    pool = _get_pool()
    dao = TenderDAO(pool)
    
    # 更新 run 状态
    if run_id:
        dao.update_run(run_id, "running", progress=0.1, message="正在抽取项目信息...")
    
    try:
        llm_client = LLMClient()
        extract_v2 = ExtractV2Service(pool, llm_client)
        
        result = extract_v2.extract_project_info_v2(
            project_id=project_id,
            model_id=model_id,
            run_id=run_id,
            owner_id=owner_id,
        )
        
        # 写入旧表（保证前端兼容）
        data = result.get("data") or {}
        eids = result.get("evidence_chunk_ids") or []
        dao.upsert_project_info(project_id, data_json=data, evidence_chunk_ids=eids)
        
        # 更新 run 状态
        if run_id:
            dao.update_run(run_id, "success", progress=1.0, message="ok", result_json=result)
        
        logger.info(f"[Worker] async_extract_project_info_v2 done: project={project_id}")
        return result
        
    except Exception as e:
        logger.error(f"[Worker] async_extract_project_info_v2 failed: {e}", exc_info=True)
        
        if run_id:
            dao.update_run(run_id, "failed", progress=0.0, message=str(e))
        
        raise


def async_extract_risks_v2(
    project_id: str,
    model_id: Optional[str],
    run_id: Optional[str] = None,
    owner_id: Optional[str] = None,
) -> list:
    """
    异步执行风险抽取 v2
    
    Args:
        project_id: 项目ID
        model_id: 模型ID
        run_id: tender_runs.id
        owner_id: 用户ID
        
    Returns:
        风险列表
    """
    from app.services.db.postgres import _get_pool
    from app.works.tender.extract_v2_service import ExtractV2Service
    from app.services.llm.llm_client import LLMClient
    from app.services.dao.tender_dao import TenderDAO
    
    logger.info(f"[Worker] async_extract_risks_v2 start: project={project_id}")
    
    pool = _get_pool()
    dao = TenderDAO(pool)
    
    # 更新 run 状态
    if run_id:
        dao.update_run(run_id, "running", progress=0.1, message="正在抽取风险...")
    
    try:
        llm_client = LLMClient()
        extract_v2 = ExtractV2Service(pool, llm_client)
        
        result = extract_v2.extract_risks_v2(
            project_id=project_id,
            model_id=model_id,
            run_id=run_id,
            owner_id=owner_id,
        )
        
        # 写入旧表（保证前端兼容）
        dao.replace_risks(project_id, result)
        
        # 更新 run 状态
        if run_id:
            dao.update_run(run_id, "success", progress=1.0, message="ok", result_json=result)
        
        logger.info(f"[Worker] async_extract_risks_v2 done: project={project_id}, count={len(result)}")
        return result
        
    except Exception as e:
        logger.error(f"[Worker] async_extract_risks_v2 failed: {e}", exc_info=True)
        
        if run_id:
            dao.update_run(run_id, "failed", progress=0.0, message=str(e))
        
        raise


# ==================== Review v2 异步任务 ====================

# async_review_run_v2 已删除，统一使用 V3 审核


# ==================== Helper Functions ====================

def _update_job_status(
    job_id: str,
    status: str,
    progress: int,
    message: str,
    result_json: Optional[Dict[str, Any]] = None,
):
    """更新 platform_jobs 状态"""
    from app.services.db.postgres import _get_pool
    import json
    
    pool = _get_pool()
    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            if result_json:
                cur.execute(
                    """
                    UPDATE platform_jobs
                    SET status=%s, progress=%s, message=%s, result_json=%s, updated_at=NOW()
                    WHERE id=%s
                    """,
                    (status, progress, message, json.dumps(result_json), job_id)
                )
            else:
                cur.execute(
                    """
                    UPDATE platform_jobs
                    SET status=%s, progress=%s, message=%s, updated_at=NOW()
                    WHERE id=%s
                    """,
                    (status, progress, message, job_id)
                )
            conn.commit()

