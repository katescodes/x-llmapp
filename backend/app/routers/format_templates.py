"""
格式模板 REST API 路由
专门处理格式模板相关的所有接口，使用 Work 层进行编排
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from psycopg_pool import ConnectionPool
from pydantic import BaseModel

from app.services.dao.tender_dao import TenderDAO
from app.utils.permission import require_permission
from app.models.user import TokenData

logger = logging.getLogger(__name__)

# 创建路由器（注意：prefix 在 main.py 中由 tender router 统一处理）
router = APIRouter(tags=["format-templates"])


# ==================== Schemas ====================

class ApplyFormatTemplateReq(BaseModel):
    """套用格式模板请求"""
    format_template_id: str


class FormatTemplateUpdateReq(BaseModel):
    """更新格式模板请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None


# ==================== Helper Functions ====================

def _get_pool(request: Request) -> ConnectionPool:
    """从 postgres 模块获取连接池"""
    from app.services.db.postgres import _get_pool as get_sync_pool
    return get_sync_pool()


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


# ==================== CRUD Endpoints ====================

@router.get("/format-templates")
def list_format_templates(
    request: Request,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """列出格式模板（返回当前用户的模板和所有公开模板）"""
    work = _get_format_templates_work(request)
    templates = work.list_templates(owner_id=user.user_id)
    return templates


@router.post("/format-templates")
async def create_format_template(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    is_public: bool = Form(False),
    file: UploadFile = File(...),
    model_id: Optional[str] = Form(None),
    request: Request = None,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """创建格式模板（支持可选的LLM分析）"""
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


@router.get("/format-templates/{template_id}")
def get_format_template(
    template_id: str,
    request: Request,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """获取格式模板详情"""
    work = _get_format_templates_work(request)
    template = work.get_template(template_id)
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # 权限检查
    if template.owner_id != user.user_id and not template.is_public and user.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")
    
    return template


@router.put("/format-templates/{template_id}")
def update_format_template(
    template_id: str,
    req: FormatTemplateUpdateReq,
    request: Request,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """更新格式模板元数据"""
    work = _get_format_templates_work(request)
    
    # 权限检查
    template = work.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.owner_id != user.user_id and user.role != "admin":
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


@router.delete("/format-templates/{template_id}", status_code=204)
def delete_format_template(
    template_id: str,
    request: Request,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """删除格式模板"""
    work = _get_format_templates_work(request)
    
    # 权限检查
    template = work.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.owner_id != user.user_id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")
    
    success = work.delete_template(template_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete template")
    
    return Response(status_code=204)


# ==================== File & Spec Endpoints ====================

@router.get("/format-templates/{template_id}/file")
def get_format_template_file(
    template_id: str,
    request: Request,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """下载格式模板原始文件"""
    work = _get_format_templates_work(request)
    
    template = work.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # 权限检查
    if template.owner_id != user.user_id and not template.is_public and user.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")
    
    storage_path = template.template_storage_path
    if not storage_path or not os.path.exists(storage_path):
        raise HTTPException(status_code=404, detail="Template file not found")
    
    return FileResponse(
        storage_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{template.name}.docx"
    )


@router.get("/format-templates/{template_id}/spec")
def get_format_template_spec(
    template_id: str,
    request: Request,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """获取格式模板的样式规格"""
    work = _get_format_templates_work(request)
    
    try:
        spec = work.get_spec(template_id)
        
        # 转换为前端期望的格式
        return {
            "template_name": template_id,
            "version": "2.0",
            "style_hints": spec.style_hints,
            "role_mapping": spec.role_mapping,
            "merge_policy": {
                "template_defines_structure": False,
                "keep_ai_content": True
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ==================== Analysis & Parse Endpoints ====================

@router.post("/format-templates/{template_id}/analyze")
async def analyze_format_template(
    template_id: str,
    force: bool = Query(True),
    file: UploadFile = File(None),
    model_id: Optional[str] = Form(None),
    request: Request = None,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """分析或重新分析格式模板"""
    work = _get_format_templates_work(request)
    
    # 权限检查
    template = work.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.owner_id != user.user_id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # 读取文件（如果提供）
    docx_bytes = None
    if file:
        if not file.filename.endswith((".docx", ".doc")):
            raise HTTPException(status_code=400, detail="Only .docx files are supported")
        docx_bytes = await file.read()
    
    # 调用 Work 层
    try:
        updated = await work.analyze_template(
            template_id=template_id,
            force=force,
            docx_bytes=docx_bytes,
            model_id=model_id
        )
        return updated
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.get("/format-templates/{template_id}/analysis-summary")
def get_format_template_analysis_summary(
    template_id: str,
    request: Request,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """获取格式模板分析摘要"""
    work = _get_format_templates_work(request)
    
    try:
        summary = work.get_analysis_summary(template_id)
        return summary
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/format-templates/{template_id}/parse")
async def parse_format_template(
    template_id: str,
    force: bool = Query(True),
    request: Request = None,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """确定性解析格式模板"""
    work = _get_format_templates_work(request)
    
    # 权限检查
    template = work.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.owner_id != user.user_id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")
    
    try:
        result = await work.parse_template(template_id=template_id, force=force)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@router.get("/format-templates/{template_id}/parse-summary")
def get_format_template_parse_summary(
    template_id: str,
    request: Request,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """获取格式模板解析摘要"""
    work = _get_format_templates_work(request)
    
    try:
        summary = work.get_parse_summary(template_id)
        return summary
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ==================== Preview Endpoint ====================

@router.get("/format-templates/{template_id}/preview")
def get_format_template_preview(
    template_id: str,
    format: str = Query("pdf", pattern="^(pdf|docx)$"),
    request: Request = None,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """生成并返回格式模板预览"""
    work = _get_format_templates_work(request)
    
    # 权限检查
    template = work.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.owner_id != user.user_id and not template.is_public and user.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")
    
    try:
        preview = work.preview(template_id=template_id, format=format)
        
        if not os.path.exists(preview.file_path):
            raise HTTPException(status_code=500, detail="Preview file generation failed")
        
        if format.lower() == "pdf":
            return FileResponse(
                preview.file_path,
                media_type="application/pdf",
                headers={"Content-Disposition": f'inline; filename="{template_id}.pdf"'}
            )
        else:
            return FileResponse(
                preview.file_path,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={"Content-Disposition": f'inline; filename="{template_id}.docx"'}
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预览失败: {str(e)}")


# ==================== Apply to Directory Endpoint ====================

@router.post("/projects/{project_id}/directory/apply-format-template")
async def apply_format_template_to_directory(
    project_id: str,
    req: ApplyFormatTemplateReq,
    return_type: str = Query("json", description="返回类型: json 或 file"),
    request: Request = None,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """套用格式模板到项目目录"""
    work = _get_format_templates_work(request)
    
    # 权限检查（检查项目所有权）
    dao = TenderDAO(_get_pool(request))
    project = dao.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.get("owner_id") != user.user_id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")
    
    try:
        result = await work.apply_to_project_directory(
            project_id=project_id,
            template_id=req.format_template_id,
            return_type=return_type
        )
        
        if not result.ok:
            raise HTTPException(status_code=500, detail=result.detail or "套用格式失败")
        
        if return_type == "file":
            # 直接返回文件
            if not result.docx_path or not os.path.exists(result.docx_path):
                raise HTTPException(status_code=500, detail="Generated file not found")
            
            return FileResponse(
                result.docx_path,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                filename=f"project_{project_id}_formatted.docx"
            )
        else:
            # 返回 JSON
            return {
                "ok": result.ok,
                "nodes": result.nodes,
                "preview_pdf_url": result.preview_pdf_url,
                "download_docx_url": result.download_docx_url
            }
    
    except Exception as e:
        logger.error(f"套用格式失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"套用格式失败: {str(e)}")


# ==================== Template Analysis Routes (/templates/) ====================

@router.get("/templates/{template_id}/analysis")
def get_template_analysis(
    template_id: str,
    request: Request,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """获取模板分析结果（给 FormatTemplatesPage 使用）"""
    work = _get_format_templates_work(request)
    
    template = work.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # 权限检查
    if template.owner_id != user.user_id and not template.is_public and user.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")
    
    analysis_json = template.analysis_json
    if not analysis_json:
        raise HTTPException(status_code=404, detail="Template not analyzed")
    
    # 构建摘要
    role_mapping = analysis_json.get("roleMapping", {})
    apply_assets = analysis_json.get("applyAssets", {})
    blocks = analysis_json.get("blocks", [])
    policy = apply_assets.get("policy", {})
    anchors = apply_assets.get("anchors", [])
    keep_plan = apply_assets.get("keepPlan", {})
    
    # 检查是否有内容标记
    has_content_marker = any(
        b.get("markerFlags", {}).get("hasContentMarker")
        for b in blocks
    )
    
    # 构建前端期望的数据结构
    return {
        "template_id": template_id,
        "template_name": template.name,
        "analysis_summary": {
            "confidence": policy.get("confidence", 0.5),
            "anchorsCount": len(anchors),
            "keepBlocksCount": len(keep_plan.get("keepBlockIds", [])),
            "deleteBlocksCount": len(keep_plan.get("deleteBlockIds", [])),
            "hasContentMarker": has_content_marker,
        },
        "warnings": policy.get("warnings", []),
        "full_analysis": {
            "roleMapping": role_mapping,
            "applyAssets": apply_assets,
            "blocks": blocks,
        },
    }


@router.post("/templates/{template_id}/reanalyze")
async def reanalyze_template(
    template_id: str,
    model_id: Optional[str] = Query(None, description="LLM模型ID"),
    request: Request = None,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """重新分析模板（给 FormatTemplatesPage 使用）"""
    work = _get_format_templates_work(request)
    
    # 权限检查
    template = work.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.owner_id != user.user_id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # 如果没有提供 model_id，自动选择默认的LLM模型
    if not model_id:
        logger.info("未提供 model_id，尝试获取默认LLM模型")
        try:
            from app.services.llm_model_store import get_llm_store
            
            # 使用LLMModelStore获取默认模型（从llm_models.json文件）
            llm_store = get_llm_store()
            default_model = llm_store.get_default_model()
            
            if default_model:
                model_id = default_model.id
                logger.info(f"✅ 使用默认LLM模型: {model_id} ({default_model.name})")
                logger.info(f"   模型地址: {default_model.base_url}")
            else:
                # 如果没有默认模型，获取第一个可用的模型
                models = llm_store.list_models()
                if models:
                    model_id = models[0].id
                    logger.info(f"✅ 使用第一个可用的LLM模型: {model_id} ({models[0].name})")
                else:
                    logger.warning("⚠️ 未找到任何LLM模型，将使用默认策略（不调用LLM）")
        except Exception as e:
            logger.warning(f"❌ 获取默认LLM模型失败: {e}，将使用默认策略", exc_info=True)
    
    try:
        updated = await work.analyze_template(
            template_id=template_id,
            force=True,
            docx_bytes=None,  # 使用现有文件
            model_id=model_id
        )
        
        # 返回分析结果
        return {
            "success": True,
            "template_id": template_id,
            "analysis_status": "SUCCESS",
            "model_id": model_id  # 返回使用的模型ID
        }
    
    except Exception as e:
        logger.error(f"重新分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"重新分析失败: {str(e)}")


# ==================== Export Download Endpoint ====================

@router.get("/projects/{project_id}/directory/format-preview")
async def get_format_preview(
    project_id: str,
    format: str = Query("pdf", description="预览格式: pdf 或 docx"),
    format_template_id: Optional[str] = Query(None, description="格式模板ID"),
    request: Request = None,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """
    获取套用格式后的预览文件
    
    Args:
        project_id: 项目ID
        format: 预览格式 (pdf 或 docx)
        format_template_id: 格式模板ID（可选，默认从项目根节点读取）
    
    Returns:
        文件流（PDF 或 DOCX）
    """
    # 权限检查
    dao = TenderDAO(_get_pool(request))
    project = dao.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.get("owner_id") != user.user_id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")
    
    work = _get_format_templates_work(request)
    
    try:
        # 1. 如果未指定模板，从根节点获取
        if not format_template_id:
            format_template_id = dao.get_directory_root_format_template(project_id)
            if not format_template_id:
                raise HTTPException(
                    status_code=400,
                    detail="项目未绑定格式模板，请先套用格式模板"
                )
        
        # 2. 生成预览
        result = await work.preview_project_with_template(
            project_id=project_id,
            template_id=format_template_id,
            output_format=format
        )
        
        if not result.ok:
            raise HTTPException(status_code=500, detail=result.error or "生成预览失败")
        
        # 3. 返回文件
        file_path = result.pdf_path if format == "pdf" else result.docx_path
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Preview file not found")
        
        # 确定 media_type
        if format == "pdf":
            media_type = "application/pdf"
            filename_suffix = ".pdf"
        else:
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            filename_suffix = ".docx"
        
        project_name = project.get("name", "投标文件")
        safe_filename = f"{project_name}_预览{filename_suffix}"
        
        return FileResponse(
            file_path,
            media_type=media_type,
            filename=safe_filename
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成格式预览失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成预览失败: {str(e)}")


@router.get("/projects/{project_id}/exports/docx/{filename}")
def download_exported_docx(
    project_id: str,
    filename: str,
    request: Request,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """
    下载项目导出的 DOCX 文件
    
    Args:
        project_id: 项目ID
        filename: 文件名
    """
    # 权限检查
    dao = TenderDAO(_get_pool(request))
    project = dao.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.get("owner_id") != user.user_id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # 构建文件路径
    renders_dir = os.getenv("TENDER_RENDERS_DIR", "/app/storage/tender/renders")
    file_path = Path(renders_dir) / project_id / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # 返回文件
    project_name = project.get("name", "投标文件")
    safe_filename = f"{project_name}_{filename}"
    
    return FileResponse(
        str(file_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=safe_filename
    )


