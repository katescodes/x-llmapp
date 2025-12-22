"""
申报书自动生成内容功能 - 快速启用示例

这个示例展示如何在现有的导出 API 中快速启用自动生成功能
"""

# ============================================================================
# 方案 1: 通过查询参数启用（推荐）
# ============================================================================

# 在 backend/app/routers/export.py 中修改：

from typing import Optional
from fastapi import Query

@router.post("/projects/{project_id}/export/docx")
async def export_project_docx(
    project_id: str,
    format_template_id: Optional[str] = Query(None, description="格式模板ID"),
    include_toc: bool = Query(True, description="是否包含目录"),
    prefix_numbering: bool = Query(False, description="是否在标题前添加编号"),
    merge_semantic_summary: bool = Query(False, description="是否合并语义目录的summary"),
    # 👇 新增参数
    auto_generate: bool = Query(False, description="是否自动生成缺失的内容"),
    project_context: str = Query("", description="项目上下文信息（用于内容生成）"),
    min_words_h1: int = Query(1200, description="H1标题最小字数"),
    min_words_h2: int = Query(800, description="H2标题最小字数"),
    min_words_h3: int = Query(500, description="H3标题最小字数"),
    min_words_h4: int = Query(300, description="H4标题最小字数"),
    # 👆 新增参数
    pool: ConnectionPool = Depends(get_pool),
    current_user: dict = Depends(get_current_user_sync),
):
    """导出项目为 Word 文档"""
    try:
        dao = TenderDAO(pool)
        export_service = ExportService(dao)
        
        # 👇 准备自动生成配置
        auto_write_cfg = None
        if auto_generate:
            from app.services.export.docx_exporter import AutoWriteCfg
            auto_write_cfg = AutoWriteCfg(
                min_words_h1=min_words_h1,
                min_words_h2=min_words_h2,
                min_words_h3=min_words_h3,
                min_words_h4=min_words_h4,
            )
        # 👆 准备自动生成配置
        
        output_path = await export_service.export_project_to_docx(
            project_id=project_id,
            format_template_id=format_template_id,
            include_toc=include_toc,
            prefix_numbering=prefix_numbering,
            merge_semantic_summary=merge_semantic_summary,
            # 👇 传递自动生成参数
            auto_generate_content=auto_generate,
            auto_write_cfg=auto_write_cfg,
            project_context=project_context,
            # 👆 传递自动生成参数
        )
        
        if not os.path.exists(output_path):
            raise HTTPException(status_code=500, detail="文档生成失败")
        
        filename = f"project_{project_id}.docx"
        
        return FileResponse(
            output_path,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=filename,
        )
    
    except Exception as e:
        logger.error(f"导出失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


# ============================================================================
# 方案 2: 默认启用（适合测试）
# ============================================================================

# 如果希望默认启用自动生成，只需将 auto_generate 的默认值改为 True：

@router.post("/projects/{project_id}/export/docx")
async def export_project_docx(
    project_id: str,
    # ...其他参数...
    auto_generate: bool = Query(True, description="是否自动生成缺失的内容"),  # 👈 默认 True
    # ...
):
    # ...（代码同上）


# ============================================================================
# 方案 3: 通过项目元数据控制
# ============================================================================

# 如果希望每个项目可以单独配置是否自动生成，可以在项目的 meta_json 中添加配置：

@router.post("/projects/{project_id}/export/docx")
async def export_project_docx(
    project_id: str,
    # ...其他参数...
    pool: ConnectionPool = Depends(get_pool),
    current_user: dict = Depends(get_current_user_sync),
):
    try:
        dao = TenderDAO(pool)
        export_service = ExportService(dao)
        
        # 👇 从项目元数据中读取配置
        project = dao.get_project(project_id)
        project_meta = project.get("meta_json", {})
        
        auto_generate = project_meta.get("auto_generate_content", False)
        project_context = project_meta.get("project_context", "")
        
        # 如果项目元数据中有自定义字数配置
        auto_write_cfg = None
        if auto_generate:
            from app.services.export.docx_exporter import AutoWriteCfg
            auto_write_cfg = AutoWriteCfg(
                min_words_h1=project_meta.get("min_words_h1", 1200),
                min_words_h2=project_meta.get("min_words_h2", 800),
                min_words_h3=project_meta.get("min_words_h3", 500),
                min_words_h4=project_meta.get("min_words_h4", 300),
            )
        # 👆 从项目元数据中读取配置
        
        output_path = await export_service.export_project_to_docx(
            project_id=project_id,
            auto_generate_content=auto_generate,
            auto_write_cfg=auto_write_cfg,
            project_context=project_context,
        )
        
        # ...返回文件


# ============================================================================
# 测试示例
# ============================================================================

# 1. 通过 curl 测试（方案 1）
"""
curl -X POST "http://localhost:8000/api/export/projects/proj_123/export/docx?auto_generate=true&project_context=这是某制造企业的数字化转型项目" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  --output project.docx
"""

# 2. 自定义字数要求
"""
curl -X POST "http://localhost:8000/api/export/projects/proj_123/export/docx?auto_generate=true&min_words_h1=1500&min_words_h2=1000" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  --output project.docx
"""

# 3. 通过 Python 客户端测试
"""
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/api/export/projects/proj_123/export/docx",
        params={
            "auto_generate": True,
            "project_context": "某制造企业的数字化转型项目",
            "min_words_h1": 1500,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    
    with open("project.docx", "wb") as f:
        f.write(response.content)
"""


# ============================================================================
# 在 format_templates 路由中启用（套用格式模板场景）
# ============================================================================

# 在 backend/app/routers/format_templates.py 中：

@router.post("/projects/{project_id}/directory/apply-format-template")
async def apply_format_template_to_directory(
    project_id: str,
    req: ApplyFormatTemplateReq,
    return_type: str = Query("json", description="返回类型: json 或 file"),
    # 👇 新增参数
    auto_generate: bool = Query(False, description="是否自动生成缺失的内容"),
    project_context: str = Query("", description="项目上下文信息"),
    # 👆 新增参数
    request: Request = None,
    user=Depends(get_current_user_sync)
):
    """套用格式模板到项目目录"""
    work = _get_format_templates_work(request)
    
    # 权限检查
    # ...
    
    try:
        # 👇 如果 Work 层也支持传递这些参数，可以在这里传递
        # 或者在 Work 层内部调用 export_service 时传递
        result = await work.apply_to_project_directory(
            project_id=project_id,
            template_id=req.format_template_id,
            return_type=return_type,
            # 如果 Work 层支持：
            # auto_generate_content=auto_generate,
            # project_context=project_context,
        )
        # 👆
        
        # ...返回结果


# ============================================================================
# 注意事项
# ============================================================================

"""
1. LLM 配置
   - 确保系统中已配置可用的 LLM 模型
   - 检查 app/services/llm_model_store.py 中的模型配置

2. 性能考虑
   - 大目录树（50+ 节点）+ 自动生成 = 可能需要 2-5 分钟
   - 建议添加超时控制和进度反馈

3. 成本控制
   - 每个标题约消耗 500-1000 tokens
   - 建议在测试环境先验证，生产环境谨慎使用

4. 错误处理
   - LLM 调用失败不会中断整个导出流程
   - 失败的节点会显示错误提示：【生成内容失败：...】

5. 缓存
   - 内容会在单次导出会话中缓存
   - 如需持久化，建议将生成的内容写回数据库的 summary 字段
"""

