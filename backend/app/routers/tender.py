"""
招投标应用 - REST API 路由
提供所有 HTTP 接口
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from psycopg_pool import ConnectionPool
import psycopg.rows

from app.schemas.tender import (
    AssetOut,
    ChunkLookupReq,
    DirectorySaveReq,
    ExtractReq,
    ProjectCreateReq,
    ProjectInfoOut,
    ProjectOut,
    ReviewItemOut,
    ReviewRunReq,
    RunOut,
)
from app.schemas.project_delete import (
    ProjectDeletePlanResponse,
    ProjectDeleteRequest,
)
from pydantic import BaseModel
from app.config import get_feature_flags
from app.services.dao.tender_dao import TenderDAO
from app.services.tender_service import TenderService
from app.services.platform.jobs_service import JobsService
from app.services import kb_service
from app.utils.auth import get_current_user_sync
from app.utils.permission import require_permission
from app.utils.evidence_mapper import chunks_to_span_refs

# 创建路由器
router = APIRouter(prefix="/api/apps/tender", tags=["tender"])

# 导入格式模板子路由
from . import format_templates
router.include_router(format_templates.router)

def _serialize_directory_nodes(flat_nodes: List[dict]) -> List[dict]:
    """
    将 service/dao 返回的目录节点（扁平，可能带 bodyMeta/meta_json）序列化为前端使用的格式。
    """
    return [
        {
            "id": r["id"],
            "parent_id": r.get("parent_id"),
            "order_no": r.get("order_no") or 0,
            "numbering": r["numbering"],
            "level": r["level"],
            "title": r["title"],
            "required": bool(r.get("is_required", False)),
            "source": r.get("source") or "tender",
            "notes": r.get("notes") or "",
            "volume": r.get("volume") or "",
            "evidence_chunk_ids": r.get("evidence_chunk_ids") or [],
            "bodyMeta": r.get("bodyMeta") or {"source": "EMPTY", "fragmentId": None, "hasContent": False},
        }
        for r in flat_nodes
    ]


# ==================== 依赖注入 ====================

def _get_pool(req: Request) -> ConnectionPool:
    """从 postgres 模块获取连接池"""
    from app.services.db.postgres import _get_pool as get_sync_pool
    return get_sync_pool()


def _get_llm(req: Request):
    """从 app.state 获取 LLM orchestrator"""
    llm = getattr(req.app.state, "llm_orchestrator", None)
    if llm is None:
        raise HTTPException(status_code=500, detail="LLM orchestrator not initialized on app.state")
    return llm


def _svc(req: Request) -> TenderService:
    """创建 TenderService 实例"""
    dao = TenderDAO(_get_pool(req))
    # 根据 feature flags 决定是否注入 jobs_service
    jobs_service = None
    flags = get_feature_flags()
    if flags.PLATFORM_JOBS_ENABLED:
        jobs_service = JobsService(_get_pool(req))
    return TenderService(dao=dao, llm_orchestrator=_get_llm(req), jobs_service=jobs_service)


# ==================== 项目管理 ====================

@router.post("/projects", response_model=ProjectOut)
def create_project(req: ProjectCreateReq, request: Request, user=Depends(require_permission("tender.create"))):
    """创建项目（自动创建KB）"""
    # 1. 先创建知识库，设置owner为当前用户
    kb_id = kb_service.create_kb(
        name=f"招投标-{req.name}",
        description=req.description or f"招投标项目：{req.name}",
        category_id="cat_knowledge",  # 使用正确的分类ID
        owner_id=user.user_id  # 关键：设置知识库所有者
    )
    
    # 2. 创建项目并关联KB
    dao = TenderDAO(_get_pool(request))
    row = dao.create_project(kb_id, req.name, req.description, owner_id=user.user_id)
    return row


@router.get("/projects", response_model=List[ProjectOut])
def list_projects(request: Request, user=Depends(get_current_user_sync)):
    """列出当前用户的所有项目"""
    dao = TenderDAO(_get_pool(request))
    return dao.list_projects(owner_id=user.user_id)


class ProjectUpdateReq(BaseModel):
    """更新项目请求"""
    name: Optional[str] = None
    description: Optional[str] = None


@router.put("/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, req: ProjectUpdateReq, request: Request, user=Depends(get_current_user_sync)):
    """更新项目信息"""
    svc = _svc(request)
    try:
        updated = svc.update_project(project_id, req.name, req.description)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/projects/{project_id}/delete-plan", response_model=ProjectDeletePlanResponse)
def get_project_delete_plan(project_id: str, request: Request, user=Depends(get_current_user_sync)):
    """
    获取项目删除计划（预检）
    返回将被删除的资源清单和确认令牌
    """
    svc = _svc(request)
    try:
        return svc.get_project_delete_plan(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, req: ProjectDeleteRequest, request: Request, user=Depends(get_current_user_sync)):
    """
    删除项目（需要确认）
    必须提供正确的确认文本和确认令牌
    """
    svc = _svc(request)
    try:
        svc.delete_project(project_id, req)
        return None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# REMOVED: list_legacy_documents endpoint moved to routers/legacy/tender_legacy.py
# To re-enable, set LEGACY_TENDER_APIS_ENABLED=true


# ==================== 资产管理 ====================

@router.get("/projects/{project_id}/assets", response_model=List[AssetOut])
def list_assets(project_id: str, request: Request):
    """列出项目的所有资产"""
    dao = TenderDAO(_get_pool(request))
    return dao.list_assets(project_id)


@router.delete("/projects/{project_id}/assets/{asset_id}", status_code=204)
def delete_asset(project_id: str, asset_id: str, request: Request):
    """
    删除资产
    - 删除数据库记录
    - 删除知识库文档
    - 删除磁盘文件（如果是模板文件）
    """
    svc = _svc(request)
    try:
        svc.delete_asset(project_id, asset_id)
        # 显式返回 None，FastAPI 会自动处理为 204 No Content
        return None
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete asset: {str(e)}")


@router.get("/projects/{project_id}/assets/{asset_id}/view")
async def view_asset(
    project_id: str,
    asset_id: str,
    request: Request
):
    """
    查看/打开资产文件
    返回文件内容，浏览器会根据Content-Type决定如何处理（在新标签页打开或下载）
    """
    from fastapi.responses import FileResponse
    from urllib.parse import quote
    import os
    
    dao = TenderDAO(_get_pool(request))
    
    with dao.pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT filename, storage_path, mime_type, kb_doc_id
                FROM tender_project_assets
                WHERE id = %s AND project_id = %s
            """, [asset_id, project_id])
            
            row = cur.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="文件未找到")
            
            filename = row['filename']
            storage_path = row['storage_path']
            mime_type = row['mime_type'] or 'application/octet-stream'
            kb_doc_id = row['kb_doc_id']
            
            # 对文件名进行 URL 编码以支持中文
            encoded_filename = quote(filename or 'file')
            
            # 检查文件是否存储在磁盘上
            if storage_path and os.path.exists(storage_path):
                # 从文件系统读取
                return FileResponse(
                    storage_path,
                    media_type=mime_type,
                    headers={
                        'Content-Disposition': f"inline; filename*=UTF-8''{encoded_filename}",
                    }
                )
            elif kb_doc_id:
                # 文件在知识库中，从 docstore 读取
                from app.services.docstore import get_docstore
                docstore = get_docstore()
                
                # 获取文档的存储路径
                doc_info = docstore.get_document(kb_doc_id)
                if not doc_info:
                    raise HTTPException(status_code=404, detail="文件内容不存在")
                
                # 尝试从 docstore 的存储路径读取
                doc_storage_path = doc_info.get('storage_path')
                if doc_storage_path and os.path.exists(doc_storage_path):
                    return FileResponse(
                        doc_storage_path,
                        media_type=mime_type,
                        headers={
                            'Content-Disposition': f"inline; filename*=UTF-8''{encoded_filename}",
                        }
                    )
                else:
                    raise HTTPException(status_code=404, detail="文件内容不存在")
            else:
                raise HTTPException(status_code=404, detail="文件内容不存在")


@router.post("/projects/{project_id}/assets/import", response_model=List[AssetOut])
async def import_assets(
    project_id: str,
    request: Request,
    kind: str = Form(...),  # tender | bid | template | custom_rule | company_profile | tech_doc | case_study | finance_doc | cert_doc
    bidder_name: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
):
    """
    项目内上传文件并自动绑定
    
    Args:
        kind: 文件类型（tender/bid/company_profile/tech_doc/case_study/finance_doc/cert_doc/template/custom_rule）
        bidder_name: 投标人名称（kind=bid 时必填）
        files: 上传的文件列表
    """
    # 参数校验
    if kind not in ("tender", "bid", "template", "custom_rule", "company_profile", "tech_doc", "case_study", "finance_doc", "cert_doc"):
        raise HTTPException(status_code=400, detail="invalid kind")
    if kind == "bid" and not (bidder_name or "").strip():
        raise HTTPException(status_code=400, detail="bidder_name required for bid")
    
    svc = _svc(request)
    try:
        return await svc.import_assets(project_id, kind, files, bidder_name)
    except ValueError as e:
        # 文件解析错误或业务逻辑错误，返回 400
        error_msg = str(e)
        if "文件解析失败" in error_msg or "DOCX parse failed" in error_msg or "BadZipFile" in error_msg:
            raise HTTPException(
                status_code=400, 
                detail=f"文件损坏或格式错误，无法解析: {error_msg}"
            )
        raise HTTPException(status_code=400, detail=error_msg)


