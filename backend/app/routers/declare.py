"""
申报书 Router
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.utils.auth import get_current_user_sync, get_current_user
from app.services.db.postgres import _get_pool
from app.services.dao.declare_dao import DeclareDAO
from app.services.declare_service import DeclareService
from app.works.declare.extract_v2_service import DeclareExtractV2Service

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


class ProjectUpdateReq(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ProjectDeleteRequest(BaseModel):
    confirm_token: str


class ProjectDeletePlanResponse(BaseModel):
    warning: str
    items: List[dict]
    confirm_token: str


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


@router.put("/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, req: ProjectUpdateReq, user=Depends(get_current_user_sync)):
    """更新项目信息"""
    dao = _get_dao()
    project = dao.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # 更新项目
    updated = dao.update_project(
        project_id=project_id,
        name=req.name,
        description=req.description
    )
    return updated


@router.get("/projects/{project_id}/delete-plan", response_model=ProjectDeletePlanResponse)
def get_project_delete_plan(project_id: str, user=Depends(get_current_user_sync)):
    """获取项目删除计划（预检）"""
    import uuid
    dao = _get_dao()
    
    project = dao.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # 获取资产数量
    assets = dao.list_assets(project_id)
    
    # 获取其他资源数量
    requirements = dao.get_requirements(project_id)
    directory_nodes = dao.get_active_directory_nodes(project_id)
    sections = dao.get_active_sections(project_id)
    
    items = []
    if assets:
        items.append({
            "type": "资产文件",
            "count": len(assets),
            "samples": [a.get("filename", "") for a in assets[:3]],
            "physical_targets": []
        })
    if requirements:
        items.append({
            "type": "申报要求",
            "count": 1,
            "samples": ["申报要求数据"],
            "physical_targets": []
        })
    if directory_nodes:
        items.append({
            "type": "目录节点",
            "count": len(directory_nodes),
            "samples": [n.get("title", "") for n in directory_nodes[:3]],
            "physical_targets": []
        })
    if sections:
        items.append({
            "type": "章节内容",
            "count": len(sections),
            "samples": [s.get("node_title", "") for s in sections[:3]],
            "physical_targets": []
        })
    
    confirm_token = str(uuid.uuid4())
    
    return {
        "warning": f"删除项目 \"{project.get('name')}\" 将同时删除所有关联数据",
        "items": items,
        "confirm_token": confirm_token
    }


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, req: ProjectDeleteRequest, user=Depends(get_current_user_sync)):
    """删除项目"""
    dao = _get_dao()
    
    project = dao.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # 简单验证token（在生产环境应该更严格）
    if not req.confirm_token:
        raise HTTPException(status_code=400, detail="缺少确认令牌")
    
    # 删除项目（级联删除所有关联数据）
    dao.delete_project(project_id)
    
    # 删除知识库
    try:
        from app.services.kb_service import delete_kb
        kb_id = project.get("kb_id")
        if kb_id:
            delete_kb(kb_id)
    except Exception as e:
        logger.warning(f"删除知识库失败: {e}")
    
    return None


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
    """获取目录节点（活跃版本）"""
    dao = _get_dao()
    nodes = dao.get_active_directory_nodes(project_id)
    return {"nodes": nodes}


@router.get("/projects/{project_id}/directory/all-versions")
def get_all_directory_versions(project_id: str, user=Depends(get_current_user_sync)):
    """
    获取所有项目类型的目录版本
    返回格式：
    {
        "versions": [
            {
                "version_id": "...",
                "project_type": "头雁型",
                "project_description": "...",
                "is_active": true,
                "nodes": [...]
            },
            ...
        ]
    }
    """
    dao = _get_dao()
    versions = dao.get_all_directory_versions(project_id)
    
    # 为每个版本加载对应的nodes
    result = []
    for version in versions:
        nodes = dao.get_directory_nodes_by_version(version["version_id"])
        
        # 处理created_at字段（可能是datetime对象或字符串）
        created_at = version.get("created_at")
        if created_at:
            if hasattr(created_at, 'isoformat'):
                created_at = created_at.isoformat()
            else:
                created_at = str(created_at)
        
        result.append({
            "version_id": version["version_id"],
            "project_type": version["project_type"],
            "project_description": version.get("project_description"),
            "is_active": version["is_active"],
            "created_at": created_at,
            "nodes": nodes
        })
    
    return {"versions": result}


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


@router.post("/projects/{project_id}/sections/generate")
async def generate_section_content(
    project_id: str,
    req: Request,
    user=Depends(get_current_user),
):
    """
    AI生成单个章节内容
    用于DocumentComponentManagement组件的AI助手功能
    """
    from pydantic import BaseModel
    
    class GenerateSectionRequest(BaseModel):
        title: str
        level: int
        requirements: Optional[str] = None
    
    body = await req.json()
    request_data = GenerateSectionRequest(**body)
    
    dao = _get_dao()
    pool = _get_pool()
    llm = _get_llm(req)
    
    # 获取申报要求（用于生成上下文）
    requirements = dao.get_requirements(project_id)
    requirements_summary = ""
    if requirements:
        req_data = requirements.get("data_json", {})
        requirements_summary = req_data.get("summary", "") if isinstance(req_data, dict) else ""
    
    # 如果有用户自定义要求，添加到上下文
    if request_data.requirements:
        requirements_summary += f"\n\n【用户要求】\n{request_data.requirements}"
    
    # 创建extract_v2实例并生成内容
    extract_v2 = DeclareExtractV2Service(pool, llm)
    model_id = None  # 使用默认模型
    
    result = await extract_v2.autofill_section_unified(
        project_id=project_id,
        model_id=model_id,
        node_title=request_data.title,
        node_level=request_data.level,  # 使用前端传来的level
        requirements_summary=requirements_summary,
        run_id=None,
    )
    
    # 返回生成的内容
    # autofill_section 返回格式: {"data": {"content_md": "..."}, "evidence_chunk_ids": [...], ...}
    data = result.get("data", {})
    if isinstance(data, dict):
        content = data.get("content_md", "")
    else:
        content = ""
    
    logger.info(f"[sections/generate] 返回内容长度: {len(content)}")
    
    return {"content": content}


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

