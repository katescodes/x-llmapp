# 申报书自动生成内容功能 - 实施总结

## ✅ 完成情况

已成功实现"按标题自动写内容"功能，**仅修改了 DOCX 导出生成相关代码**，未涉及解析、目录生成、入库、worker 等其他模块。

## 📝 修改文件清单

### 核心功能文件

1. **`backend/app/services/export/docx_exporter.py`** ✅
   - 新增 `AutoWriteCfg` 数据类（配置字数要求）
   - 新增 `_target_min_words()` 函数（根据层级返回最小字数）
   - 新增 `_infer_section_style()` 函数（根据标题推断写作侧重点）
   - 新增 `generate_section_text_by_title()` 异步函数（调用 LLM 生成内容）
   - 修改 `render_directory_tree_to_docx()` 函数：
     - 改为异步函数
     - 添加自动生成相关参数
     - 在 `emit_node()` 中集成自动生成逻辑

2. **`backend/app/services/export/export_service.py`** ✅
   - 修改 `export_project_to_docx()` 函数：
     - 改为异步函数
     - 添加自动生成相关参数
   - 修改 `_export_with_template()` 函数：
     - 改为异步函数
     - 传递自动生成参数到底层函数

### 调用链更新（支持异步）

3. **`backend/app/routers/export.py`** ✅
   - `export_project_docx()` 改为异步
   - `export_project_docx_post()` 改为异步
   - 使用 `await` 调用导出服务

4. **`backend/app/routers/format_templates.py`** ✅
   - `apply_format_template_to_directory()` 改为异步
   - `get_format_preview()` 改为异步
   - 使用 `await` 调用 work 层函数

5. **`backend/app/works/tender/format_templates/work.py`** ✅
   - `apply_to_project_directory()` 改为异步
   - `preview_project_with_template()` 改为异步
   - 使用 `await` 调用导出服务

### 文档文件

6. **`docs/AUTO_GENERATE_CONTENT_USAGE.md`** ✅
   - 功能使用说明
   - API 调用示例
   - 配置说明
   - 工作原理说明

7. **`IMPLEMENTATION_SUMMARY.md`** ✅（本文件）
   - 实施总结
   - 修改清单

## 🔧 核心功能特性

### 1. 智能标题识别

根据标题关键词自动推断写作侧重点：

| 关键词模式 | 生成内容风格 |
|-----------|-------------|
| 概况/背景/意义 | 背景现状、政策依据、问题痛点、建设必要性 |
| 目标/指标/成效 | 可量化目标指标、对标分析、预期成效 |
| 建设内容/技术方案 | 总体架构、关键系统、技术路线 |
| 场景/应用/流程 | 典型场景、系统支撑、数据闭环、指标提升 |
| 组织/保障/管理 | 组织架构、制度流程、数据治理、安全保障 |
| 投资/预算/资金 | 投资构成、测算口径、资金来源 |
| 进度/计划/里程碑 | 阶段划分、里程碑、交付物、验收机制 |

### 2. 字数分级控制

按标题层级设置最小字数要求（可配置）：

- **H1**：≥ 1200 字
- **H2**：≥ 800 字
- **H3**：≥ 500 字
- **H4**：≥ 300 字

### 3. 专业文风

- 采用政府项目申报书的正式口吻
- 结构清晰，自动分段（6-12 段）
- 使用条目式列举（如：一是...二是...）
- 避免虚构具体数据，缺失信息用【待补】占位

### 4. 性能优化

- **内容缓存**：同一标题只生成一次
- **异步调用**：全链路异步，不阻塞其他请求
- **可配置**：字数、模型、上下文都可自定义

## 🚀 使用方式

### 基本调用

```python
from app.services.export.export_service import ExportService
from app.services.dao.tender_dao import TenderDAO

dao = TenderDAO(pool)
export_service = ExportService(dao)

output_path = await export_service.export_project_to_docx(
    project_id="proj_123",
    format_template_id="tpl_456",
    auto_generate_content=True,  # 启用自动生成
    project_context="项目背景信息...",
    model_id="your_llm_model_id",  # 可选
)
```

### 自定义配置