# ==================== 运行任务管理 ====================

@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str, request: Request):
    """获取运行任务状态"""
    dao = TenderDAO(_get_pool(request))
    row = dao.get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="run not found")
    return row


@router.get("/projects/{project_id}/runs/latest")
def get_latest_runs(project_id: str, request: Request):
    """获取项目的最新run状态（每种类型的最新一个）"""
    dao = TenderDAO(_get_pool(request))
    
    # 查询各类型的最新run
    kinds = ["extract_project_info", "extract_risks", "generate_directory", "review"]
    result = {}
    
    with dao.pool.connection() as conn:
        # 设置row_factory使返回dict
        conn.row_factory = psycopg.rows.dict_row
        for kind in kinds:
            # 查询该类型的最新run
            runs = conn.execute(
                """
                SELECT id, project_id, kind, status, progress, message, started_at, finished_at
                FROM tender_runs
                WHERE project_id = %s AND kind = %s
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (project_id, kind)
            ).fetchall()
            
            if runs:
                run = runs[0]
                result[kind] = {
                    "id": run["id"],
                    "status": run["status"],
                    "progress": run["progress"],
                    "message": run["message"],
                    "kind": run["kind"],
                }
            else:
                result[kind] = None
    
    return result


# ==================== 招标要求抽取 ====================

@router.post("/projects/{project_id}/extract/requirements")
async def extract_requirements(
    project_id: str,
    req: ExtractReq,
    request: Request,
    bg: BackgroundTasks,
    sync: int = 0,
    user=Depends(get_current_user_sync),
):
    """抽取招标要求（框架式自主提取）
    
    Args:
        sync: 同步执行模式，1=同步返回结果，0=后台任务（默认）
    """
    dao = TenderDAO(_get_pool(request))
    run_id = dao.create_run(project_id, "extract_requirements_v2")
    dao.update_run(run_id, "running", progress=0.01, message="running")
    
    # 获取ExtractV2Service
    pool = _get_pool(request)
    llm_orchestrator = getattr(request.app.state, 'llm_orchestrator', None)
    
    from app.works.tender.extract_v2_service import ExtractV2Service
    extract_svc = ExtractV2Service(
        pool=pool,
        llm_orchestrator=llm_orchestrator
    )
    
    # 检查是否同步执行
    run_sync = sync == 1 or request.headers.get("X-Run-Sync") == "1"
    
    async def job():
        try:
            result = await extract_svc.extract_requirements_v2(
                project_id=project_id,
                model_id=req.model_id,
                checklist_template=getattr(req, 'checklist_template', 'engineering'),
                run_id=run_id
            )
            dao.update_run(run_id, "success", progress=1.0, result_json=result)
            return result
        except Exception as e:
            logger.error(f"Extract requirements failed: {e}", exc_info=True)
            dao.update_run(run_id, "failed", progress=0.0, message=str(e))
            raise
    
    if run_sync:
        # 同步执行
        try:
            result = await job()
            return {"run_id": run_id, "status": "completed", "result": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # 后台执行
        bg.add_task(lambda: asyncio.run(job()))
        return {"run_id": run_id, "status": "running", "message": "Task started in background"}

# ==================== 项目信息抽取 ====================

@router.post("/projects/{project_id}/extract/project-info")
async def extract_project_info(
    project_id: str,
    req: ExtractReq,
    request: Request,
    bg: BackgroundTasks,
    sync: int = 0,
    user=Depends(get_current_user_sync),
):
    """抽取项目信息
    
    Args:
        sync: 同步执行模式，1=同步返回结果，0=后台任务（默认）
    """
    dao = TenderDAO(_get_pool(request))
    
    # 🔥 删除历史项目信息数据
    dao.delete_project_info(project_id)
    logger.info(f"[extract_project_info] 已删除历史项目信息: project_id={project_id}")
    
    run_id = dao.create_run(project_id, "extract_project_info")
    dao.update_run(run_id, "running", progress=0.01, message="初始化...")
    svc = _svc(request)
    owner_id = user.user_id if user else None
    
    # 检查是否同步执行
    run_sync = sync == 1 or request.headers.get("X-Run-Sync") == "1"

    async def job_async():
        """异步后台任务"""
        try:
            from app.works.tender.extract_v2_service import ExtractV2Service
            from app.services.db.postgres import _get_pool
            
            logger.info(f"[后台任务] 开始: extract_project_info project={project_id}")
            pool = _get_pool()
            extract_v2 = ExtractV2Service(pool, svc.llm)
            
            # 直接调用异步方法
            result = await extract_v2.extract_project_info_v2(
                project_id=project_id,
                model_id=req.model_id,
                run_id=run_id
            )
            
            # extract_project_info_v2 返回时状态为running(0.98)
            # 这里更新为最终的success状态
            dao.update_run(run_id, "success", progress=1.0, message="项目信息提取完成")
            logger.info(f"[后台任务] 完成: extract_project_info project={project_id}, stages={len([r for r in result.values() if isinstance(r, dict) and r])}")
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception(f"[后台任务] 失败: {e}")
            dao.update_run(run_id, "failed", message=f"提取失败: {str(e)}")

    if run_sync:
        # 同步执行 - 直接await
        await job_async()
        # 返回最新状态
        run = dao.get_run(run_id)
        return {
            "run_id": run_id,
            "status": run.get("status") if run else "unknown",
            "progress": run.get("progress") if run else 0,
            "message": run.get("message") if run else "",
        }
    else:
        # 异步执行 - 使用asyncio.create_task在当前事件循环中创建任务
        import asyncio
        asyncio.create_task(job_async())
        return {"run_id": run_id}


@router.get("/projects/{project_id}/project-info", response_model=Optional[ProjectInfoOut])
def get_project_info(project_id: str, request: Request):
    """获取项目信息"""
    dao = TenderDAO(_get_pool(request))
    row = dao.get_project_info(project_id)
    if not row:
        return None
    
    # 基础字段
    result = {
        "project_id": row["project_id"],
        "data_json": row.get("data_json") or {},
        "evidence_chunk_ids": row.get("evidence_chunk_ids_json") or [],
        "updated_at": row.get("updated_at"),
    }
    
    # 如果启用 EVIDENCE_SPANS_ENABLED，生成 evidence_spans
    flags = get_feature_flags()
    if flags.EVIDENCE_SPANS_ENABLED:
        chunk_ids = result["evidence_chunk_ids"]
        if chunk_ids:
            result["evidence_spans"] = chunks_to_span_refs(chunk_ids)
    
    return result


# ==================== 招标要求提取 ====================

@router.post("/projects/{project_id}/extract/risks")
def extract_risks(
    project_id: str,
    req: ExtractReq,
    request: Request,
    bg: BackgroundTasks,
    sync: int = 0,
    use_checklist: int = 1,  # ✅ 默认使用V2清单方式（V1已废弃）
    user=Depends(get_current_user_sync),
):
    """提取招标要求（V2清单方式）
    
    新流程：
    1. 提取 tender_requirements（调用 LLM + 标准清单）
    2. 前端通过 /risk-analysis 接口聚合展示
    
    Args:
        sync: 同步执行模式，1=同步返回结果，0=后台任务（默认）
        use_checklist: 是否使用标准清单方式，1=使用v2清单（默认），0=v1传统方式（已废弃）
    
    ✨ V2清单方式（P0+P1优化）：
        - 标准清单引导：覆盖95%+高频要求
        - 全文补充扫描：捕获遗漏的项目特定要求
        - 强制norm_key：100%覆盖率，便于精准比对
        - 完整性验证：自动检测并报告提取质量
    """
    dao = TenderDAO(_get_pool(request))
    run_id = dao.create_run(project_id, "extract_risks")
    
    # 根据use_checklist参数选择提示信息
    extract_method = "标准清单方式" if use_checklist == 1 else "传统方式"
    dao.update_run(run_id, "running", progress=0.01, message=f"正在提取招标要求（{extract_method}）...")
    
    # 在路由层面获取依赖，确保在后台任务中可用（与 extract_project_info 相同模式）
    pool = _get_pool(request)
    llm = _get_llm(request)  # 从 app.state.llm_orchestrator 获取
    owner_id = user.user_id if user else None
    
    # 检查是否同步执行
    run_sync = sync == 1 or request.headers.get("X-Run-Sync") == "1"

    def job():
        try:
            import asyncio
            from app.works.tender.extract_v2_service import ExtractV2Service
            
            # 创建 ExtractV2Service，传递 llm orchestrator（与 TenderService.extract_project_info 相同）
            extract_v2 = ExtractV2Service(pool, llm)
            
            # ✨ 根据use_checklist参数选择v1或v2
            if use_checklist == 1:
                logger.info(f"📋 Using checklist-based extraction (v2) for project={project_id}")
                
                # 调用 extract_requirements_v2（标准清单方式 + P1全文补充）
                result = asyncio.run(extract_v2.extract_requirements_v2(
                    project_id=project_id,
                    model_id=req.model_id,
                    checklist_template="engineering",  # 默认工程类模板
                    run_id=run_id
                ))
                
                req_count = result.get("count", 0)
                coverage = result.get("checklist_coverage", {})
                
                # 更新运行状态（包含覆盖率信息）
                dao.update_run(
                    run_id, 
                    "success", 
                    progress=1.0, 
                    message=f"成功提取 {req_count} 条招标要求（标准清单方式，覆盖率{coverage.get('coverage_rate', 0):.1%}）",
                    result_json={
                        "count": req_count,
                        "method": "checklist_v2",
                        "coverage": coverage
                    }
                )
                
                logger.info(
                    f"✅ Extract requirements (v2 checklist): project={project_id}, "
                    f"count={req_count}, coverage={coverage.get('coverage_rate', 0):.1%}"
                )
            else:
                # ❌ V1已废弃，强制使用V2
                logger.error(f"❌ V1提取方式已废弃，自动使用V2: project={project_id}")
                dao.update_run(run_id, "failed", message="V1已废弃，请使用use_checklist=1")
                raise ValueError("V1招标要求提取已废弃，请使用 use_checklist=1 参数")
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception(f"Extract requirements failed: {e}")
            dao.update_run(run_id, "failed", message=str(e))

    if run_sync:
        # 同步执行
        job()
        # 返回最新状态
        run = dao.get_run(run_id)
        return {
            "run_id": run_id,
            "status": run.get("status") if run else "unknown",
            "progress": run.get("progress") if run else 0,
            "message": run.get("message") if run else "",
        }
    else:
        # 异步执行
        bg.add_task(job)
        return {"run_id": run_id}


@router.get("/projects/{project_id}/risk-analysis")
def get_risk_analysis(project_id: str, request: Request):
    """
    获取风险分析聚合数据（基于 tender_requirements）
    
    返回两张表：
    1. must_reject_table: 废标项/关键硬性要求（is_hard=true）
    2. checklist_table: 注意事项/得分点（is_hard=false）
    
    每行包含：
    - 基础字段：dimension, req_type, requirement_text, allow_deviation, value_schema_json, evidence_chunk_ids
    - 派生字段：severity, consequence/category, suggestion
    """
    from app.works.tender.risk import RiskAnalysisService
    
    pool = _get_pool(request)
    service = RiskAnalysisService(pool)
    
    try:
        result = service.build_risk_analysis(project_id)
        return result.model_dump()
    except Exception as e:
        logger.error(f"Risk analysis failed for project {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Risk analysis failed: {str(e)}")


@router.get("/projects/{project_id}/requirements")
def get_requirements(project_id: str, request: Request):
    """
    获取招标要求基准条款库
    
    返回从招标文件中提取的结构化要求条款，用于标书审核
    """
    pool = _get_pool(request)
    
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        id,
                        requirement_id,
                        dimension,
                        req_type,
                        requirement_text,
                        is_hard,
                        allow_deviation,
                        value_schema_json,
                        evidence_chunk_ids,
                        eval_method,
                        must_reject,
                        expected_evidence_json,
                        rubric_json,
                        weight,
                        created_at
                    FROM tender_requirements
                    WHERE project_id = %s
                    ORDER BY created_at ASC
                """, (project_id,))
                
                rows = cur.fetchall()
                
                requirements = []
                for row in rows:
                    requirements.append({
                        "id": row['id'],
                        "requirement_id": row['requirement_id'],
                        "dimension": row['dimension'],
                        "req_type": row['req_type'],
                        "requirement_text": row['requirement_text'],
                        "is_hard": row['is_hard'],
                        "allow_deviation": row['allow_deviation'],
                        "value_schema_json": row['value_schema_json'],
                        "evidence_chunk_ids": row.get('evidence_chunk_ids') or [],
                        "eval_method": row.get('eval_method'),
                        "must_reject": row.get('must_reject', False),
                        "expected_evidence_json": row.get('expected_evidence_json'),
                        "rubric_json": row.get('rubric_json'),
                        "weight": row.get('weight'),
                        "created_at": row['created_at'].isoformat() if row.get('created_at') else None
                    })
                
                return {
                    "count": len(requirements),
                    "requirements": requirements
                }
    
    except Exception as e:
        logger.error(f"Failed to get requirements for project {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get requirements: {str(e)}")


