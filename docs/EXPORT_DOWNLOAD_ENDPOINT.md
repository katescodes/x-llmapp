"""
Step 4: 增加导出文件下载端点

在 tender.py 或 format_templates.py 中添加以下代码：
"""

@router.get("/projects/{project_id}/exports/docx/{filename}")
def download_exported_docx(
    project_id: str,
    filename: str,
    request: Request,
    user=Depends(get_current_user_sync)
):
    """
    下载项目导出的 DOCX 文件
    
    Args:
        project_id: 项目ID
        filename: 文件名
    """
    import os
    from pathlib import Path
    from fastapi.responses import FileResponse
    
    # 权限检查
    dao = TenderDAO(_get_pool(request))
    project = dao.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.get("owner_id") != user.user_id:
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

