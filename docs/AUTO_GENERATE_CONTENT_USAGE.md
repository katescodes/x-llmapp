# 自动生成申报书内容功能使用说明

## 功能概述

本功能在申报书 DOCX 导出时，可以自动为没有 `summary` 的章节标题生成正文内容。生成的内容会：

- **字数充足**：根据标题层级，H1 至少 1200 字，H2 至少 800 字，H3 至少 500 字，H4 至少 300 字
- **风格专业**：采用政府项目申报书的正式口吻
- **结构清晰**：自动分段（6-12 段），使用条目式列举
- **避免虚构**：不会编造具体的企业名称、金额、专利号等，缺失信息用【待补】占位

## 代码修改位置

✅ **仅修改了导出 DOCX 生成的代码**，不涉及解析、目录生成、入库、worker 等其他模块。

核心修改文件：
- `backend/app/services/export/docx_exporter.py` - 添加了自动生成内容的辅助函数
- `backend/app/services/export/export_service.py` - 更新导出服务以支持异步和自动生成
- `backend/app/routers/export.py` - 更新路由以支持异步
- `backend/app/routers/format_templates.py` - 更新路由以支持异步
- `backend/app/works/tender/format_templates/work.py` - 更新 Work 层以支持异步

## 使用方式

### 1. 基本用法（Python API）

```python
from app.services.export.export_service import ExportService
from app.services.export.docx_exporter import AutoWriteCfg
from app.services.dao.tender_dao import TenderDAO

# 创建 DAO 和服务
dao = TenderDAO(pool)
export_service = ExportService(dao)

# 导出时启用自动生成
output_path = await export_service.export_project_to_docx(
    project_id="proj_123",
    format_template_id="tpl_456",
    auto_generate_content=True,  # 启用自动生成
    project_context="这是项目的背景信息，可以包含任何已知的上下文...",  # 可选
    model_id="your_llm_model_id",  # 可选，不提供则使用默认模型
)
```

### 2. 自定义配置

如果需要调整字数等参数：

```python
from app.services.export.docx_exporter import AutoWriteCfg

# 自定义配置
cfg = AutoWriteCfg(
    min_words_h1=1500,  # H1 标题至少 1500 字
    min_words_h2=1000,  # H2 标题至少 1000 字
    min_words_h3=600,   # H3 标题至少 600 字
    min_words_h4=400,   # H4 标题至少 400 字
    max_tokens=2500,    # 单次 LLM 调用的最大 token 数
)

output_path = await export_service.export_project_to_docx(
    project_id="proj_123",
    auto_generate_content=True,
    auto_write_cfg=cfg,  # 使用自定义配置
)
```

### 3. 通过 HTTP API 使用

目前 HTTP API 尚未暴露这些参数，如需通过 API 使用，可以在路由中添加相应的查询参数：

```python
# 在 backend/app/routers/export.py 中添加参数
@router.post("/projects/{project_id}/export/docx")
async def export_project_docx(
    project_id: str,
    # ... 其他参数 ...
    auto_generate: bool = Query(False, description="是否自动生成内容"),
    project_context: str = Query("", description="项目上下文信息"),
    model_id: Optional[str] = Query(None, description="LLM模型ID"),
):
    # ...
    output_path = await export_service.export_project_to_docx(
        project_id=project_id,
        auto_generate_content=auto_generate,
        project_context=project_context,
        model_id=model_id,
    )
```

## 工作原理

### 1. 标题样式推断

系统会根据标题关键词自动推断写作侧重点：

| 关键词 | 写作侧重点 |
|--------|-----------|
| 概况、背景、意义、必要性 | 背景现状、政策依据、问题痛点、建设必要性与总体目标 |
| 目标、指标、成效、效益 | 可量化目标指标（效率/质量/成本等）+对标+预期成效 |
| 建设内容、技术方案、架构 | 总体架构（业务/数据/应用/安全）+关键系统+技术路线 |
| 场景、应用、业务流程 | 典型场景：现状→改造→系统支撑→数据闭环→指标提升 |
| 组织、保障、管理、制度 | 组织架构、制度流程、数据治理、安全与运维保障 |
| 投资、预算、资金 | 投资构成（软硬件/服务/集成/运维）+测算口径 |
| 进度、计划、里程碑 | 阶段划分、里程碑、交付物、验收机制 |

### 2. LLM 调用

系统使用项目现有的 LLM 调用方式（`app.services.llm_client.generate_answer_with_model`），会：

1. 自动获取默认 LLM 模型（如果未指定 `model_id`）
2. 构建专业的 system prompt 和 user prompt
3. 传入标题、层级、上下文信息
4. 要求 LLM 输出至少 N 字的分段正文
5. 缓存结果，避免重复生成

### 3. 内容缓存

生成的内容会在内存中缓存（key = `L{level}:{title}`），同一次导出中相同标题不会重复调用 LLM。

## 注意事项

1. **异步调用**：所有涉及的函数都已改为异步（`async def`），调用时需要使用 `await`
2. **LLM 配置**：确保系统中已配置可用的 LLM 模型
3. **性能考虑**：如果目录树很大且很多节点没有 summary，自动生成会调用多次 LLM，耗时较长
4. **成本控制**：每次生成会消耗 LLM tokens，建议在测试环境先验证效果

## 扩展建议

如果需要进一步优化，可以考虑：

1. **批量生成**：收集所有需要生成的标题，一次性调用 LLM 批量生成
2. **持久化缓存**：将生成的内容写回数据库的 `summary` 字段
3. **用户确认**：生成后提供预览界面，让用户确认或修改
4. **模板库**：为常见的标题类型准备模板，减少 LLM 调用

## 示例输出

### 输入
- 标题：`1.1 项目建设背景与必要性`
- 层级：H2
- 上下文：（空）

### 输出（示例）
```
随着制造业数字化转型的深入推进，传统生产管理模式已难以满足【待补：企业名称】在新发展阶段的要求。本项目建设背景主要体现在以下几个方面：

一是国家政策导向明确。《"十四五"智能制造发展规划》《关于深化新一代信息技术与制造业融合发展的指导意见》等政策文件，明确提出推动制造业高质量发展，加快数字化、网络化、智能化转型。本项目响应国家战略，符合产业政策导向。

二是市场竞争压力加大。当前行业竞争日益激烈，客户对产品质量、交付周期、定制化能力提出了更高要求。传统依靠人工管理、纸质单据流转的模式，已无法满足市场需求，亟需通过信息化、数字化手段提升管理水平和响应速度。

三是内部管理亟待优化。企业现有生产管理系统存在【待补：问题描述】，导致【待补：具体痛点】。通过本项目建设，可以实现【待补：预期改进】，显著提升管理效率和决策水平。

四是技术条件已经成熟。工业互联网、大数据、云计算等新一代信息技术快速发展，为企业数字化转型提供了坚实的技术支撑。本项目将充分利用这些技术，构建先进的数字化管理平台。

因此，本项目建设具有重要的战略意义和现实必要性，是企业实现高质量发展的必由之路。
```

（注：实际输出会根据上下文和 LLM 模型有所不同）