# ==================== 目录生成 ====================

@router.post("/projects/{project_id}/directory/generate")
def generate_directory(
    project_id: str,
    req: ExtractReq,
    request: Request,
    bg: BackgroundTasks,
):
    """生成目录"""
    # 🔍 DEBUG
    debug_log = open("/app/router_debug.log", "a")
    debug_log.write(f"\n=== Router generate_directory START ===\n")
    debug_log.write(f"project_id: {project_id}\n")
    debug_log.write(f"model_id: {req.model_id}\n")
    debug_log.flush()
    
    dao = TenderDAO(_get_pool(request))
    run_id = dao.create_run(project_id, "generate_directory")
    debug_log.write(f"run_id: {run_id}\n")
    debug_log.flush()
    
    dao.update_run(run_id, "running", progress=0.01, message="running")
    svc = _svc(request)

    def job():
        debug_log.write(f"后台任务开始执行...\n")
        debug_log.flush()
        try:
            svc.generate_directory(project_id, req.model_id, run_id=run_id)
            debug_log.write(f"svc.generate_directory 执行完成\n")
            debug_log.close()
        except Exception as e:
            debug_log.write(f"svc.generate_directory 执行失败: {e}\n")
            debug_log.close()
            dao.update_run(run_id, "failed", message=str(e))

    bg.add_task(job)
    return {"run_id": run_id}


@router.get("/projects/{project_id}/directory")
def get_directory(project_id: str, request: Request):
    """获取目录（树形结构，带正文元信息）"""
    svc = _svc(request)
    
    # 获取扁平节点列表（带 bodyMeta）
    flat_nodes = svc.get_directory_with_body_meta(project_id)
    
    # 返回原始格式（兼容前端）
    return _serialize_directory_nodes(flat_nodes)


@router.get("/projects/{project_id}/directory/{node_id}/body")
def get_section_body(project_id: str, node_id: str, request: Request):
    """获取章节正文内容"""
    svc = _svc(request)
    content = svc.get_section_body_content(project_id, node_id)
    
    if not content:
        return {"source": "EMPTY", "contentHtml": "", "fragmentId": None}
    
    return content


@router.put("/projects/{project_id}/directory/{node_id}/body")
def update_section_body(project_id: str, node_id: str, body: Dict[str, Any], request: Request):
    """更新章节正文（用户编辑）"""
    svc = _svc(request)
    content_html = body.get("contentHtml", "")
    svc.update_section_body(project_id, node_id, content_html)
    
    return {"status": "success"}


