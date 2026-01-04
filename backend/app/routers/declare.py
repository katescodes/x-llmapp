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


@router.delete("/projects/{project_id}/assets/{asset_id}")
def delete_asset(
    project_id: str,
    asset_id: str,
    user=Depends(get_current_user_sync)
):
    """删除资产"""
    dao = _get_dao()
    dao.delete_asset(asset_id)
    return {"success": True}


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
        node_id: Optional[str] = None  # ✅ 新增：节点ID
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
    
    logger.info(f"[sections/generate] 生成内容长度: {len(content)}, node_id={request_data.node_id}")
    
    # ✅ 新增：自动保存到数据库（如果提供了node_id）
    if request_data.node_id and content:
        try:
            section_id = dao.save_section(
                project_id=project_id,
                node_id=request_data.node_id,
                node_title=request_data.title,
                content_html=content,  # content_md实际上是HTML格式
                content_md=None,
                evidence_chunk_ids=result.get("evidence_chunk_ids"),
                retrieval_trace=result.get("retrieval_trace"),
            )
            logger.info(f"[sections/generate] 已保存到数据库: section_id={section_id}")
        except Exception as e:
            logger.error(f"[sections/generate] 保存失败: {e}", exc_info=True)
            # 保存失败不影响返回生成的内容
    
    return {"content": content}


