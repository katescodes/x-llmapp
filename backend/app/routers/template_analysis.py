"""
模板分析和渲染 REST API 路由
提供模板分析和基于模板的目录渲染接口
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from psycopg_pool import ConnectionPool

from app.services.dao.tender_dao import TenderDAO
from app.utils.permission import require_permission
from app.utils.auth import get_current_user_sync
from app.models.user import TokenData

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/apps/tender/templates", tags=["template-analysis"])


def get_pool(request: Request) -> ConnectionPool:
    """获取数据库连接池"""
    from app.services.db.postgres import _get_pool as get_sync_pool
    return get_sync_pool()


class TemplateAnalysisResponse(BaseModel):
    """模板分析响应"""
    template_id: str
    template_name: str
    analysis_summary: dict
    warnings: list[str]


class RenderOutlineRequest(BaseModel):
    """渲染目录请求"""
    template_id: str
    project_id: Optional[str] = None  # 如果提供，从项目目录渲染
    outline_tree: Optional[list[dict]] = None  # 或直接提供目录树


@router.post("/upload-and-analyze")
async def upload_and_analyze_template(
    name: str = Form(..., description="模板名称"),
    file: UploadFile = File(..., description="模板文件（.docx）"),
    is_public: bool = Form(False, description="是否公开"),
    model_id: Optional[str] = Form(None, description="LLM模型ID"),
    pool: ConnectionPool = Depends(get_pool),
    current_user: dict = Depends(get_current_user_sync),
) -> TemplateAnalysisResponse:
    """
    上传模板并分析
    
    流程：
    1. 保存模板文件
    2. 分析模板（extract_doc_blocks + LLM + style parsing）
    3. 存储分析结果到数据库
    4. 返回分析摘要
    """
    logger.info(f"上传并分析模板: name={name}, user={current_user.get('username')}")
    
    try:
        # 1. 验证文件类型
        if not file.filename or not file.filename.endswith('.docx'):
            raise HTTPException(status_code=400, detail="只支持 .docx 文件")
        
        # 2. 保存文件
        storage_dir = Path("storage/templates")
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        file_id = uuid.uuid4().hex
        storage_path = storage_dir / f"{file_id}_{file.filename}"
        
        content = await file.read()
        with open(storage_path, "wb") as f:
            f.write(content)
        
        logger.info(f"模板文件已保存: {storage_path}")
        
        # 3. 解析样式
        from app.services.template.template_style_analyzer import (
            extract_style_profile,
            infer_role_mapping
        )
        style_profile = extract_style_profile(str(storage_path))
        role_mapping = infer_role_mapping(style_profile)
        logger.info(f"样式解析完成: {len(style_profile.get('styles', []))} 个样式")
        
        # 4. 提取 blocks
        from app.services.template.docx_blocks import extract_doc_blocks
        blocks = extract_doc_blocks(str(storage_path))
        logger.info(f"提取文档块: {len(blocks)} 个块")
        
        # 5. LLM 生成 applyAssets（可选，失败不阻塞）
        apply_assets = None
        if model_id:
            try:
                from app.services.template.template_applyassets_llm import (
                    build_applyassets_prompt,
                    validate_applyassets,
                    get_fallback_apply_assets
                )
                from app.services.llm_client import llm_json
                
                logger.info(f"开始 LLM 分析: model_id={model_id}")
                prompt = build_applyassets_prompt(name, blocks)
                llm_result = llm_json(prompt, model_id=model_id, temperature=0.0)
                apply_assets = validate_applyassets(llm_result, blocks)
                logger.info(f"LLM 分析完成: confidence={apply_assets.get('policy', {}).get('confidence', 0)}")
            except Exception as e:
                logger.warning(f"LLM 分析失败，使用默认策略: {e}")
                from app.services.template.template_applyassets_llm import get_fallback_apply_assets
                apply_assets = get_fallback_apply_assets()
        else:
            logger.info("未指定 model_id，跳过 LLM 分析")
            from app.services.template.template_applyassets_llm import get_fallback_apply_assets
            apply_assets = get_fallback_apply_assets()
        
        # 6. 构建 analysis_json
        analysis = {
            "styleProfile": style_profile,
            "roleMapping": role_mapping,
            "applyAssets": apply_assets,
            "blocks": blocks[:100]  # 只保留前100个块，避免太大
        }
        
        # 4. 存储到数据库
        dao = TenderDAO(pool)
        
        template_id = dao.create_format_template(
            owner_id=current_user.get("id"),
            name=name,
            is_public=is_public
        )
        
        # 更新 template_storage_path 和 analysis_json
        dao._execute(
            """
            UPDATE format_templates
            SET template_storage_path = %s,
                analysis_json = %s
            WHERE id = %s
            """,
            (str(storage_path), json.dumps(analysis), template_id)
        )
        
        logger.info(f"模板分析完成: template_id={template_id}")
        
        # 7. 构建返回摘要
        policy = apply_assets.get("policy", {})
        summary = {
            "templateName": name,
            "confidence": policy.get("confidence", 0.5),
            "warnings": policy.get("warnings", []),
            "anchorsCount": len(apply_assets.get("anchors", [])),
            "hasContentMarker": any(b.get("markerFlags", {}).get("hasContentMarker") for b in blocks),
            "keepBlocksCount": len(apply_assets.get("keepPlan", {}).get("keepBlockIds", [])),
            "deleteBlocksCount": len(apply_assets.get("keepPlan", {}).get("deleteBlockIds", [])),
            "headingStyles": {k: v for k, v in role_mapping.items() if k.startswith("h")},
            "bodyStyle": role_mapping.get("body"),
            "blocksSummary": {
                "total": len(blocks),
                "paragraphs": sum(1 for b in blocks if b["type"] == "paragraph"),
                "tables": sum(1 for b in blocks if b["type"] == "table"),
            }
        }
        warnings = policy.get("warnings", [])
        
        return TemplateAnalysisResponse(
            template_id=template_id,
            template_name=name,
            analysis_summary=summary,
            warnings=warnings
        )
    
    except Exception as e:
        logger.error(f"模板分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"模板分析失败: {str(e)}")


@router.get("/{template_id}/analysis")
def get_template_analysis(
    template_id: str,
    pool: ConnectionPool = Depends(get_pool),
    current_user: dict = Depends(get_current_user_sync),
) -> dict:
    """
    获取模板分析结果
    """
    logger.info(f"获取模板分析: template_id={template_id}")
    
    try:
        dao = TenderDAO(pool)
        template = dao.get_format_template(template_id)
        
        if not template:
            raise HTTPException(status_code=404, detail="模板不存在")
        
        analysis_json = template.get("analysis_json")
        
        if not analysis_json:
            raise HTTPException(status_code=404, detail="模板未分析或分析结果丢失")
        
        # 如果是字符串，解析为JSON
        if isinstance(analysis_json, str):
            analysis_json = json.loads(analysis_json)
        
        # 构建摘要
        role_mapping = analysis_json.get("roleMapping", {})
        apply_assets = analysis_json.get("applyAssets", {})
        blocks = analysis_json.get("blocks", [])
        policy = apply_assets.get("policy", {})
        
        summary = {
            "templateName": template.get("name"),
            "confidence": policy.get("confidence", 0.5),
            "warnings": policy.get("warnings", []),
            "anchorsCount": len(apply_assets.get("anchors", [])),
            "hasContentMarker": any(b.get("markerFlags", {}).get("hasContentMarker") for b in blocks),
            "keepBlocksCount": len(apply_assets.get("keepPlan", {}).get("keepBlockIds", [])),
            "deleteBlocksCount": len(apply_assets.get("keepPlan", {}).get("deleteBlockIds", [])),
            "headingStyles": {k: v for k, v in role_mapping.items() if k.startswith("h")},
            "bodyStyle": role_mapping.get("body"),
            "blocksSummary": {
                "total": len(blocks),
                "paragraphs": sum(1 for b in blocks if b.get("type") == "paragraph"),
                "tables": sum(1 for b in blocks if b.get("type") == "table"),
            }
        }
        
        return {
            "template_id": template_id,
            "template_name": template.get("name"),
            "analysis_summary": summary,
            "full_analysis": analysis_json  # 完整分析（包含roleMapping等）
        }
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"获取模板分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取模板分析失败: {str(e)}")


@router.post("/render-outline")
def render_outline(
    req: RenderOutlineRequest,
    pool: ConnectionPool = Depends(get_pool),
    current_user: dict = Depends(get_current_user_sync),
):
    """
    使用模板渲染目录树
    
    支持两种模式：
    1. 从项目目录渲染（提供 project_id）
    2. 直接提供目录树（提供 outline_tree）
    """
    logger.info(
        f"渲染目录: template_id={req.template_id}, "
        f"project_id={req.project_id}, user={current_user.get('username')}"
    )
    
    try:
        dao = TenderDAO(pool)
        
        # 1. 获取模板
        template = dao.get_format_template(req.template_id)
        
        if not template:
            raise HTTPException(status_code=404, detail="模板不存在")
        
        template_path = template.get("template_storage_path")
        if not template_path or not os.path.exists(template_path):
            raise HTTPException(status_code=404, detail="模板文件不存在")
        
        analysis_json = template.get("analysis_json")
        if not analysis_json:
            raise HTTPException(status_code=400, detail="模板未分析，请先分析模板")
        
        if isinstance(analysis_json, str):
            analysis_json = json.loads(analysis_json)
        
        # 2. 获取目录树
        if req.project_id:
            # 从项目加载目录
            outline_tree = dao.list_directory(req.project_id)
            if not outline_tree:
                raise HTTPException(status_code=400, detail="项目没有目录数据")
        elif req.outline_tree:
            # 直接使用提供的目录树
            outline_tree = req.outline_tree
        else:
            raise HTTPException(status_code=400, detail="必须提供 project_id 或 outline_tree")
        
        # 3. 渲染
        output_dir = Path(tempfile.gettempdir()) / "template_renders"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_filename = f"render_{req.template_id}_{uuid.uuid4().hex[:8]}.docx"
        output_path = output_dir / output_filename
        
        # 使用新的基于模板复制的渲染器
        from app.services.template.template_renderer import render_outline_with_template_v2
        
        render_outline_with_template_v2(
            template_path=template_path,
            output_path=str(output_path),
            outline_tree=outline_tree,
            analysis_json=analysis_json,
            prefix_numbering=True  # 默认启用编号前缀
        )
        
        # 4. 返回文件
        logger.info(f"渲染完成: {output_path}")
        
        return FileResponse(
            output_path,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=output_filename,
            headers={
                "Content-Disposition": f'attachment; filename="{output_filename}"'
            }
        )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"渲染失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"渲染失败: {str(e)}")


@router.post("/{template_id}/reanalyze")
def reanalyze_template(
    template_id: str,
    model_id: Optional[str] = Query(None, description="LLM模型ID"),
    pool: ConnectionPool = Depends(get_pool),
    current_user: dict = Depends(get_current_user_sync),
) -> dict:
    """
    重新分析模板
    """
    logger.info(f"重新分析模板: template_id={template_id}")
    
    try:
        dao = TenderDAO(pool)
        template = dao.get_format_template(template_id)
        
        if not template:
            raise HTTPException(status_code=404, detail="模板不存在")
        
        template_path = template.get("template_storage_path")
        if not template_path or not os.path.exists(template_path):
            raise HTTPException(status_code=404, detail="模板文件不存在")
        
        # 重新分析（使用新的流程）
        from app.services.template.template_style_analyzer import (
            extract_style_profile,
            infer_role_mapping
        )
        from app.services.template.docx_blocks import extract_doc_blocks
        from app.services.template.template_applyassets_llm import (
            build_applyassets_prompt,
            validate_applyassets,
            get_fallback_apply_assets
        )
        from app.services.llm_client import llm_json
        
        # 样式解析
        style_profile = extract_style_profile(template_path)
        role_mapping = infer_role_mapping(style_profile)
        
        # 提取blocks
        blocks = extract_doc_blocks(template_path)
        
        # LLM分析（可选）
        apply_assets = None
        if model_id:
            try:
                prompt = build_applyassets_prompt(template.get("name", ""), blocks)
                llm_result = llm_json(prompt, model_id=model_id, temperature=0.0)
                apply_assets = validate_applyassets(llm_result, blocks)
            except Exception as e:
                logger.warning(f"LLM分析失败: {e}")
                apply_assets = get_fallback_apply_assets()
        else:
            apply_assets = get_fallback_apply_assets()
        
        # 构建analysis_json
        analysis = {
            "styleProfile": style_profile,
            "roleMapping": role_mapping,
            "applyAssets": apply_assets,
            "blocks": blocks[:100]
        }
        
        # 更新数据库
        dao._execute(
            "UPDATE format_templates SET analysis_json = %s WHERE id = %s",
            (json.dumps(analysis), template_id)
        )
        
        logger.info("模板重新分析完成")
        
        # 构建摘要
        policy = apply_assets.get("policy", {})
        summary = {
            "templateName": template.get("name"),
            "confidence": policy.get("confidence", 0.5),
            "warnings": policy.get("warnings", []),
            "anchorsCount": len(apply_assets.get("anchors", [])),
            "hasContentMarker": any(b.get("markerFlags", {}).get("hasContentMarker") for b in blocks),
            "keepBlocksCount": len(apply_assets.get("keepPlan", {}).get("keepBlockIds", [])),
            "deleteBlocksCount": len(apply_assets.get("keepPlan", {}).get("deleteBlockIds", [])),
            "headingStyles": {k: v for k, v in role_mapping.items() if k.startswith("h")},
            "bodyStyle": role_mapping.get("body"),
        }
        warnings = policy.get("warnings", [])
        
        return {
            "template_id": template_id,
            "analysis_summary": summary,
            "warnings": warnings
        }
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"重新分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"重新分析失败: {str(e)}")

