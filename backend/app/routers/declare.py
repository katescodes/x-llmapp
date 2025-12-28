"""
申报书 Router
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.utils.auth import get_current_user_sync
from app.services.db.postgres import _get_pool
from app.services.dao.declare_dao import DeclareDAO
from app.services.declare_service import DeclareService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/apps/declare", tags=["declare"])


def _get_llm(req: Request):
    """从 app.state 获取 LLM orchestrator"""
    llm = getattr(req.app.state, "llm_orchestrator", None)
    if llm is None:
        raise HTTPException(status_code=500, detail="LLM orchestrator not initialized on app.state")
    return llm


def _get_dao():
    """获取 DAO"""
    pool = _get_pool()
    return DeclareDAO(pool)


def _get_service(req: Request):
    """获取 Service"""
    dao = _get_dao()
    llm = _get_llm(req)
    # TODO: 集成 jobs_service
    return DeclareService(dao, llm, jobs_service=None)


# ==================== Request/Response Models ====================

class ProjectCreateReq(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectOut(BaseModel):
    project_id: str
    kb_id: str
    name: str
    description: Optional[str]
    owner_id: Optional[str]
    created_at: str
    updated_at: str


class RunOut(BaseModel):
    run_id: str
    project_id: str
    task_type: str
    status: str
    progress: float
    message: Optional[str]
    result_json: dict
    created_at: str
    updated_at: str


# ==================== Projects ====================

@router.post("/projects", response_model=ProjectOut)
def create_project(req: ProjectCreateReq, user=Depends(get_current_user_sync)):
    """创建申报项目"""
    from app.services.kb_service import create_kb
    
    # 创建知识库，设置owner为当前用户
    kb_id = create_kb(
        name=f"申报-{req.name}",
        description=req.description or f"申报项目：{req.name}",
        category_id="cat_knowledge",
        owner_id=user.user_id  # 关键：设置知识库所有者
    )
    
    # 创建项目
    dao = _get_dao()
    project = dao.create_project(kb_id, req.name, req.description, owner_id=user.user_id)
    return project


@router.get("/projects", response_model=List[ProjectOut])
def list_projects(user=Depends(get_current_user_sync)):
    """列出申报项目"""
    dao = _get_dao()
    projects = dao.list_projects(owner_id=user.user_id)
    return projects


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, user=Depends(get_current_user_sync)):
    """获取项目详情"""
    dao = _get_dao()
    project = dao.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# ==================== Assets ====================

@router.post("/projects/{project_id}/assets/import")
def import_assets(
    project_id: str,
    kind: str = Form(...),
    files: List[UploadFile] = File(...),
    req: Request = None,
    user=Depends(get_current_user_sync),
):
    """导入资产"""
    service = _get_service(req)
    assets = service.import_assets(project_id, kind, files, user_id=user.user_id)
    return {"assets": assets}


@router.get("/projects/{project_id}/assets")
def list_assets(project_id: str, kind: Optional[str] = None, user=Depends(get_current_user_sync)):
    """列出资产"""
    dao = _get_dao()
    assets = dao.list_assets(project_id, kind)
    return {"assets": assets}


# ==================== Requirements ====================

@router.post("/projects/{project_id}/extract/requirements", response_model=RunOut)
def extract_requirements(
    project_id: str,
    bg: BackgroundTasks,
    req: Request,
    sync: int = 0,
    model_id: Optional[str] = None,
    user=Depends(get_current_user_sync),
):
    """抽取申报要求"""
    dao = _get_dao()
    service = _get_service(req)
    
    # 创建 run
    run_id = dao.create_run(project_id, "requirements")
    
    if sync == 1:
        # 同步执行
        service.extract_requirements(project_id, model_id, run_id)
        run = dao.get_run(run_id)
        return run
    else:
        # 异步执行
        bg.add_task(service.extract_requirements, project_id, model_id, run_id)
        run = dao.get_run(run_id)
        return run


@router.get("/projects/{project_id}/requirements")
def get_requirements(project_id: str, user=Depends(get_current_user_sync)):
    """获取申报要求"""
    dao = _get_dao()
    requirements = dao.get_requirements(project_id)
    if not requirements:
        return {"data": None}
    return requirements


# ==================== Directory ====================

@router.post("/projects/{project_id}/directory/generate", response_model=RunOut)
def generate_directory(
    project_id: str,
    bg: BackgroundTasks,
    req: Request,
    sync: int = 0,
    model_id: Optional[str] = None,
    user=Depends(get_current_user_sync),
):
    """生成申报书目录"""
    dao = _get_dao()
    service = _get_service(req)
    
    # 创建 run
    run_id = dao.create_run(project_id, "directory")
    
    if sync == 1:
        # 同步执行
        service.generate_directory(project_id, model_id, run_id)
        run = dao.get_run(run_id)
        return run
    else:
        # 异步执行
        bg.add_task(service.generate_directory, project_id, model_id, run_id)
        run = dao.get_run(run_id)
        return run


@router.get("/projects/{project_id}/directory/nodes")
def get_directory_nodes(project_id: str, user=Depends(get_current_user_sync)):
    """获取目录节点"""
    dao = _get_dao()
    nodes = dao.get_active_directory_nodes(project_id)
    return {"nodes": nodes}


# ==================== Sections ====================

@router.post("/projects/{project_id}/sections/autofill", response_model=RunOut)
def autofill_sections(
    project_id: str,
    bg: BackgroundTasks,
    req: Request,
    sync: int = 0,
    model_id: Optional[str] = None,
    user=Depends(get_current_user_sync),
):
    """自动填充章节"""
    dao = _get_dao()
    service = _get_service(req)
    
    # 创建 run
    run_id = dao.create_run(project_id, "sections")
    
    if sync == 1:
        # 同步执行
        service.autofill_sections(project_id, model_id, run_id)
        run = dao.get_run(run_id)
        return run
    else:
        # 异步执行
        bg.add_task(service.autofill_sections, project_id, model_id, run_id)
        run = dao.get_run(run_id)
        return run


@router.get("/projects/{project_id}/sections")
def get_sections(
    project_id: str,
    node_id: Optional[str] = None,
    user=Depends(get_current_user_sync),
):
    """获取章节内容"""
    dao = _get_dao()
    sections = dao.get_active_sections(project_id, node_id)
    return {"sections": sections}


# ==================== Document ====================

@router.post("/projects/{project_id}/document/generate", response_model=RunOut)
async def generate_document(
    project_id: str,
    bg: BackgroundTasks,
    req: Request,
    sync: int = 0,
    auto_generate: int = 1,
    user=Depends(get_current_user_sync),
):
    """生成申报书文档"""
    dao = _get_dao()
    service = _get_service(req)
    
    # 创建 run
    run_id = dao.create_run(project_id, "document")
    
    auto_generate_content = bool(auto_generate)
    
    if sync == 1:
        # 同步执行
        await service.generate_document(
            project_id, 
            run_id, 
            auto_generate_content=auto_generate_content
        )
        run = dao.get_run(run_id)
        return run
    else:
        # 异步执行（使用 asyncio.create_task）
        import asyncio
        asyncio.create_task(service.generate_document(
            project_id, 
            run_id, 
            auto_generate_content=auto_generate_content
        ))
        run = dao.get_run(run_id)
        return run


@router.get("/projects/{project_id}/export/docx")
def export_docx(project_id: str, user=Depends(get_current_user_sync)):
    """导出 DOCX"""
    dao = _get_dao()
    document = dao.get_latest_document(project_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="No document found")
    
    storage_path = document.get("storage_path")
    filename = document.get("filename")
    
    if not storage_path or not os.path.exists(storage_path):
        raise HTTPException(status_code=404, detail="Document file not found")
    
    return FileResponse(
        path=storage_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


# ==================== Runs ====================

@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str, user=Depends(get_current_user_sync)):
    """获取任务运行记录"""
    dao = _get_dao()
    run = dao.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # TODO: 如果有 platform_job_id，查询 job 状态并回写
    
    return run


import os

