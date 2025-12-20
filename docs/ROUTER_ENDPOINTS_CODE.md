# 格式模板 Router 端点（Step 3 新增/重构代码）

## 在 tender.py 中添加以下代码（在现有格式模板端点位置）

```python
# ==================== DELETE 端点 ====================

@router.delete("/format-templates/{template_id}", status_code=204)
def delete_format_template(
    template_id: str,
    request: Request,
    user=Depends(get_current_user_sync)
):
    """删除格式模板"""
    work = _get_format_templates_work(request)
    
    # 权限检查
    template = work.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.owner_id != user.user_id:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    success = work.delete_template(template_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete template")
    
    return Response(status_code=204)


# ==================== SPEC 端点 ====================

@router.get("/format-templates/{template_id}/spec")
def get_format_template_spec(
    template_id: str,
    request: Request,
    user=Depends(get_current_user_sync)
):
    """
    获取格式模板的样式规格
    
    Returns:
        包含 style_hints 和 role_mapping 的 spec 对象
    """
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


# ==================== FILE 端点 ====================

@router.get("/format-templates/{template_id}/file")
def get_format_template_file(
    template_id: str,
    request: Request,
    user=Depends(get_current_user_sync)
):
    """下载格式模板原始文件"""
    work = _get_format_templates_work(request)
    
    template = work.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # 权限检查
    if template.owner_id != user.user_id and not template.is_public:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    storage_path = template.template_storage_path
    if not storage_path or not os.path.exists(storage_path):
        raise HTTPException(status_code=404, detail="Template file not found")
    
    return FileResponse(
        storage_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{template.name}.docx"
    )


@router.put("/format-templates/{template_id}/file")
async def replace_format_template_file(
    template_id: str,
    file: UploadFile = File(...),
    request: Request = None,
    user=Depends(get_current_user_sync)
):
    """
    替换格式模板文件并重新分析
    """
    work = _get_format_templates_work(request)
    
    # 权限检查
    template = work.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.owner_id != user.user_id:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    if not file.filename.endswith((".docx", ".doc")):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")
    
    # 读取文件
    docx_bytes = await file.read()
    
    # 调用 Work 层重新分析
    try:
        updated = await work.analyze_template(
            template_id=template_id,
            force=True,
            docx_bytes=docx_bytes,
            model_id=None  # 不使用LLM
        )
        return updated
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"替换失败: {str(e)}")


# ==================== ANALYZE 端点 ====================

@router.post("/format-templates/{template_id}/analyze")
async def analyze_format_template(
    template_id: str,
    force: bool = Query(True),
    file: UploadFile = File(None),
    model_id: Optional[str] = Form(None),
    request: Request = None,
    user=Depends(get_current_user_sync)
):
    """
    分析或重新分析格式模板
    """
    work = _get_format_templates_work(request)
    
    # 权限检查
    template = work.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.owner_id != user.user_id:
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
    user=Depends(get_current_user_sync)
):
    """获取格式模板分析摘要"""
    work = _get_format_templates_work(request)
    
    try:
        summary = work.get_analysis_summary(template_id)
        return summary
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ==================== PARSE 端点 ====================

@router.post("/format-templates/{template_id}/parse")
async def parse_format_template(
    template_id: str,
    force: bool = Query(True),
    request: Request = None,
    user=Depends(get_current_user_sync)
):
    """
    确定性解析格式模板
    """
    work = _get_format_templates_work(request)
    
    # 权限检查
    template = work.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.owner_id != user.user_id:
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
    user=Depends(get_current_user_sync)
):
    """获取格式模板解析摘要"""
    work = _get_format_templates_work(request)
    
    try:
        summary = work.get_parse_summary(template_id)
        return summary
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ==================== PREVIEW 端点 ====================

@router.get("/format-templates/{template_id}/preview")
def get_format_template_preview(
    template_id: str,
    format: str = Query("pdf", pattern="^(pdf|docx)$"),
    request: Request = None,
    user=Depends(get_current_user_sync)
):
    """
    生成并返回格式模板预览
    
    Args:
        format: 预览格式 (pdf 或 docx)
    """
    work = _get_format_templates_work(request)
    
    # 权限检查
    template = work.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.owner_id != user.user_id and not template.is_public:
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


# ==================== APPLY TO DIRECTORY 端点 ====================

@router.post("/projects/{project_id}/directory/apply-format-template")
def apply_format_template_to_directory(
    project_id: str,
    req: ApplyFormatTemplateReq,
    return_type: str = Query("json", description="返回类型: json 或 file"),
    request: Request = None,
    user=Depends(get_current_user_sync)
):
    """
    套用格式模板到项目目录
    
    Args:
        project_id: 项目ID
        req: 请求体（包含 format_template_id）
        return_type: 返回类型 (json 或 file)
    
    Returns:
        json: 返回预览URL和下载URL
        file: 直接返回文件
    """
    work = _get_format_templates_work(request)
    
    # 权限检查（检查项目所有权）
    dao = TenderDAO(_get_pool(request))
    project = dao.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.get("owner_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    try:
        result = work.apply_to_project_directory(
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
        logging.getLogger(__name__).error(f"套用格式失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"套用格式失败: {str(e)}")


# ==================== 模板分析路由 (/templates/) ====================

@router.get("/templates/{template_id}/analysis")
def get_template_analysis(
    template_id: str,
    request: Request,
    user=Depends(get_current_user_sync)
):
    """
    获取模板分析结果（给 FormatTemplatesPage 使用）
    
    直接读取 format_templates.analysis_json
    """
    work = _get_format_templates_work(request)
    
    template = work.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # 权限检查
    if template.owner_id != user.user_id and not template.is_public:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    analysis_json = template.analysis_json
    if not analysis_json:
        raise HTTPException(status_code=404, detail="Template not analyzed")
    
    # 构建摘要（与 get_analysis_summary 类似但返回完整结构）
    role_mapping = analysis_json.get("roleMapping", {})
    apply_assets = analysis_json.get("applyAssets", {})
    blocks = analysis_json.get("blocks", [])
    policy = apply_assets.get("policy", {})
    
    return {
        "templateName": template.name,
        "confidence": policy.get("confidence", 0.5),
        "warnings": policy.get("warnings", []),
        "anchorsCount": len(apply_assets.get("anchors", [])),
        "hasContentMarker": any(
            b.get("markerFlags", {}).get("hasContentMarker")
            for b in blocks
        ),
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


@router.post("/templates/{template_id}/reanalyze")
async def reanalyze_template(
    template_id: str,
    model_id: Optional[str] = Query(None, description="LLM模型ID"),
    request: Request = None,
    user=Depends(get_current_user_sync)
):
    """
    重新分析模板（给 FormatTemplatesPage 使用）
    
    调用 Work.analyze_template(force=True)
    """
    work = _get_format_templates_work(request)
    
    # 权限检查
    template = work.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.owner_id != user.user_id:
        raise HTTPException(status_code=403, detail="Permission denied")
    
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
            "analysis_status": "SUCCESS"
        }
    
    except Exception as e:
        logging.getLogger(__name__).error(f"重新分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"重新分析失败: {str(e)}")
```

## 注意事项

1. 所有端点都通过 `_get_format_templates_work()` 获取 Work 实例
2. 权限检查：只有模板所有者或公开模板才能访问
3. 错误处理：统一使用 HTTPException
4. 日志记录：关键操作都有日志
5. 返回格式：与前端期望完全对齐

