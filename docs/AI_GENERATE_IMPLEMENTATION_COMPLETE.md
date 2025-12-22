# AI生成申报书功能 - 实现完成说明

## ✅ 已完成的代码修改

### 1. DeclareDocxExporter（核心改造）

**文件**: `backend/app/services/export/declare_docx_exporter.py`

**修改内容**:
- ✅ 导入自动生成相关函数
- ✅ `export()` 方法改为异步（`async def`）
- ✅ 添加 `auto_generate_content` 和 `model_id` 参数
- ✅ 初始化 `AutoWriteCfg` 配置
- ✅ 自动构建项目上下文
- ✅ 在写正文处添加判断逻辑：
  - 如果内容为空或占位符 → 调用 LLM 多轮生成
  - 如果有实际内容 → 保留不覆盖
  - 按空行分段写入 docx

**关键代码**（第 113-155 行）：
```python
# 判断是否需要自动生成
if auto_generate_content and _is_empty_or_placeholder(content_md):
    # 调用自动生成函数
    generated_text = await generate_section_text_by_title(
        title=title,
        level=level,
        project_context=project_context,
        cfg=cfg,
        cache=content_cache,
        model_id=model_id,
    )
    
    # 按空行分段写入 docx
    paragraphs = re.split(r"\n{2,}", generated_text)
    for para in paragraphs:
        doc.add_paragraph(para)
```

### 2. DeclareService（服务层）

**文件**: `backend/app/services/declare_service.py`

**修改内容**:
- ✅ `generate_document()` 方法改为异步
- ✅ 添加 `auto_generate_content` 和 `model_id` 参数
- ✅ 传递参数到 `exporter.export()`

**关键代码**（第 334-371 行）：
```python
async def generate_document(
    self,
    project_id: str,
    run_id: Optional[str] = None,
    auto_generate_content: bool = True,  # 👈 默认启用
    model_id: Optional[str] = None,
):
    exporter = DeclareDocxExporter(self.dao)
    result = await exporter.export(
        project_id,
        auto_generate_content=auto_generate_content,
        model_id=model_id,
    )
```

### 3. 路由层

**文件**: `backend/app/routers/declare.py`

**修改内容**:
- ✅ `generate_document` 路由改为异步
- ✅ 添加 `auto_generate` 查询参数（默认为 1，即启用）
- ✅ 传递参数到服务层

**关键代码**（第 255-289 行）：
```python
@router.post("/projects/{project_id}/document/generate")
async def generate_document(
    project_id: str,
    auto_generate: int = 1,  # 👈 默认启用
    # ...
):
    auto_generate_content = bool(auto_generate)
    
    if sync == 1:
        await service.generate_document(
            project_id, 
            run_id, 
            auto_generate_content=auto_generate_content
        )
```

## 📊 功能效果

### 使用方式

#### 1. 前端点击按钮（无需修改前端）

用户点击"🤖 AI 生成申报书"按钮 → 自动调用后端 API → **自动生成内容**

#### 2. API 调用

```bash
# 启用自动生成（默认）
POST /api/apps/declare/projects/{project_id}/document/generate?sync=1

# 禁用自动生成（只生成框架）
POST /api/apps/declare/projects/{project_id}/document/generate?sync=1&auto_generate=0
```

### 生成流程

```
1. 用户点击"AI生成申报书"
   ↓
2. 后端加载项目数据、目录节点、已有章节
   ↓
3. 遍历每个目录节点
   ↓
4. 写标题（Heading）
   ↓
5. 判断内容：
   - 如果为空或占位符（【填写】、TODO等）
     → 调用 LLM 多轮生成（1000-2500字）
     → 分段写入 docx
   - 如果已有内容
     → 保留不覆盖
   ↓
6. 保存 docx 到数据库
   ↓
7. 前端显示"生成完成，可导出"
   ↓
8. 用户点击"导出 DOCX"下载
```

### 生成内容特点

| 特性 | 说明 |
|------|------|
| **字数充足** | H1≥1200字，H2≥800字，H3≥500字，H4≥300字 |
| **多轮生成** | 分3轮（主体+保障+指标），避免超时 |
| **智能识别** | 根据标题关键词（背景/目标/技术等）调整写作风格 |
| **不虚构** | 缺失信息用【待补】占位，不编造数据 |
| **分段清晰** | 按空行自动分段，保持 docx 段落结构 |
| **上下文** | 自动提取项目信息（名称/企业/专利/设备等） |

## 🧪 测试验证

### 方式 1：通过前端测试（推荐）