@router.post("/projects/{project_id}/sections/save")
async def save_section_content(
    project_id: str,
    req: Request,
    user=Depends(get_current_user),
):
    """
    保存章节内容到数据库
    用于手动编辑后的保存
    """
    from pydantic import BaseModel
    
    class SaveSectionRequest(BaseModel):
        node_id: str
        node_title: str
        content_html: str
        content_md: Optional[str] = None
    
    body = await req.json()
    request_data = SaveSectionRequest(**body)
    
    dao = _get_dao()
    
    try:
        section_id = dao.save_section(
            project_id=project_id,
            node_id=request_data.node_id,
            node_title=request_data.node_title,
            content_html=request_data.content_html,
            content_md=request_data.content_md,
        )
        logger.info(f"[sections/save] 保存成功: section_id={section_id}")
        return {"success": True, "section_id": section_id}
    except Exception as e:
        logger.error(f"[sections/save] 保存失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@router.get("/projects/{project_id}/sections/load")
async def load_all_sections(
    project_id: str,
    user=Depends(get_current_user),
):
    """
    加载项目的所有章节内容
    返回格式: {node_id: {content_html: "...", content_md: "...", ...}}
    """
    dao = _get_dao()
    
    try:
        sections_dict = dao.get_all_sections(project_id)
        logger.info(f"[sections/load] 加载了 {len(sections_dict)} 个章节")
        return {"sections": sections_dict}
    except Exception as e:
        logger.error(f"[sections/load] 加载失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"加载失败: {str(e)}")


@router.get("/projects/{project_id}/sections/{node_id}")
async def get_section_content(
    project_id: str,
    node_id: str,
    user=Depends(get_current_user),
):
    """
    获取单个节点的章节内容
    """
    dao = _get_dao()
    
    try:
        section = dao.get_section(project_id, node_id)
        if not section:
            return {"section": None}
        return {"section": section}
    except Exception as e:
        logger.error(f"[sections/get] 获取失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


# ==================== Assets ====================

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
    
    dao = _get_dao()
    
    # 解码文件名
    filename = unquote(filename)
    
    # 查找匹配的资源
    with dao.pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT storage_path, mime_type
                FROM declare_assets
                WHERE project_id = %s AND filename = %s AND asset_type = 'image'
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
async def export_docx(project_id: str, user=Depends(get_current_user_sync)):
    """导出申报书为 Word 文档"""
    from docx import Document
    from docx.shared import Pt
    from io import BytesIO
    import tempfile
    from pathlib import Path
    
    dao = _get_dao()
    
    # 1. 获取项目信息
    project = dao.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project_name = project.get("project_name", "申报书")
    
    # 2. 获取目录节点（最新版本）
    with dao.pool.connection() as conn:
        with conn.cursor() as cur:
            # 获取最新的目录版本
            cur.execute("""
                SELECT version_id 
                FROM declare_directory_versions 
                WHERE project_id = %s AND is_active = true 
                ORDER BY created_at DESC 
                LIMIT 1
            """, [project_id])
            version_row = cur.fetchone()
            
            if not version_row:
                raise HTTPException(status_code=404, detail="No directory found")
            
            version_id = version_row['version_id']
            
            # 获取该版本的所有目录节点，按 order_no 排序
            cur.execute("""
                SELECT id, title, level, order_no, parent_id, meta_json
                FROM declare_directory_nodes
                WHERE version_id = %s
                ORDER BY order_no
            """, [version_id])
            nodes = cur.fetchall()
    
    if not nodes:
        raise HTTPException(status_code=404, detail="No directory nodes found")
    
    # ✅ 从 meta_json 中提取 notes 到顶层（便于后续使用）
    for node in nodes:
        meta_json = node.get('meta_json')
        if isinstance(meta_json, dict) and 'notes' in meta_json:
            node['notes'] = meta_json['notes']
        else:
            node['notes'] = None
    
    # 3. 获取所有章节内容（使用最新版本的sections）
    sections_dict = {}
    with dao.pool.connection() as conn:
        with conn.cursor() as cur:
            for node in nodes:
                cur.execute("""
                    SELECT content_html
                    FROM declare_sections
                    WHERE project_id = %s AND node_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, [project_id, node['id']])
                section_row = cur.fetchone()
                if section_row and section_row['content_html']:
                    sections_dict[node['id']] = section_row['content_html']
    
    # 4. 创建 Word 文档
    doc = Document()
    
    # 设置文档默认字体
    style = doc.styles['Normal']
    style.font.name = '宋体'
    style.font.size = Pt(12)
    
    # 5. 按目录顺序写入内容
    for node in nodes:
        node_id = node['id']
        title = node['title']
        level = node['level']
        
        # 5.1 添加标题
        heading_level = min(max(level, 1), 9)  # Word 支持 1-9 级标题
        doc.add_heading(title, level=heading_level)
        
        # 5.2 添加正文内容
        content = sections_dict.get(node_id, "")
        
        if content:
            # 将 HTML 内容转换为纯文本（简单处理）
            # 移除 HTML 标签
            import re
            
            # 处理图片占位符 {image:filename}
            def process_images(html_text):
                # 暂时将图片占位符替换为文字说明
                pattern = r'\{image:([^}]+)\}'
                return re.sub(pattern, r'[图片: \1]', html_text)
            
            content = process_images(content)
            
            # 移除 HTML 标签，保留文本
            content = re.sub(r'<br\s*/?>', '\n', content)  # 换行符
            content = re.sub(r'<p[^>]*>', '', content)  # 段落开始
            content = re.sub(r'</p>', '\n', content)  # 段落结束
            content = re.sub(r'<h[1-6][^>]*>', '\n', content)  # 标题开始
            content = re.sub(r'</h[1-6]>', '\n', content)  # 标题结束
            content = re.sub(r'<strong>', '', content)  # 加粗开始
            content = re.sub(r'</strong>', '', content)  # 加粗结束
            content = re.sub(r'<li[^>]*>', '\n• ', content)  # 列表项
            content = re.sub(r'</li>', '', content)
            content = re.sub(r'<ul[^>]*>', '', content)
            content = re.sub(r'</ul>', '\n', content)
            content = re.sub(r'<ol[^>]*>', '', content)
            content = re.sub(r'</ol>', '\n', content)
            content = re.sub(r'<[^>]+>', '', content)  # 移除其他标签
            
            # 清理多余的空行
            content = re.sub(r'\n\s*\n', '\n\n', content)
            content = content.strip()
            
            # 添加段落
            if content:
                paragraphs = content.split('\n\n')
                for para_text in paragraphs:
                    if para_text.strip():
                        doc.add_paragraph(para_text.strip())
        else:
            # 如果没有内容，添加提示
            doc.add_paragraph("（本章节内容待填写）", style='Normal')
        
        # 添加一些间距
        doc.add_paragraph("")
    
    # 6. 保存文档到临时文件
    temp_dir = tempfile.gettempdir()
    filename = f"{project_name}.docx"
    output_path = Path(temp_dir) / f"declare_{project_id}_{filename}"
    
    doc.save(str(output_path))
    
    logger.info(f"[export_docx] 导出成功: {output_path}")
    
    # 7. 返回文件
    return FileResponse(
        path=str(output_path),
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

