"""
招投标应用 - REST API 路由
提供所有 HTTP 接口
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
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
def create_project(req: ProjectCreateReq, request: Request, user=Depends(get_current_user_sync)):
    """创建项目（自动创建KB）"""
    # 1. 先创建知识库
    kb_id = kb_service.create_kb(
        name=f"招投标-{req.name}",
        description=req.description or f"招投标项目：{req.name}",
        category_id="cat_knowledge"  # 使用正确的分类ID
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


@router.post("/projects/{project_id}/assets/import", response_model=List[AssetOut])
async def import_assets(
    project_id: str,
    request: Request,
    kind: str = Form(...),  # tender | bid | template | custom_rule
    bidder_name: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
):
    """
    项目内上传文件并自动绑定
    
    Args:
        kind: 文件类型（tender/bid/template/custom_rule）
        bidder_name: 投标人名称（kind=bid 时必填）
        files: 上传的文件列表
    """
    # 参数校验
    if kind not in ("tender", "bid", "template", "custom_rule"):
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


# ==================== 项目信息抽取 ====================

@router.post("/projects/{project_id}/extract/project-info")
def extract_project_info(
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
    run_id = dao.create_run(project_id, "extract_project_info")
    dao.update_run(run_id, "running", progress=0.01, message="running")
    svc = _svc(request)
    owner_id = user.user_id if user else None
    
    # 检查是否同步执行
    run_sync = sync == 1 or request.headers.get("X-Run-Sync") == "1"

    def job():
        try:
            svc.extract_project_info(project_id, req.model_id, run_id=run_id, owner_id=owner_id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception(f"Extract project-info failed: {e}")
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


# ==================== 风险识别 ====================

@router.post("/projects/{project_id}/extract/risks")
def extract_risks(
    project_id: str,
    req: ExtractReq,
    request: Request,
    bg: BackgroundTasks,
    sync: int = 0,
    user=Depends(get_current_user_sync),
):
    """识别风险（V3版本：提取 requirements 作为风险分析基础）
    
    新流程：
    1. 提取 tender_requirements（调用 LLM）
    2. 前端通过 /risk-analysis 接口聚合展示
    
    Args:
        sync: 同步执行模式，1=同步返回结果，0=后台任务（默认）
    """
    dao = TenderDAO(_get_pool(request))
    run_id = dao.create_run(project_id, "extract_risks")
    dao.update_run(run_id, "running", progress=0.01, message="正在提取招标要求...")
    
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
            
            # 调用 extract_requirements_v1（会自动写入 tender_requirements 表）
            requirements = asyncio.run(extract_v2.extract_requirements_v1(
                project_id=project_id,
                model_id=req.model_id,
                run_id=run_id
            ))
            
            # 获取count
            req_count = requirements.get("count", 0) if isinstance(requirements, dict) else len(requirements)
            
            # 更新运行状态
            dao.update_run(
                run_id, 
                "success", 
                progress=1.0, 
                message=f"成功提取 {req_count} 条招标要求",
                result_json={"count": req_count}
            )
            
            logger.info(f"✅ Extract requirements for risk analysis: project={project_id}, count={req_count}")
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception(f"Extract requirements for risks failed: {e}")
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
                        created_at
                    FROM tender_requirements
                    WHERE project_id = %s
                    ORDER BY created_at ASC
                """, (project_id,))
                
                rows = cur.fetchall()
                
                requirements = []
                for row in rows:
                    requirements.append({
                        "id": row[0],
                        "requirement_id": row[1],
                        "dimension": row[2],
                        "req_type": row[3],
                        "requirement_text": row[4],
                        "is_hard": row[5],
                        "allow_deviation": row[6],
                        "value_schema_json": row[7],
                        "evidence_chunk_ids": row[8] or [],
                        "created_at": row[9].isoformat() if row[9] else None
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
    dao = TenderDAO(_get_pool(request))
    run_id = dao.create_run(project_id, "generate_directory")
    dao.update_run(run_id, "running", progress=0.01, message="running")
    svc = _svc(request)

    def job():
        try:
            svc.generate_directory(project_id, req.model_id, run_id=run_id)
        except Exception as e:
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


@router.post("/projects/{project_id}/directory/{node_id}/body/restore-sample")
def restore_sample(project_id: str, node_id: str, request: Request):
    """恢复章节的范本内容"""
    svc = _svc(request)
    svc.restore_sample_for_section(project_id, node_id)
    
    return {"status": "success"}


@router.post("/projects/{project_id}/directory/auto-fill-samples")
def auto_fill_samples(project_id: str, request: Request):
    """自动填充所有章节的范本"""
    svc = _svc(request)
    logger = logging.getLogger(__name__)

    # 永不抛 500：任何异常都收敛为 ok=false + warnings + debug
    try:
        result = svc.auto_fill_samples(project_id)
        if not isinstance(result, dict):
            result = {
                "ok": False,
                "project_id": project_id,
                "warnings": ["auto_fill_samples returned non-dict result"],
                "tender_asset_id": None,
                "tender_filename": None,
                "tender_storage_path": None,
                "storage_path_exists": False,
                "needs_reupload": False,
                "tender_fragments_upserted": 0,
                "tender_fragments_total": 0,
                "attached_sections_template_sample": 0,
                "attached_sections_builtin": 0,
                # 兼容字段
                "extracted_fragments": 0,
                "attached_sections": 0,
            }
    except Exception as e:
        logger.exception("auto_fill_samples failed project_id=%s", project_id)
        result = {
            "ok": False,
            "project_id": project_id,
            "warnings": [f"auto_fill_samples exception: {type(e).__name__}: {str(e)}"],
            "tender_asset_id": None,
            "tender_filename": None,
            "tender_storage_path": None,
            "storage_path_exists": False,
            "needs_reupload": False,
            "tender_fragments_upserted": 0,
            "tender_fragments_total": 0,
            "attached_sections_template_sample": 0,
            "attached_sections_builtin": 0,
            # 兼容字段
            "extracted_fragments": 0,
            "attached_sections": 0,
        }

    # 统一补齐 nodes（避免前端“没反应”）；这里也要兜底，不能二次抛错
    try:
        flat_nodes = svc.get_directory_with_body_meta(project_id)
        result["nodes"] = _serialize_directory_nodes(flat_nodes)
    except Exception as e:
        logger.exception("auto_fill_samples nodes fetch failed project_id=%s", project_id)
        warnings = result.get("warnings")
        if not isinstance(warnings, list):
            warnings = []
        warnings.append(f"get_directory_with_body_meta exception: {type(e).__name__}: {str(e)}")
        result["warnings"] = warnings
        result["nodes"] = []

    # 兼容补齐（service 内也会填，但这里确保永不缺字段）
    result.setdefault("project_id", project_id)
    result.setdefault("warnings", [])
    result.setdefault("tender_asset_id", None)
    result.setdefault("tender_filename", None)
    result.setdefault("tender_storage_path", None)
    result.setdefault("storage_path_exists", False)
    result.setdefault("needs_reupload", False)
    result.setdefault("tender_fragments_upserted", 0)
    result.setdefault("tender_fragments_total", 0)
    result.setdefault("attached_sections_template_sample", 0)
    result.setdefault("attached_sections_builtin", 0)
    result.setdefault("extracted_fragments", 0)
    result.setdefault("attached_sections", 0)
    result.setdefault("ok", False)
    return result


# ==================== 范本片段：列表 + 预览（目录页侧边栏） ====================

@router.get("/projects/{project_id}/sample-fragments")
def list_sample_fragments(project_id: str, request: Request):
    """
    列出本项目下抽取到的范本片段（轻量列表，不含大正文）。
    """
    svc = _svc(request)
    return svc.list_sample_fragments(project_id)


@router.get("/projects/{project_id}/sample-fragments/{fragment_id}/preview")
def get_sample_fragment_preview(
    project_id: str,
    fragment_id: str,
    request: Request,
    max_elems: int = 60,
):
    """
    获取单条范本片段预览（懒加载）。
    返回 preview_html（简化 HTML），用于前端只读展示，不跳转页面。
    """
    svc = _svc(request)
    try:
        return svc.get_sample_fragment_preview(project_id=project_id, fragment_id=fragment_id, max_elems=max_elems)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"preview_failed: {type(e).__name__}: {str(e)}")


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


@router.get("/files/temp")
def get_temp_file(path: str, format: str = "pdf"):
    """
    获取临时文件（用于预览和下载）
    
    安全限制：仅允许访问 /tmp 目录下的文件
    
    Args:
        path: 文件路径（必须在 /tmp 目录下）
        format: 文件格式（pdf 或 docx）
        
    Returns:
        FileResponse
    """
    import os
    from fastapi.responses import FileResponse
    
    # ⚠️ 安全检查：仅允许 /tmp 下的文件，避免任意文件读取
    if not path.startswith("/tmp/"):
        raise HTTPException(status_code=400, detail="无效的临时文件路径")
    
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # 根据格式设置 MIME 类型
    if format == "pdf":
        media_type = "application/pdf"
    else:
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    
    return FileResponse(path, media_type=media_type)


@router.get("/projects/{project_id}/directory/meta")
def get_directory_meta(project_id: str, request: Request):
    """
    获取目录（带 bodyMeta）+ 套用的 format_template_id + style_hints
    用于前端/脚本验证“套用格式”是否已持久化。
    """
    svc = _svc(request)
    flat_nodes = svc.get_directory_with_body_meta(project_id)

    applied_format_template_id = None
    for n in flat_nodes:
        meta = n.get("meta_json") or {}
        if isinstance(meta, str):
            try:
                import json as _json
                meta = _json.loads(meta)
            except Exception:
                meta = {}
        if isinstance(meta, dict) and meta.get("format_template_id"):
            applied_format_template_id = str(meta.get("format_template_id"))
            break

    style_hints = {}
    if applied_format_template_id:
        spec = svc.get_format_template_spec(applied_format_template_id)
        if spec:
            try:
                style_hints = (spec.to_dict() or {}).get("style_hints") or {}
            except Exception:
                style_hints = {}

    return {
        "nodes": _serialize_directory_nodes(flat_nodes),
        "style_hints": style_hints,
        "applied_format_template_id": applied_format_template_id,
    }


@router.get("/projects/{project_id}/fragments")
def list_fragments(project_id: str, request: Request):
    """列出项目的所有范本片段（用于调试）"""
    dao = TenderDAO(_get_pool(request))
    fragments = dao.list_fragments("PROJECT", project_id)
    return {"fragments": fragments}


@router.put("/projects/{project_id}/directory")
def save_directory(project_id: str, req: DirectorySaveReq, request: Request):
    """保存目录（用户编辑后）"""
    svc = _svc(request)
    svc.save_directory(project_id, [n.dict() for n in req.nodes])
    return {"ok": True}


# 新增：模板预览和套用接口
class TemplateDirReq(BaseModel):
    template_asset_id: str

@router.post("/projects/{project_id}/directory/preview-template")
def preview_template_directory(project_id: str, req: TemplateDirReq, request: Request):
    """预览模板目录（不写库），返回目录节点和样式提示"""
    svc = _svc(request)
    try:
        result = svc.preview_directory_by_template(project_id, req.template_asset_id)
        return result
    except ValueError as e:
        # 该接口历史上使用 template_asset_id，但前端也会传入格式模板ID（tpl_...）。
        # 对“找不到模板”类错误返回 404，避免前端看到 500 空白错误。
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/projects/{project_id}/directory/apply-template")
def apply_template_directory(project_id: str, req: TemplateDirReq, request: Request):
    """套用模板到目录（写库）"""
    svc = _svc(request)
    try:
        n = svc.apply_template_to_directory(project_id, req.template_asset_id)
        return {"ok": True, "count": n}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ==================== 审核 ====================

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
def get_review(project_id: str, request: Request):
    """获取审核结果（包含对比审核和规则审核）"""
    dao = TenderDAO(_get_pool(request))
    rows = dao.list_review_items(project_id)
    flags = get_feature_flags()
    
    out = []
    # 1. 从旧表读取对比审核结果
    for r in rows:
        review_item = {
            "id": r["id"],
            "project_id": r["project_id"],
            "source": "compare",  # 对比审核
            "dimension": r.get("dimension") or "其他",
            "requirement_text": r.get("requirement_text"),
            "response_text": r.get("response_text"),
            "result": r.get("result") or "risk",
            "remark": r.get("remark"),
            "rigid": bool(r.get("rigid", False)),
            "rule_id": None,  # 对比审核没有 rule_id
            "tender_evidence_chunk_ids": r.get("tender_evidence_chunk_ids_json") or [],
            "bid_evidence_chunk_ids": r.get("bid_evidence_chunk_ids_json") or [],
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
    
    # 2. 如果启用规则评估器和 ReviewCase，从 review_findings 读取规则审核结果
    if flags.RULES_EVALUATOR_ENABLED and flags.REVIEWCASE_DUALWRITE:
        try:
            from app.services.platform.reviewcase_service import ReviewCaseService
            reviewcase_service = ReviewCaseService(_get_pool(request))
            
            # 获取项目的最新 review case
            cases = reviewcase_service.list_cases_by_project(project_id, limit=1)
            if cases:
                latest_case = cases[0]
                # 获取最新 run
                runs = reviewcase_service.list_runs_by_case(latest_case["id"], limit=1)
                if runs:
                    latest_run = runs[0]
                    # 获取规则审核 findings
                    findings = reviewcase_service.list_findings_by_run(latest_run["id"])
                    
                    for finding in findings:
                        if finding.get("source") == "rule":
                            evidence_jsonb = finding.get("evidence_jsonb") or {}
                            rule_item = {
                                "id": finding["id"],
                                "project_id": project_id,
                                "source": "rule",
                                "dimension": finding.get("dimension") or "其他",
                                "requirement_text": finding.get("requirement_text"),
                                "response_text": finding.get("response_text"),
                                "result": finding.get("result") or "risk",
                                "remark": finding.get("remark"),
                                "rigid": bool(finding.get("rigid", False)),
                                "rule_id": evidence_jsonb.get("rule_id"),
                                "tender_evidence_chunk_ids": evidence_jsonb.get("tender_chunk_ids", []),
                                "bid_evidence_chunk_ids": evidence_jsonb.get("bid_chunk_ids", []),
                            }
                            out.append(rule_item)
        except Exception as e:
            # 降级：读取规则审核失败不影响对比审核结果
            print(f"[WARN] Failed to load rule findings: {e}")
    
    return out


# ==================== 文档生成 ====================

@router.get("/projects/{project_id}/docx")
def gen_docx_get(
    project_id: str,
    request: Request,
    template_asset_id: Optional[str] = None,
):
    """
    生成 Word 文档（GET 请求）
    
    Args:
        template_asset_id: 模板资产ID（可选，查询参数）
    """
    svc = _svc(request)
    data = svc.generate_docx(project_id, template_asset_id)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

@router.post("/projects/{project_id}/docx")
def gen_docx_post(
    project_id: str,
    request: Request,
    template_asset_id: Optional[str] = None,
):
    """
    生成 Word 文档（POST 请求，兼容）
    
    Args:
        template_asset_id: 模板资产ID（可选）
    """
    svc = _svc(request)
    data = svc.generate_docx(project_id, template_asset_id)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


# ==================== 文档生成（新接口） ====================

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


@router.post("/projects/{project_id}/semantic-outline/generate")
def generate_semantic_outline(
    project_id: str,
    req: SemanticOutlineGenerateReq,
    request: Request,
    user=Depends(get_current_user_sync),
):
    """
    生成语义目录（从评分/要求推导）
    
    工作流：
    1. 阶段A：从chunks抽取结构化要求项（RequirementItem）
    2. 阶段B：用要求项合成多级目录（SemanticOutlineNode）
    3. 阶段C：计算覆盖率、保存结果
    
    Returns:
        {
            "success": bool,
            "message": str,
            "result": {
                "outline_id": str,
                "status": "SUCCESS|LOW_COVERAGE|FAILED",
                "outline": [...],  # 树形目录
                "requirements": [...],  # 要求项列表
                "diagnostics": {
                    "coverage_rate": float,
                    "total_req_count": int,
                    "covered_req_count": int,
                    ...
                }
            }
        }
    """
    # 权限检查
    dao = TenderDAO(_get_pool(request))
    project = dao.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # 这里可以加权限检查：project["owner_id"] == user.user_id
    
    # 使用 works/tender/outline 的统一入口
    from app.works.tender.outline.outline_v2_service import generate_outline_v2
    from app.services.llm.llm_orchestrator_service import get_llm_orchestrator
    
    try:
        pool = _get_pool(request)
        llm = get_llm_orchestrator()
        
        result = generate_outline_v2(
            pool=pool,
            project_id=project_id,
            owner_id=project.get("owner_id"),
            mode=req.mode,
            max_depth=req.max_depth,
            llm_orchestrator=llm,
        )
        
        return {
            "success": True,
            "message": "Semantic outline generated successfully",
            "result": result,
        }
    except Exception as e:
        import logging
        logging.error(f"生成语义目录失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate semantic outline: {str(e)}")


@router.get("/projects/{project_id}/semantic-outline/latest")
def get_latest_semantic_outline(
    project_id: str,
    request: Request,
    user=Depends(get_current_user_sync),
):
    """
    获取项目最新的语义目录
    
    Returns:
        {
            "outline_id": str,
            "status": str,
            "outline": [...],  # 树形目录
            "requirements": [...],  # 要求项列表
            "diagnostics": {...},
            "created_at": datetime
        }
    """
    # 权限检查
    dao = TenderDAO(_get_pool(request))
    project = dao.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # 获取最新语义目录
    svc = _svc(request)
    result = svc.get_latest_semantic_outline(project_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="No semantic outline found for this project")
    
    return result


@router.get("/projects/{project_id}/semantic-outline/list")
def list_semantic_outlines(
    project_id: str,
    request: Request,
    user=Depends(get_current_user_sync),
):
    """
    列出项目的所有语义目录（摘要）
    
    Returns:
        {
            "outlines": [
                {
                    "outline_id": str,
                    "status": str,
                    "mode": str,
                    "coverage_rate": float,
                    "created_at": datetime
                },
                ...
            ]
        }
    """
    # 权限检查
    dao = TenderDAO(_get_pool(request))
    project = dao.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # 获取语义目录列表
    outlines = dao.list_semantic_outlines(project_id)
    
    return {
        "outlines": outlines
    }


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