@router.get("/projects/{project_id}/sections/load")
async def load_all_sections(
    project_id: str,
    request: Request,
):
    """
    加载项目的所有章节内容
    用于页面初始化时从数据库读取已保存的内容
    
    Returns:
        {"sections": {node_id: {content_html: "...", ...}}}
    """
    dao = TenderDAO(_get_pool(request))
    
    try:
        # 获取所有章节内容
        sections_dict = dao.get_all_section_bodies(project_id)
        logger.info(f"[sections/load] 加载了 {len(sections_dict)} 个章节")
        return {"sections": sections_dict}
    except Exception as e:
        logger.error(f"[sections/load] 加载失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"加载失败: {str(e)}")


class ApplyFormatTemplateReq(BaseModel):
    format_template_id: str


@router.post("/projects/{project_id}/directory/apply-format-template")
async def apply_format_template(
    project_id: str, 
    req: ApplyFormatTemplateReq, 
    request: Request,
    return_type: str = Query("json", description="返回类型: json（预览+下载链接）或 file（直接下载）")
):
    """
    自动套用格式模板到目录（生成DOCX文件）
    
    新流程（使用模板复制渲染器）：
    1. 记录 format_template_id 到目录节点
    2. 获取模板的 analysis_json（包含 roleMapping）
    3. 调用新的模板渲染器生成 DOCX
    4. 转换为 PDF（用于预览）
    5. 返回 JSON（preview_url + download_url）或 FileResponse（直接下载）
    """
    import os
    import uuid
    import json
    import tempfile
    import logging
    from pathlib import Path
    from fastapi.responses import FileResponse
    from urllib.parse import quote
    from app.services.export.export_service import ExportService
    
    logger = logging.getLogger(__name__)
    logger.info(f"自动套用格式: project={project_id}, template={req.format_template_id}, return_type={return_type}")
    
    try:
        svc = _svc(request)
        dao = TenderDAO(_get_pool(request))
        
        # 1. 记录模板ID到目录节点（保持原有逻辑）
        nodes = svc.apply_format_template_to_directory(project_id, req.format_template_id)
        
        # 2. 获取模板并校验
        template = dao.get_format_template(req.format_template_id)
        if not template:
            raise HTTPException(status_code=404, detail="格式模板不存在")
        
        template_path = template.get("template_storage_path")
        if not template_path or not os.path.exists(template_path):
            raise HTTPException(
                status_code=404,
                detail="模板文件不存在，请重新上传模板"
            )
        
        analysis_json = template.get("analysis_json")
        if not analysis_json:
            raise HTTPException(
                status_code=400,
                detail="模板未分析，请先在格式模板管理中分析模板或重新上传"
            )
        
        # 3. 检查目录是否为空
        outline_tree = dao.list_directory(project_id)
        if not outline_tree:
            raise HTTPException(status_code=400, detail="项目目录为空，请先生成目录")
        
        # 4. 使用 ExportService 导出项目为 DOCX（统一走旧版7步流程）
        output_dir = Path(tempfile.gettempdir()) / "template_renders"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        export_service = ExportService(dao)
        
        try:
            output_docx_path = await export_service.export_project_to_docx(
                project_id=project_id,
                format_template_id=req.format_template_id,
                include_toc=True,
                prefix_numbering=False,
                merge_semantic_summary=False,
                output_dir=str(output_dir),
                auto_generate_content=False
            )
            logger.info(f"✓ ExportService 导出完成: {output_docx_path}")
        except ValueError as ve:
            logger.error(f"ExportService 导出失败: {ve}")
            raise HTTPException(status_code=400, detail=f"模板渲染失败: {str(ve)}")
        except Exception as e:
            logger.error(f"ExportService 导出异常: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")
        
        # 5. 准备文件名
        project = dao.get_project(project_id)
        project_name = project.get("name", "投标文件") if project else "投标文件"
        display_name = f"{project_name}_套用格式_{uuid.uuid4().hex[:8]}.docx"
        encoded_filename = quote(display_name.encode('utf-8'))
        
        output_path = Path(output_docx_path)
        
        logger.info(f"✓ 套用格式完成: {output_path}")
        
        # 5. 根据 return_type 返回不同内容
        if return_type == "file":
            # 兼容老逻辑：直接下载文件
            return FileResponse(
                output_path,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                filename=display_name,
                headers={
                    "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
                }
            )
        else:
            # 新逻辑：转换为 PDF 用于预览，返回 JSON
            from app.services.office.convert import docx_to_pdf
            
            try:
                pdf_path = docx_to_pdf(str(output_path))
                logger.info(f"✓ DOCX 转 PDF 完成: {pdf_path}")
            except Exception as e:
                logger.warning(f"DOCX 转 PDF 失败: {e}，预览将不可用")
                pdf_path = None
            
            # 构建预览和下载 URL
            preview_url = None
            if pdf_path:
                preview_url = f"/api/apps/tender/files/temp?path={quote(str(pdf_path))}&format=pdf"
            
            download_url = f"/api/apps/tender/files/temp?path={quote(str(output_path))}&format=docx"
            
            # 刷新目录（获取最新的目录和正文元数据）
            nodes = svc.get_directory_with_body_meta(project_id)
            
            return {
                "ok": True,
                "project_id": project_id,
                "preview_pdf_url": preview_url,
                "download_docx_url": download_url,
                "nodes": nodes,
            }
    
    except HTTPException:
        raise
    except ValueError as ve:
        # ValueError 通常表示业务逻辑错误（如目录为空、模板未分析等）
        error_detail = str(ve)
        logger.error(f"[APPLY_FMT_FAIL] 业务校验失败: {error_detail}")
        
        # 根据错误信息提供更友好的提示
        if "目录" in error_detail and "为空" in error_detail:
            detail = f"模板渲染失败：{error_detail}。请先生成项目目录。"
        elif "roleMapping" in error_detail or "role_mapping" in error_detail:
            detail = f"模板渲染失败：{error_detail}。请在格式模板管理中重新分析模板。"
        elif "锚点" in error_detail:
            detail = f"模板渲染失败：{error_detail}。模板格式可能不符合要求。"
        else:
            detail = f"模板渲染失败：{error_detail}"
        
        raise HTTPException(status_code=400, detail=detail)
    except Exception as e:
        logger.error(f"套用格式失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"套用格式失败: {str(e)}")


# ==================== 自定义规则（简化输入） ====================

class SimpleRuleCreateReq(BaseModel):
    """简化规则创建请求"""
    rule_text: str = Field(..., description="规则文本，支持多条规则（用空行分隔）")
    pack_name: Optional[str] = Field(None, description="规则包名称（可选）")

@router.post("/projects/{project_id}/rules/create-from-text")
def create_rules_from_text_api(
    project_id: str,
    req: SimpleRuleCreateReq,
    request: Request,
    user=Depends(get_current_user_sync),
):
    """
    从文本创建自定义规则（简化接口）
    
    用户只需输入规则文本，系统自动解析并创建规则包。
    
    支持格式：
    1. 结构化格式：
       ```
       维度：资格条件
       规则：投标人注册资本不得低于1000万元
       类型：硬性
       ```
    
    2. 自由文本格式：
       ```
       投标人注册资本不得低于1000万元（硬性要求）
       ```
    
    返回：
        {
            "pack_id": "规则包ID",
            "pack_name": "规则包名称",
            "rules_count": 3,
            "rules": [...]
        }
    """
    from app.works.tender.simple_rule_parser import create_rules_from_text
    from app.services.dao.tender_dao import TenderDAO
    
    try:
        dao = TenderDAO()
        result = create_rules_from_text(
            pool=dao.pool,
            project_id=project_id,
            rule_text=req.rule_text,
            pack_name=req.pack_name,
            owner_id=user.get("id"),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"创建规则失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建规则失败: {str(e)}")


# ==================== 审核 ====================

@router.post("/projects/{project_id}/audit/unified")
async def run_unified_audit(
    project_id: str,
    bidder_name: str,
    request: Request,
    bg: BackgroundTasks,
    sync: int = 0,
    custom_rule_pack_ids: Optional[str] = Query(None, description="自定义规则包ID列表（逗号分隔）"),
    user=Depends(get_current_user_sync),
):
    """
    一体化审核（提取响应 + 审核判断一次完成）
    
    特性：
    - 直接从招标要求开始
    - LLM一次调用完成响应提取和审核判断
    - 保存响应数据（供其他用途）
    - 保存审核结果（供前端展示）
    - 返回完整审核报告
    - ✨ 支持自定义规则包集成
    
    Args:
        bidder_name: 投标人名称
        sync: 同步执行模式，1=同步返回结果，0=后台任务（默认）
        custom_rule_pack_ids: 自定义规则包ID列表（逗号分隔，可选）
    """
    dao = TenderDAO(_get_pool(request))
    run_id = dao.create_run(project_id, "unified_audit")
    
    # 解析规则包ID
    rule_pack_ids_list = []
    if custom_rule_pack_ids:
        rule_pack_ids_list = [pid.strip() for pid in custom_rule_pack_ids.split(',') if pid.strip()]
    
    mode_msg = f"（启用{len(rule_pack_ids_list)}个自定义规则包）" if rule_pack_ids_list else "（基础评估模式）"
    dao.update_run(run_id, "running", progress=0.01, message=f"开始一体化审核：{bidder_name} {mode_msg}")
    
    # 检查是否同步执行
    run_sync = sync == 1 or request.headers.get("X-Run-Sync") == "1"
    
    async def job():
        from app.platform.retrieval.facade import RetrievalFacade
        from app.works.tender.unified_audit_service import UnifiedAuditService
        
        try:
            pool = _get_pool(request)
            llm = getattr(request.app.state, 'llm_orchestrator', None)
            retriever = RetrievalFacade(pool)
            
            service = UnifiedAuditService(
                pool=pool,
                llm_orchestrator=llm,
                retriever=retriever
            )
            
            # ✨ 执行一体化审核（传入自定义规则包ID）
            result = await service.run_unified_audit(
                project_id=project_id,
                bidder_name=bidder_name,
                model_id=None,
                run_id=run_id,
                custom_rule_pack_ids=rule_pack_ids_list  # 新增参数
            )
            
            # 更新运行状态
            stats = result.get("statistics", {})
            dao.update_run(
                run_id,
                "success",
                progress=1.0,
                message=f"审核完成：{stats.get('pass_count', 0)}条通过，{stats.get('fail_count', 0)}条不合规",
                result_json=result
            )
            return result
        except ValueError as e:
            # 业务逻辑错误（如：未找到招标要求）
            error_msg = str(e)
            logger.warning(f"Unified audit validation error: {error_msg}")
            if "未找到招标要求" in error_msg or "招标要求" in error_msg:
                friendly_msg = "未找到招标要求，请先在【② 要求】标签页提取招标要求"
                dao.update_run(run_id, "failed", message=friendly_msg)
            else:
                dao.update_run(run_id, "failed", message=error_msg)
            raise
        except Exception as e:
            logger.exception(f"Unified audit failed: {e}")
            dao.update_run(run_id, "failed", message=str(e))
            raise
    
    if run_sync:
        # 同步执行
        try:
            result = await job()
            return {
                "run_id": run_id,
                "status": "success",
                "result": result
            }
        except ValueError as e:
            # 业务逻辑错误（如：未找到招标要求）
            error_msg = str(e)
            if "未找到招标要求" in error_msg or "招标要求" in error_msg:
                raise HTTPException(
                    status_code=400, 
                    detail="请先在【② 要求】标签页提取招标要求，然后再进行审核"
                )
            raise HTTPException(status_code=400, detail=error_msg)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # 异步执行
        bg.add_task(lambda: asyncio.run(job()))
        return {"run_id": run_id, "bidder_name": bidder_name, "status": "running"}


@router.post("/projects/{project_id}/review/run")
def run_review(
    project_id: str,
    req: ReviewRunReq,
    request: Request,
    bg: BackgroundTasks,
    sync: int = 0,
    user=Depends(get_current_user_sync),
):
    """
    运行审核（招标规则 + 自定义规则文件叠加）
    
    Args:
        req.custom_rule_asset_ids: 自定义规则文件资产ID列表（直接叠加原文）
        req.custom_rule_pack_ids: 自定义规则包ID列表（应用规则包中的规则）
        req.bidder_name: 投标人名称（选择投标人）
        req.bid_asset_ids: 投标资产ID列表（精确指定文件）
        sync: 同步执行模式，1=同步返回结果，0=后台任务（默认）
    """
    dao = TenderDAO(_get_pool(request))
    run_id = dao.create_run(project_id, "review")
    dao.update_run(run_id, "running", progress=0.01, message="running")
    svc = _svc(request)
    owner_id = user.user_id if user else None
    
    # 检查是否同步执行
    run_sync = sync == 1 or request.headers.get("X-Run-Sync") == "1"

    def job():
        try:
            svc.run_review(
                project_id,
                req.model_id,
                req.custom_rule_asset_ids,
                req.bidder_name,
                req.bid_asset_ids,
                custom_rule_pack_ids=req.custom_rule_pack_ids,
                use_llm_semantic=req.use_llm_semantic,
                run_id=run_id,
                owner_id=owner_id,
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception(f"Review failed: {e}")
            dao.update_run(run_id, "failed", message=str(e))

    if run_sync:
        # 同步执行
        job()
        # 返回最新状态
        run = dao.get_run(run_id)
        return {
            "run_id": run_id,
            "status": run.get("status") if run else "unknown",
            "progress": run.get("progress") if run else 0,
            "message": run.get("message") if run else "",
        }
    else:
        # 异步执行
        bg.add_task(job)
        return {"run_id": run_id}


@router.get("/projects/{project_id}/review", response_model=List[ReviewItemOut])
def get_review(
    project_id: str, 
    request: Request,
    bidder_name: Optional[str] = None
):
    """获取审核结果（V3流水线）
    
    Args:
        bidder_name: 投标人名称（可选，如果提供则只返回该投标人的审核结果）
    """
    dao = TenderDAO(_get_pool(request))
    rows = dao.list_review_items(project_id, bidder_name=bidder_name)
    flags = get_feature_flags()
    
    out = []
    # 从 tender_review_items 读取 V3 审核结果
    for r in rows:
        # 转换UUID为字符串
        matched_response_id = r.get("matched_response_id")
        if matched_response_id is not None:
            matched_response_id = str(matched_response_id)
        
        # 规范化状态：数据库中是小写（pass/fail/pending/missing），前端需要大写
        db_status = r.get("status") or r.get("result") or "pending"
        normalized_status = db_status.upper() if db_status else "PENDING"
        # 特殊处理：missing → WARN（前端没有MISSING状态）
        if normalized_status == "MISSING":
            normalized_status = "WARN"
        
        review_item = {
            "id": r["id"],
            "project_id": r["project_id"],
            "source": "v3",  # V3流水线
            "dimension": r.get("dimension") or "其他",
            "requirement_text": r.get("requirement_text") or "",
            "response_text": r.get("response_text") or "",
            "result": normalized_status.lower(),  # result字段保持小写兼容性
            "remark": r.get("remark") or "",
            "rigid": bool(r.get("rigid", False)),
            "rule_id": None,
            "evaluator": r.get("evaluator"),  # V3新增字段
            "status": normalized_status,  # V3新增字段：规范化为大写
            "requirement_id": r.get("requirement_id"),  # V3新增字段
            "matched_response_id": matched_response_id,  # V3新增字段（UUID转字符串）
            "tender_evidence_chunk_ids": r.get("tender_evidence_chunk_ids") or [],
            "bid_evidence_chunk_ids": r.get("bid_evidence_chunk_ids") or [],
            "evidence_json": r.get("evidence_json"),  # V3证据结构
            "rule_trace_json": r.get("rule_trace_json"),  # V3规则追踪
            "computed_trace_json": r.get("computed_trace_json"),  # V3计算追踪
        }
        
        # 如果启用 EVIDENCE_SPANS_ENABLED，生成 evidence_spans
        if flags.EVIDENCE_SPANS_ENABLED:
            tender_chunk_ids = review_item["tender_evidence_chunk_ids"]
            bid_chunk_ids = review_item["bid_evidence_chunk_ids"]
            
            if tender_chunk_ids:
                review_item["tender_evidence_spans"] = chunks_to_span_refs(tender_chunk_ids)
            if bid_chunk_ids:
                review_item["bid_evidence_spans"] = chunks_to_span_refs(bid_chunk_ids)
        
        out.append(review_item)
    
    return out


# ==================== AI生成全文 ====================

class AnalyzeIntentReq(BaseModel):
    """AI意图识别请求"""
    user_input: str = Field(..., description="用户输入的自然语言")
    conversation_history: List[Dict[str, str]] = Field(default_factory=list, description="对话历史")
    directory_structure: List[Dict[str, Any]] = Field(..., description="当前文档的章节结构")


class AnalyzeIntentRes(BaseModel):
    """AI意图识别响应"""
    intent_type: str = Field(..., description="意图类型：generate/modify/optimize/global")
    target_node_ids: List[str] = Field(..., description="目标章节ID列表")
    action_description: str = Field(..., description="动作描述")
    requirements: str = Field(..., description="提炼的用户需求")
    confidence: float = Field(..., description="识别置信度 0-1")


@router.post("/projects/{project_id}/ai-assistant/analyze-intent", response_model=AnalyzeIntentRes)
async def analyze_user_intent(
    project_id: str,
    req: AnalyzeIntentReq,
    request: Request,
):
    """
    AI意图识别 - 理解用户想修改哪些章节、如何修改
    
    意图类型：
    - generate: 生成新内容
    - modify: 修改现有内容
    - optimize: 优化/润色
    - global: 全局修改（多个章节）
    """
    llm = _get_llm(request)
    
    # 构建章节信息供AI理解
    sections_info = "\n".join([
        f"- [{node.get('id')}] {node.get('orderNo', '')} {node.get('title', '')}"
        for node in req.directory_structure
    ])
    
    # 构建对话历史
    history_text = ""
    if req.conversation_history:
        history_text = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in req.conversation_history[-5:]  # 只取最近5轮
        ])
    
    # 意图识别prompt
    intent_prompt = f"""你是一个文档编辑AI助手。请分析用户的意图，理解他们想修改哪些章节、如何修改。

【当前文档章节结构】
{sections_info}

{f"【最近对话历史】{history_text}" if history_text else ""}

【用户输入】
{req.user_input}

请以JSON格式返回分析结果：
{{
    "intent_type": "generate|modify|optimize|global",
    "target_node_ids": ["章节ID列表"],
    "action_description": "简短描述要做什么",
    "requirements": "提炼的具体需求（传给生成API）",
    "confidence": 0.0-1.0
}}

判断规则：
1. 如果提到"第X章"、章节标题、或章节编号 → 提取对应的node_id
2. 如果说"这里"、"上面"、"刚才" → 结合对话历史判断
3. 如果说"整个文档"、"所有" → intent_type=global，返回多个node_id
4. 如果说"扩写"、"增加" → intent_type=generate
5. 如果说"修改"、"改成" → intent_type=modify
6. 如果说"优化"、"润色" → intent_type=optimize

只返回JSON，不要其他文字。"""

    try:
        # 调用LLM分析意图
        messages = [{"role": "user", "content": intent_prompt}]
        response = await llm.achat(messages=messages, model_id=None)
        
        # 提取文本内容
        if isinstance(response, dict) and "choices" in response:
            result_text = response["choices"][0]["message"]["content"].strip()
        elif isinstance(response, str):
            result_text = response.strip()
        else:
            result_text = str(response).strip()
        
        # 尝试提取JSON（去掉可能的markdown代码块标记）
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
        
        import json
        result = json.loads(result_text)
        
        logger.info(f"[意图识别] 用户输入: {req.user_input[:50]}...")
        logger.info(f"[意图识别] 识别结果: {result}")
        
        return AnalyzeIntentRes(**result)
        
    except Exception as e:
        logger.error(f"[意图识别] 失败: {e}", exc_info=True)
        # 返回默认结果（识别失败，让用户重新描述）
        return AnalyzeIntentRes(
            intent_type="unknown",
            target_node_ids=[],
            action_description="无法理解意图",
            requirements=req.user_input,
            confidence=0.0
        )


class GenerateSectionContentReq(BaseModel):
    """生成单个章节内容请求"""
    title: str = Field(..., description="章节标题")
    level: int = Field(..., description="章节层级")
    node_id: Optional[str] = Field(None, description="节点ID（用于自动保存）")
    requirements: Optional[str] = Field(None, description="用户自定义要求")
    original_content: Optional[str] = Field(None, description="原始内容（用于对比）")


@router.post("/projects/{project_id}/sections/generate")
async def generate_section_content(
    project_id: str,
    req: GenerateSectionContentReq,
    request: Request,
    model_id: Optional[str] = None,
):
    """
    生成单个章节的内容
    - 根据章节标题和层级生成内容
    - 可选：传入用户自定义要求
    - ✅ 新增：自动保存到数据库（如果提供node_id）
    """
    svc = _svc(request)
    dao = TenderDAO(_get_pool(request))
    
    # 构建项目上下文
    project = dao.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project_context = await svc._build_tender_project_context(project_id)
    
    # 如果有用户要求，添加到上下文中
    if req.requirements:
        project_context += f"\n\n【用户自定义要求】\n{req.requirements}"
    
    # 生成内容
    result = await svc._generate_section_content(
        project_id=project_id,
        title=req.title,
        level=req.level,
        project_context=project_context,
        requirements=req.requirements,  # ✅ 传递用户要求
        model_id=model_id,
    )
    
    content = result.get("content", "")
    
    # ✅ 新增：自动保存到数据库（如果提供了node_id）
    if req.node_id and content:
        try:
            svc.update_section_body(project_id, req.node_id, content)
            logger.info(f"[sections/generate] 已自动保存到数据库: node_id={req.node_id}")
        except Exception as e:
            logger.error(f"[sections/generate] 保存失败: {e}", exc_info=True)
            # 保存失败不影响返回生成的内容
    
    return {"content": content}


@router.get("/projects/{project_id}/directory/{node_id}/template")
async def get_node_template(
    project_id: str,
    node_id: str,
    request: Request,
):
    """
    获取章节的模板/示例原文
    
    Returns:
        {
            "has_template": bool,
            "template_html": str,
            "template_type": str,  # "table", "example", "format"
            "source_chunks": [...]
        }
    """
    dao = TenderDAO(_get_pool(request))
    
    # 1. 获取节点信息
    nodes = dao.list_directory(project_id)
    node = next((n for n in nodes if n.get("id") == node_id), None)
    
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    # 2. 检查meta_json中是否有template_chunk_ids
    meta_json = node.get("meta_json") or {}
    template_chunk_ids = meta_json.get("template_chunk_ids") or []
    
    if not template_chunk_ids:
        return {
            "has_template": False,
            "template_html": "",
            "template_type": "",
            "source_chunks": []
        }
    
    # 3. 检索模板内容
    from app.services.db.postgres import _get_pool
    from app.platform.retrieval.facade import RetrievalFacade
    
    pool = _get_pool(request)
    retrieval = RetrievalFacade(pool)
    
    try:
        # 通过chunk_ids直接检索
        chunks = await retrieval.retrieve_by_chunk_ids(
            chunk_ids=template_chunk_ids,
            project_id=project_id
        )
        
        if not chunks:
            return {
                "has_template": False,
                "template_html": "",
                "template_type": "",
                "source_chunks": []
            }
        
        # 4. 合并chunk文本并转换为HTML
        template_text = "\n\n".join([c.text for c in chunks])
        
        # 简单的文本到HTML转换（保留换行和格式）
        import html
        template_html = html.escape(template_text).replace("\n", "<br>")
        
        # 判断模板类型
        template_type = "example"
        if "表" in template_text or "|" in template_text:
            template_type = "table"
        elif "格式" in template_text or "模板" in template_text:
            template_type = "format"
        
        return {
            "has_template": True,
            "template_html": template_html,
            "template_type": template_type,
            "source_chunks": [
                {
                    "chunk_id": c.chunk_id,
                    "text": c.text[:200] + "..." if len(c.text) > 200 else c.text
                }
                for c in chunks
            ]
        }
        
    except Exception as e:
        logger.error(f"获取模板失败: {e}", exc_info=True)
        return {
            "has_template": False,
            "template_html": "",
            "template_type": "",
            "source_chunks": [],
            "error": str(e)
        }


@router.post("/projects/{project_id}/generate-full-content", response_model=RunOut)
async def generate_full_content(
    project_id: str,
    request: Request,
    bg: BackgroundTasks,
    sync: int = Query(0, description="是否同步执行：0=异步，1=同步"),
    model_id: Optional[str] = None,
):
    """
    AI生成标书全文
    - 基于已生成的目录，为所有空章节生成内容
    - 支持同步/异步执行
    """
    svc = _svc(request)
    dao = TenderDAO(_get_pool(request))
    
    # 创建 run 记录
    run_id = dao.create_run(project_id, kind="generate_full_content")
    
    if sync == 1:
        # 同步执行
        await svc.generate_full_content(project_id, model_id, run_id)
        run = dao.get_run(run_id)
        return run
    else:
        # 异步执行
        import asyncio
        asyncio.create_task(svc.generate_full_content(project_id, model_id, run_id))
        run = dao.get_run(run_id)
        return run


# ==================== 文档生成 ====================


class ExportDocxReq(BaseModel):
    format_template_id: Optional[str] = None


@router.get("/projects/{project_id}/export/docx")
def export_docx_get(
    project_id: str,
    request: Request,
    format_template_id: Optional[str] = None,
):
    """
    导出 Word 文档（推荐接口）
    - 支持 format_template_id（优先）
    - 若不传 format_template_id，则尝试从目录节点 meta_json 推断已套用模板
    """
    svc = _svc(request)
    data = svc.generate_docx_v2(project_id=project_id, format_template_id=format_template_id)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.post("/projects/{project_id}/export/docx")
def export_docx_post(project_id: str, req: ExportDocxReq, request: Request):
    """
    导出 Word 文档（POST 兼容）
    body: { "format_template_id": "tpl_..." }
    """
    svc = _svc(request)
    data = svc.generate_docx_v2(project_id=project_id, format_template_id=req.format_template_id)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


# ==================== Chunk 查询（证据回溯） ====================

@router.post("/chunks/lookup")
def chunks_lookup(req: ChunkLookupReq, request: Request):
    """查询 chunks（证据回溯）"""
    svc = _svc(request)
    rows = svc.lookup_chunks(req.chunk_ids)
    # 输出给前端 SourcePanel
    return [
        {
            "chunk_id": r["chunk_id"],
            "doc_id": r["doc_id"],
            "title": r.get("title") or "",
            "url": r.get("url") or "",
            "position": r.get("position") or 0,
            "content": r.get("content") or "",
        }
        for r in rows
    ]


# ==================== 格式模板管理 ====================

class FormatTemplateCreateReq(BaseModel):
    """创建格式模板请求"""
    name: str
    description: Optional[str] = None
    is_public: bool = False


class FormatTemplateOut(BaseModel):
    """格式模板输出"""
    id: str
    name: str
    description: Optional[str] = None
    is_public: bool
    owner_id: Optional[str] = None
    template_sha256: Optional[str] = None
    template_spec_version: Optional[str] = None
    template_spec_analyzed_at: Optional[str] = None
    created_at: str
    updated_at: str


# ==================== 格式模板 Work 辅助函数 ====================

def _get_format_templates_work(request: Request) -> Any:
    """获取格式模板 Work 实例"""
    from app.works.tender.format_templates import FormatTemplatesWork
    
    pool = _get_pool(request)
    llm_orchestrator = getattr(request.app.state, 'llm_orchestrator', None)
    
    return FormatTemplatesWork(
        pool=pool,
        llm_orchestrator=llm_orchestrator,
        storage_dir="storage/templates"
    )


# ==================== 格式模板 CRUD API ====================

@router.get("/format-templates", response_model=List[FormatTemplateOut])
def list_format_templates(
    request: Request,
    user=Depends(get_current_user_sync)
):
    """
    列出格式模板
    
    返回当前用户的模板和所有公开模板
    """
    work = _get_format_templates_work(request)
    templates = work.list_templates(owner_id=user.user_id)
    return templates


async def create_format_template(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    is_public: bool = Form(False),
    file: UploadFile = File(...),
    model_id: Optional[str] = Form(None),
    request: Request = None,
    user=Depends(get_current_user_sync)
):
    """
    创建格式模板（使用 Work 层）
    
    流程：
    1. 样式解析（必须）- 识别标题和正文样式
    2. Blocks提取（必须）- 提取文档结构
    3. LLM分析（可选）- 仅在传入 model_id 时执行
    
    Args:
        name: 模板名称
        description: 模板描述
        is_public: 是否公开
        file: Word 文档文件
        model_id: LLM模型ID（可选）
    """
    import logging
    
    logger = logging.getLogger(__name__)
    
    if not file.filename.endswith((".docx", ".doc")):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")
    
    # 读取文件
    docx_bytes = await file.read()
    
    # 调用 Work 层
    work = _get_format_templates_work(request)
    
    try:
        result = await work.create_template(
            name=name,
            docx_bytes=docx_bytes,
            filename=file.filename,
            owner_id=user.user_id,
            description=description,
            is_public=is_public,
            model_id=model_id
        )
        
        logger.info(f"模板创建成功: template_id={result.template_id}, status={result.analysis_status}")
        
        # 返回完整的模板对象
        template = work.get_template(result.template_id)
        return template
        
    except Exception as e:
        logger.error(f"创建格式模板失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")


@router.get("/format-templates/{template_id}", response_model=FormatTemplateOut)
def get_format_template(
    template_id: str,
    request: Request,
    user=Depends(get_current_user_sync)
):
    """
    获取格式模板详情
    """
    work = _get_format_templates_work(request)
    template = work.get_template(template_id)
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # 权限检查
    if template.owner_id != user.user_id and not template.is_public:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    return template


class FormatTemplateUpdateReq(BaseModel):
    """更新格式模板请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None


@router.put("/format-templates/{template_id}", response_model=FormatTemplateOut)
def update_format_template(
    template_id: str,
    req: FormatTemplateUpdateReq,
    request: Request,
    user=Depends(get_current_user_sync)
):
    """
    更新格式模板元数据
    """
    work = _get_format_templates_work(request)
    
    # 权限检查
    template = work.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.owner_id != user.user_id:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    try:
        from app.works.tender.format_templates.types import FormatTemplateUpdateReq as WorkUpdateReq
        work_req = WorkUpdateReq(
            name=req.name,
            description=req.description,
            is_public=req.is_public
        )
        updated = work.update_template(template_id, work_req)
        return updated
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/format-templates/{template_id}/spec")
def get_format_template_spec(template_id: str, request: Request):
    """
    获取格式模板的样式规格（新版，基于 analysis_json）
    
    Returns:
        包含 style_hints 的 spec 对象（用于前端样式渲染）
    """
    import json
    
    dao = TenderDAO(_get_pool(request))
    template = dao.get_format_template(template_id)
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # 从 analysis_json 构建 style_hints
    analysis_json = template.get("analysis_json")
    if not analysis_json:
        # 如果没有分析结果，返回默认样式
        return {
            "template_name": template.get("name", "未分析模板"),
            "version": "2.0",
            "style_hints": {
                "page_background": "#ffffff",
                "font_family": "SimSun, serif",
                "font_size": "14px",
                "line_height": "1.6",
                "toc_indent_1": "0px",
                "toc_indent_2": "20px",
                "toc_indent_3": "40px",
                "toc_indent_4": "60px",
                "toc_indent_5": "80px",
            },
            "merge_policy": {
                "template_defines_structure": False,
                "keep_ai_content": True
            }
        }
    
    if isinstance(analysis_json, str):
        analysis_json = json.loads(analysis_json)
    
    role_mapping = analysis_json.get("roleMapping", {})
    
    # 构建 style_hints
    style_hints = {
        "page_background": "#ffffff",
        "font_family": "SimSun, serif",
        "font_size": "14px",
        "line_height": "1.6",
        "toc_indent_1": "0px",
        "toc_indent_2": "20px",
        "toc_indent_3": "40px",
        "toc_indent_4": "60px",
        "toc_indent_5": "80px",
    }
    
    # 从 role_mapping 映射样式名称
    for i in range(1, 6):
        key = f"h{i}"
        if key in role_mapping:
            style_hints[f"heading{i}"] = role_mapping[key]
    
    if "body" in role_mapping:
        style_hints["body"] = role_mapping["body"]
    
    return {
        "template_name": template.get("name", ""),
        "version": "2.0",
        "style_hints": style_hints,
        "role_mapping": role_mapping,  # 新增：提供完整的角色映射
        "merge_policy": {
            "template_defines_structure": False,
            "keep_ai_content": True
        }
    }


@router.get("/format-templates/{template_id}/extract")
async def get_format_template_extract(
    template_id: str,
    file: UploadFile = File(...),
    request: Request = None
):
    """
    获取格式模板的解析结构（blocks + exclude 信息）
    
    Args:
        template_id: 模板ID
        file: Word 文档文件
        
    Returns:
        解析结构详情
    """
    if not file.filename.endswith((".docx", ".doc")):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")
    
    docx_bytes = await file.read()
    svc = _svc(request)
    
    try:
        return svc.get_format_template_extract(template_id, docx_bytes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract template: {str(e)}")


@router.get("/format-templates/{template_id}/analysis-summary")
def get_format_template_analysis_summary(template_id: str, request: Request):
    """
    获取格式模板分析摘要
    
    Returns:
        分析摘要信息
    """
    svc = _svc(request)
    summary = svc.get_format_template_analysis_summary(template_id)
    return summary


@router.post("/format-templates/{template_id}/analyze")
async def reanalyze_format_template(
    template_id: str,
    force: bool = True,
    file: UploadFile = File(...),
    request: Request = None
):
    """
    强制重新分析格式模板或替换文件
    
    Args:
        template_id: 模板 ID
        force: 是否强制（忽略缓存）
        file: Word 文档文件
        
    Returns:
        更新后的模板记录
    """
    if not file.filename.endswith((".docx", ".doc")):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")
    
    # 读取文件内容
    docx_bytes = await file.read()
    
    # 调用服务层
    svc = _svc(request)
    template = await svc.reanalyze_format_template(template_id, docx_bytes, force=force)
    
    return template


@router.put("/format-templates/{template_id}/file")
async def replace_format_template_file(
    template_id: str,
    file: UploadFile = File(...),
    request: Request = None,
    user=Depends(get_current_user_sync)
):
    """
    替换格式模板文件并重新分析
    
    Args:
        template_id: 模板ID
        file: 新的 Word 文档文件
        
    Returns:
        更新后的模板记录
    """
    if not file.filename.endswith((".docx", ".doc")):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")
    
    # 读取文件内容
    docx_bytes = await file.read()
    
    # 调用服务层
    svc = _svc(request)
    template = await svc.reanalyze_format_template(template_id, docx_bytes)
    
    return template


@router.delete("/format-templates/{template_id}", status_code=204)
def delete_format_template(template_id: str, request: Request, user=Depends(get_current_user_sync)):
    """删除格式模板"""
    dao = TenderDAO(_get_pool(request))
    
    # 检查权限
    template = dao.get_format_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    if template["owner_id"] != user.user_id and not template["is_public"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    dao.delete_format_template(template_id)
    return None


@router.get("/format-templates/{template_id}/file")
def download_format_template_file(template_id: str, request: Request, user=Depends(get_current_user_sync)):
    """下载模板原始 docx 文件（用于前端下载/调试）"""
    dao = TenderDAO(_get_pool(request))
    tpl = dao.get_format_template(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if tpl["owner_id"] != user.user_id and not tpl["is_public"]:
        raise HTTPException(status_code=403, detail="Permission denied")

    path = str((tpl.get("template_storage_path") or "")).strip()
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Template file not found on disk")

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{tpl.get('name') or template_id}.docx",
    )


@router.post("/format-templates/{template_id}/parse")
def parse_format_template(
    template_id: str,
    request: Request,
    force: bool = Query(True),
    user=Depends(get_current_user_sync),
):
    """触发“确定性模板解析”（header/footer 图片 + section + heading 样式摘要）"""
    dao = TenderDAO(_get_pool(request))
    tpl = dao.get_format_template(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if tpl["owner_id"] != user.user_id and not tpl["is_public"]:
        raise HTTPException(status_code=403, detail="Permission denied")

    svc = _svc(request)
    return svc.parse_format_template(template_id, force=force)


@router.get("/format-templates/{template_id}/parse-summary")
def get_format_template_parse_summary(template_id: str, request: Request, user=Depends(get_current_user_sync)):
    """获取确定性解析摘要（parse_status + headingLevels + variants + header/footer 数量等）"""
    dao = TenderDAO(_get_pool(request))
    tpl = dao.get_format_template(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if tpl["owner_id"] != user.user_id and not tpl["is_public"]:
        raise HTTPException(status_code=403, detail="Permission denied")

    svc = _svc(request)
    try:
        return svc.get_format_template_parse_summary(template_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/format-templates/{template_id}/preview")
def get_format_template_preview(
    template_id: str,
    request: Request,
    format: str = Query("pdf", pattern="^(pdf|docx)$"),
    user=Depends(get_current_user_sync),
):
    """
    生成并返回“示范预览文档”
    - 优先 pdf（更适合网页 iframe）
    - 若 pdf 不可用则返回 docx
    """
    dao = TenderDAO(_get_pool(request))
    tpl = dao.get_format_template(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if tpl["owner_id"] != user.user_id and not tpl["is_public"]:
        raise HTTPException(status_code=403, detail="Permission denied")

    svc = _svc(request)
    info = svc.generate_format_template_preview(template_id, fmt=format)
    path = str(info.get("path") or "")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=500, detail="Preview file generation failed")

    fmt = str(info.get("format") or format).lower()
    if fmt == "pdf":
        headers = {"Content-Disposition": f'inline; filename="{template_id}.pdf"'}
        return FileResponse(path, media_type="application/pdf", headers=headers)

    headers = {"Content-Disposition": f'inline; filename="{template_id}.docx"'}
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )


# ==================== 语义目录生成 ====================

class SemanticOutlineGenerateReq(BaseModel):
    """语义目录生成请求"""
    mode: str = "FAST"  # FAST or FULL
    max_depth: int = 5



# ==================== 投标文件格式/样表抽取 ====================

class TemplateExtractRequest(BaseModel):
    """模板抽取请求"""
    mode: str = "NORMAL"  # NORMAL or ENHANCED


@router.post("/projects/{project_id}/templates/extract")
def extract_bid_templates(
    project_id: str,
    req: TemplateExtractRequest,
    request: Request,
    user=Depends(get_current_user_sync),
):
    """
    从招标书中抽取投标文件格式/样表/范本
    
    工作流：
    1. 候选召回（规则召回，不依赖标题样式）
    2. LLM分析（只负责：isTemplate、kind、边界）
    3. 边界细化（工程规则：终止规则、防吞章/防切短）
    4. 覆盖率guard（避免"只抽到几条"，自动增强重试）
    
    Returns:
        {
            "success": bool,
            "message": str,
            "result": {
                "status": "SUCCESS|NOT_FOUND|NEED_OCR|NEED_CONFIRM|LOW_COVERAGE",
                "templates": [...],  # 抽取的范本列表
                "evidences": [...],  # 证据列表（可解释）
                "diagnostics": {...} # 诊断信息
            }
        }
    """
    from app.schemas.template_extract import DocumentBlock
    from app.services.template_extract import TemplateExtractOrchestrator
    
    # 权限检查
    dao = TenderDAO(_get_pool(request))
    project = dao.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # 获取招标书的blocks（需要你们提供接口）
    # 这里假设你们有类似的方法，需要适配
    try:
        # TODO: 适配你们的block加载逻辑
        # 示例：从kb_chunks或其他地方加载blocks
        kb_id = project["kb_id"]
        from app.services import kb_service
        docs = kb_service.list_documents(kb_id)
        
        if not docs:
            raise HTTPException(status_code=400, detail="No documents found in project")
        
        # 简化：从chunks构建blocks（需要根据你们的实际数据结构调整）
        doc_ids = [doc["id"] for doc in docs]
        chunks = dao.load_chunks_by_doc_ids(doc_ids, limit=2000)
        
        # 将chunks转换为DocumentBlock格式
        blocks = []
        for i, chunk in enumerate(chunks):
            blocks.append(DocumentBlock(
                block_id=chunk.get("chunk_id", f"block_{i}"),
                order_no=i,
                block_type="PARAGRAPH",  # 简化，实际需要识别类型
                text=chunk.get("content", ""),
            ))
        
        if not blocks:
            raise HTTPException(status_code=400, detail="No blocks found")
        
        # 执行抽取
        svc = _svc(request)
        orchestrator = TemplateExtractOrchestrator(
            llm_orchestrator=svc.llm,
            config=None,  # 使用默认配置
        )
        
        result = orchestrator.extract(
            blocks=blocks,
            mode=req.mode,
        )
        
        return {
            "success": True,
            "message": "Template extraction completed",
            "result": result.model_dump(),
        }
        
    except Exception as e:
        import logging
        logging.error(f"模板抽取失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to extract templates: {str(e)}")


@router.post("/projects/{project_id}/templates/extract/confirm")
def confirm_bid_template(
    project_id: str,
    req: dict,  # TemplateConfirmRequest
    request: Request,
    user=Depends(get_current_user_sync),
):
    """
    人工确认范本（跳过LLM或仅做refine+挂载）
    
    Body:
        {
            "kind": "LEGAL_AUTHORIZATION",
            "displayTitle": "法人授权委托书",
            "forceStartBlockId": "b_1023",
            "forceEndBlockId": "b_1098"  # 可选
        }
    
    Returns:
        确认后的TemplateSpanDTO
    """
    from app.schemas.template_extract import TemplateKind, TemplateSpanDTO
    
    # 权限检查
    dao = TenderDAO(_get_pool(request))
    project = dao.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # 解析请求
    kind_str = req.get("kind")
    display_title = req.get("displayTitle", kind_str)
    force_start_block_id = req.get("forceStartBlockId")
    force_end_block_id = req.get("forceEndBlockId")
    
    if not kind_str or not force_start_block_id:
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    try:
        kind = TemplateKind(kind_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid kind: {kind_str}")
    
    # TODO: 实现确认逻辑
    # 1. 如果有forceEndBlockId，直接构建span
    # 2. 如果没有，从forceStartBlockId开始，应用refine规则确定end
    
    # 简化实现：直接返回用户指定的范围
    confirmed_span = TemplateSpanDTO(
        kind=kind,
        display_title=display_title,
        start_block_id=force_start_block_id,
        end_block_id=force_end_block_id or force_start_block_id,
        confidence=1.0,  # 人工确认，置信度100%
        evidence_block_ids=[force_start_block_id],
        reason="人工确认",
    )
    
    return {
        "success": True,
        "message": "Template confirmed",
        "span": confirmed_span.model_dump(),
    }


@router.get("/projects/{project_id}/templates/latest")
def get_latest_bid_templates(
    project_id: str,
    request: Request,
    user=Depends(get_current_user_sync),
):
    """
    获取最新的模板抽取结果（可选：从数据库或缓存读取）
    
    如果需要持久化，可以：
    1. 创建数据库表存储抽取结果
    2. 或使用缓存（Redis/内存）
    
    当前简化实现：返回提示信息
    """
    # 权限检查
    dao = TenderDAO(_get_pool(request))
    project = dao.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # TODO: 从数据库或缓存中读取最新结果
    # 当前简化：返回提示
    return {
        "message": "No cached result, please run extract first",
        "result": None,
    }


# ==================== 一键审核流水线 (P3新增) ====================

# 已删除 run_full_audit 接口（改用一体化审核 unified_audit）


# ==================== 资源访问 ====================

@router.get("/projects/{project_id}/assets/image/{filename}")
async def get_project_image(
    project_id: str,
    filename: str,
):
    """
    获取项目上传的图片资源
    用于在文档预览中显示图片
    
    注意：此接口不需要认证，因为图片通过<img>标签加载，无法携带Authorization header
    安全性由项目ID和文件名的复杂性保证
    """
    import os
    from urllib.parse import unquote
    from fastapi.responses import FileResponse
    
    dao = TenderDAO(_get_pool())
    
    # 解码文件名
    filename = unquote(filename)
    
    # 查找匹配的资源
    with dao.pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT storage_path, mime_type
                FROM tender_project_assets
                WHERE project_id = %s AND filename = %s AND kind = 'image'
                LIMIT 1
            """, [project_id, filename])
            
            row = cur.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail=f"图片未找到: {filename}")
            
            storage_path = row['storage_path']
            mime_type = row['mime_type'] or 'image/png'
            
            if not os.path.exists(storage_path):
                raise HTTPException(status_code=404, detail=f"图片文件不存在: {filename}")
            
            return FileResponse(
                storage_path,
                media_type=mime_type,
                headers={
                    "Cache-Control": "public, max-age=3600",
                    "Access-Control-Allow-Origin": "*"
                }
            )


# ==================== 临时文件访问 ====================

@router.get("/files/temp")
async def serve_temp_file(
    path: str = Query(..., description="文件路径"),
    format: str = Query("pdf", description="文件格式（pdf/docx）"),
):
    """
    提供临时文件访问
    用于预览和下载套用格式后生成的文件
    
    Args:
        path: 文件的完整路径
        format: 文件格式（pdf或docx）
    
    Returns:
        FileResponse: 文件内容
    """
    import os
    from pathlib import Path
    from urllib.parse import unquote
    
    try:
        # 解码路径
        file_path = Path(unquote(path))
        
        # 安全检查：确保文件在临时目录中
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 确定MIME类型
        if format == "pdf":
            media_type = "application/pdf"
        elif format == "docx":
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            media_type = "application/octet-stream"
        
        # 返回文件
        return FileResponse(
            file_path,
            media_type=media_type,
            headers={
                "Cache-Control": "no-cache",
                "Content-Disposition": f"inline; filename={file_path.name}"
            }
        )
    
    except Exception as e:
        logger.error(f"临时文件访问失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"文件访问失败: {str(e)}")