1. 登录系统
2. 创建或打开一个申报项目
3. 完成步骤 1-4（上传文件、生成目录等）
4. 进入步骤 5，点击"🤖 AI 生成申报书"
5. 等待生成完成（可能需要 5-15 分钟，取决于章节数量）
6. 点击"📥 导出 DOCX"下载
7. 打开 docx 检查：
   - ✓ 每个标题下都有内容
   - ✓ 内容长度充足（不再是占位符）
   - ✓ 有【待补】占位（说明没虚构）
   - ✓ 文件体积明显增大

### 方式 2：通过 API 测试

```bash
# 1. 创建项目并生成目录（假设已完成）

# 2. 调用生成文档 API
curl -X POST "http://localhost:8000/api/apps/declare/projects/{project_id}/document/generate?sync=1" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 响应示例：
{
  "run_id": "run_xxx",
  "status": "success",
  "progress": 1.0,
  "message": "Document generated"
}

# 3. 导出 docx
curl -X GET "http://localhost:8000/api/apps/declare/projects/{project_id}/export/docx" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  --output "申报书.docx"

# 4. 打开 申报书.docx 检查效果
```

### 方式 3：查看日志

```bash
# 查看生成日志
tail -f logs/app.log | grep "DeclareDocxExporter"

# 预期输出：
[INFO] [DeclareDocxExporter] 自动生成已启用，项目上下文: 567 字符
[INFO] [DeclareDocxExporter] 自动生成内容: title=项目建设背景, level=2
[INFO] 第 1 轮生成完成: 1234 字符
[INFO] 第 2 轮生成完成: 987 字符
[INFO] 第 3 轮生成完成: 765 字符
[INFO] 多轮生成完成: title=项目建设背景, 总字符数=2986, 轮数=3
[INFO] [DeclareDocxExporter] 自动生成完成: 12 个段落, 2986 字符
...
```

## ⚙️ 配置选项

### 1. 启用/禁用自动生成

在 API 调用时指定：

```bash
# 启用（默认）
?auto_generate=1

# 禁用（只生成框架，不填充内容）
?auto_generate=0
```

### 2. 调整字数要求

如需修改字数要求，编辑 `declare_docx_exporter.py` 第 67-73 行：

```python
cfg = AutoWriteCfg(
    min_words_h1=1500,  # 改为 1500
    min_words_h2=1000,  # 改为 1000
    # ...
)
```

### 3. 使用指定 LLM 模型

在服务层调用时传入 `model_id`（目前前端未暴露，可后续添加）。

## 📈 性能预估

| 项目规模 | 节点数 | 需生成节点 | 预计耗时 | 总字数 |
|----------|--------|------------|----------|--------|
| 小型 | 10-15 | 8-12 | 3-5 分钟 | 8K-15K |
| 中型 | 20-30 | 15-25 | 6-12 分钟 | 15K-30K |
| 大型 | 40-60 | 30-50 | 15-25 分钟 | 30K-60K |

**注意**：
- 每个节点平均耗时 15-25 秒
- LLM 调用速度受模型和网络影响
- 建议先测试小项目验证效果

## ⚠️ 注意事项

### 1. LLM 配置

确保系统中已配置可用的 LLM 模型：

```python
from app.services.llm_model_store import get_llm_store

store = get_llm_store()
model = store.get_default_model()
print(f"默认模型: {model.name if model else 'None'}")
```

如果未配置，生成会失败并显示错误信息。

### 2. 超时处理

- 单个节点生成超时不会影响其他节点
- 失败的节点会显示【自动生成内容失败：...】
- 建议在测试环境先验证，确认 LLM 响应速度

### 3. 成本控制

- 每个节点约消耗 1500-3000 tokens
- 30 个节点的项目约消耗 50K-90K tokens
- 按 0.01元/1K tokens 计算，约 0.5-1 元/项目

### 4. 内容质量

- 生成的内容是"初稿"，需人工审核
- 【待补】处需要补充具体数据
- 可能需要调整表述和添加细节

## 🎉 总结

✅ **已完成**：
- 核心功能实现（自动生成内容）
- 3个文件的代码改造
- 完整的调用链路（前端按钮 → 后端 API → 生成 docx）
- 默认启用自动生成

✅ **可立即使用**：
- 无需修改前端代码
- 用户点击"AI生成申报书"按钮即可体验
- 生成的 docx 内容充实，字数充足

✅ **效果预期**：
- 每个章节 1000-2500 字
- 分段清晰，结构合理
- 无虚构数据，使用【待补】占位
- 大幅减少手动填写工作量

🚀 **立即测试**，享受 AI 自动生成申报书的便利！