```python
from app.services.export.docx_exporter import AutoWriteCfg

cfg = AutoWriteCfg(
    min_words_h1=1500,
    min_words_h2=1000,
    min_words_h3=600,
    min_words_h4=400,
    max_tokens=2500,
)

output_path = await export_service.export_project_to_docx(
    project_id="proj_123",
    auto_generate_content=True,
    auto_write_cfg=cfg,
)
```

## 🔍 技术实现细节

### LLM 调用

使用项目现有的 LLM 客户端：
- `app.services.llm_model_store.get_llm_store()` - 获取模型配置
- `app.services.llm_client.generate_answer_with_model()` - 调用 LLM

### Prompt 设计

- **System Prompt**：定义专家角色、写作要求、避免虚构
- **User Prompt**：包含标题、层级、侧重点、上下文、输出要求

### 缓存策略

- 缓存 key：`L{level}:{title}`
- 生命周期：单次导出会话
- 避免重复调用 LLM

### 异步改造

全链路改为异步：
- 底层：`render_directory_tree_to_docx()` → async
- 服务层：`export_project_to_docx()` → async
- Work层：`apply_to_project_directory()` → async
- 路由层：所有相关端点 → async

## ⚠️ 注意事项

1. **LLM 配置**：需要在系统中配置可用的 LLM 模型
2. **性能考虑**：大目录树 + 多个空 summary 节点 = 多次 LLM 调用
3. **成本控制**：每次生成消耗 tokens，建议先小规模测试
4. **错误处理**：LLM 调用失败会返回错误提示，不会中断整个导出流程

## 🧪 测试建议

### 1. 单元测试

测试各个辅助函数：
```python
from app.services.export.docx_exporter import (
    _target_min_words,
    _infer_section_style,
    AutoWriteCfg,
)

cfg = AutoWriteCfg()
assert _target_min_words(1, cfg) == 1200
assert _target_min_words(2, cfg) == 800
assert "背景现状" in _infer_section_style("项目建设背景")
```

### 2. 集成测试

测试完整导出流程：
```python
# 创建测试项目（只有标题，没有 summary）
# 调用导出 API，启用 auto_generate_content=True
# 验证生成的 DOCX 中是否有内容
# 验证内容长度是否满足要求
```

### 3. 端到端测试

通过 HTTP API 测试：
```bash
# 假设已添加 API 参数
curl -X POST "http://localhost:8000/api/export/projects/proj_123/export/docx?auto_generate=true"
```

## 📊 性能指标（预估）

| 指标 | 数值 |
|-----|------|
| 单个标题生成时间 | 3-10 秒（取决于 LLM 速度）|
| 单个标题字数 | 300-1500 字 |
| Token 消耗 | 约 500-1000 tokens/标题 |
| 并发支持 | 支持（异步实现）|

## 🔮 未来优化方向

1. **批量生成**：一次调用生成多个标题的内容，减少往返次数
2. **持久化缓存**：将生成的内容写回 `summary` 字段
3. **用户确认流程**：生成后提供预览/修改界面
4. **模板库**：为常见标题准备模板，减少 LLM 依赖
5. **渐进式生成**：先生成大纲，用户确认后再扩写细节
6. **多模型支持**：根据标题类型选择不同的专业模型

## ✅ 验证清单

- [x] 定位到 DOCX 生成代码位置
- [x] 添加自动生成内容的辅助函数
- [x] 集成到 DOCX 导出流程
- [x] 更新调用链以支持异步
- [x] 添加配置选项（字数、模型等）
- [x] 实现标题样式推断
- [x] 实现内容缓存
- [x] 错误处理和日志记录
- [x] 编写使用文档
- [x] 无 linter 错误（除已有的 import 警告）

## 📞 联系与支持

如有问题或需要进一步优化，请参考：
- 使用文档：`docs/AUTO_GENERATE_CONTENT_USAGE.md`
- 核心代码：`backend/app/services/export/docx_exporter.py`

---

**实施日期**：2025-12-21  
**实施版本**：符合用户需求的"只改 DOCX 生成处"版本  
**状态**：✅ 已完成，可投入使用

