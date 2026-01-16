# 修复范本插入功能 - 完整指南

## 🎯 问题概述

您的AI标书生成系统中，**范本自动插入功能已存在，但对于旧项目可能不生效**。

### 问题原因

1. **范本识别功能**在文档入库时自动标记潜在范本（已实现）
2. 但**已入库的旧文档**没有这些标记
3. 导致目录生成时找不到范本，无法自动插入

## ✅ 解决方案

### 方案1：一键诊断和修复（推荐）

我们提供了一个诊断和修复脚本，可以自动检测并修复问题。

#### 第1步：诊断问题

```bash
# 进入后端容器
cd /aidata/x-llmapp1/backend

# 诊断所有项目（查看哪些项目有问题）
python scripts/fix_template_insertion.py --diagnose --all

# 或诊断特定项目
python scripts/fix_template_insertion.py --diagnose --project-id <项目ID>
```

诊断报告会显示：
- ✓ 招标文档是否存在
- ✓ 文档分片总数
- ✓ 已标记为范本的chunks数量
- ⚠️ 未标记的潜在范本数量
- ✓ 目录节点是否有正文内容

#### 第2步：修复问题

```bash
# 修复所有项目
python scripts/fix_template_insertion.py --fix --all

# 或修复特定项目
python scripts/fix_template_insertion.py --fix --project-id <项目ID>
```

修复过程会：
1. 扫描所有未标记的文档分片
2. 使用智能规则识别潜在范本
3. 在数据库中标记范本chunks
4. 显示标记结果统计

#### 第3步：重新生成目录

修复完成后，需要**重新生成投标目录**以应用范本：

1. 在前端界面打开项目
2. 进入"步骤2：提取信息" → "投标目录"子标签
3. 点击"生成目录"按钮
4. 等待生成完成

现在目录节点应该会自动填充范本内容！

---

### 方案2：新项目自动生效

对于**新上传的招标文档**，范本识别功能会自动工作，无需手动操作。

系统会在文档入库时自动：
1. 识别潜在范本chunks
2. 标记到数据库
3. 在生成目录时自动匹配和填充

---

## 🔍 验证功能是否生效

### 检查1：查看范本标记

```bash
# 查看项目的范本chunks（在postgres容器中）
psql -U llmapp -d llmapp -c "
SELECT 
    COUNT(*) as total_templates,
    COUNT(DISTINCT (meta_json->>'template_score')) as unique_scores
FROM doc_segments ds
JOIN document_versions dv ON dv.id = ds.doc_version_id
JOIN tender_project_documents tpd ON tpd.asset_id = dv.asset_id
WHERE tpd.project_id = '<项目ID>'
AND ds.meta_json->>'is_potential_template' = 'true';
"
```

如果返回 `total_templates > 0`，说明范本已标记成功。

### 检查2：查看目录节点正文

```bash
# 查看有正文内容的节点（在postgres容器中）
psql -U llmapp -d llmapp -c "
SELECT 
    title,
    LENGTH(body_content) as content_length,
    SUBSTRING(body_content, 1, 50) as preview
FROM tender_directory_nodes
WHERE project_id = '<项目ID>'
AND is_active = TRUE
AND body_content IS NOT NULL
AND body_content != ''
ORDER BY order_no
LIMIT 10;
"
```

如果能看到节点有正文内容，说明范本填充成功。

### 检查3：前端验证

1. 打开项目，进入"步骤3：AI生成标书"
2. 在编辑器中查看目录节点
3. 点击"投标函"、"授权委托书"等节点
4. 应该能看到自动填充的范本内容

---

## 🛠️ 范本识别规则说明

系统使用以下规则自动识别范本：

### 识别特征（满分100分，≥40分标记为范本）

| 特征 | 得分 | 说明 |
|------|------|------|
| 包含"格式"、"范本"、"模板"等关键词 | 30分 | 标题或内容前200字 |
| 典型范本标题（投标函、授权委托书等） | 45分 | 单独就能通过阈值 |
| 5个以上填写下划线（____） | 20分 | 范本特征 |
| 3个以上空白框（[ ]、（ ）） | 15分 | 填写标识 |
| 包含"致："、"兹授权"等起始词 | 25分 | 范本开头 |
| 表格结构（├、│等字符） | 10分 | 格式化内容 |
| "格式"关键词出现≥3次 | 15分 | 格式范本章节 |
| 包含"填写"、"签字"、"盖章"等词≥3个 | 15分 | 填写说明 |

### 排除规则

以下内容**不会**被识别为范本：
- ❌ 合同条款、合同格式条款
- ❌ 评分标准、评分办法
- ❌ 技术规范、验收标准
- ❌ 违约责任

---

## 🔄 完整工作流程

```
┌─────────────────────┐
│ 1. 上传招标文档     │
│   （docx/pdf）      │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│ 2. 文档解析和分片   │
│   → 自动识别范本    │  ✨ 阶段1：轻量级规则识别
│   → 标记到meta_json │     （范本关键词、下划线、空白框等）
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│ 3. 生成投标目录     │
│   → LLM生成目录树   │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│ 4. 范本自动匹配     │  ✨ 阶段2：LLM精确匹配
│   → 查询标记的范本  │     （语义匹配目录节点与范本）
│   → LLM批量匹配     │
│   → 置信度≥0.9才应用│
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│ 5. 范本自动填充     │  ✨ 阶段3：自动填充正文
│   → 填充body_content│     （写入tender_directory_nodes表）
│   → 记录chunk来源   │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│ 6. 前端显示         │
│   → 节点展开显示正文│
│   → 用户可编辑      │
└─────────────────────┘
```

---

## 📊 技术细节

### 后端实现

**文件路径：**
- `backend/app/platform/ingest/v2_service.py` - 文档入库时识别范本
- `backend/app/works/tender/template_matcher.py` - 范本匹配和填充逻辑
- `backend/app/works/tender/extract_v2_service.py` - 集成到目录生成流程

**关键代码：**

```python
# 1. 入库时识别（v2_service.py:198-212）
template_info = identify_potential_template(
    chunk_text=chunk.text,
    chunk_meta=meta_json,
)
if template_info:
    meta_json.update(template_info)

# 2. 目录生成时匹配（extract_v2_service.py:806-848）
if enable_template_matching:
    match_result = await match_templates_to_nodes(...)
    fill_result = await auto_fill_template_bodies(...)

# 3. LLM匹配（template_matcher.py:139-232）
matches = await _batch_match_with_llm(
    target_nodes=L2/L3节点,
    template_chunks=标记的范本chunks,
    llm=llm,
)
```

### 数据库结构

**doc_segments 表**（存储文档分片）
```sql
meta_json->>'is_potential_template' = 'true'  -- 范本标记
meta_json->>'template_score'                  -- 识别分数
meta_json->>'template_hints'                  -- 识别特征
```

**tender_directory_nodes 表**（存储目录节点）
```sql
body_content         -- 范本正文（自动填充）
source_chunk_ids     -- 来源chunk ID（追溯）
```

---

## ❓ 常见问题

### Q1: 修复后仍然看不到范本？

**A:** 需要重新生成目录。范本匹配和填充是在目录生成时执行的，修复标记后必须重新生成。

### Q2: 某些范本没有被识别？

**A:** 可能是识别分数不够。检查：
1. 范本是否有明显的特征词（格式、范本、模板）
2. 是否有填写标识（下划线、空白框）
3. 是否被排除规则误伤（如包含"合同条款"）

可以在诊断脚本中查看具体的识别分数。

### Q3: 可以自定义识别规则吗？

**A:** 可以。编辑 `backend/app/works/tender/template_matcher.py`：

```python
# 第45-48行：添加识别关键词
template_keywords = [
    "格式", "范本", "模板", "样表", "样式", "参考格式",
    "标准格式", "填写说明", "附表", "附件表",
    "你的自定义关键词"  # 添加在这里
]

# 第126行：调整识别阈值
if template_score >= 40:  # 可以降低阈值（如35）识别更多范本
```

### Q4: 范本匹配置信度太低？

**A:** LLM匹配时使用0.9的置信度阈值（90%确定才应用）。如果需要调整：

编辑 `backend/app/works/tender/template_matcher.py` 第343行：

```python
if match.get("confidence", 0) < 0.9:  # 可以降低到0.8
    continue
```

### Q5: 新上传的文档也没有范本？

**A:** 检查文档入库服务是否正常工作：

```bash
# 查看入库日志
tail -f /app/logs/ingest.log | grep template

# 应该能看到类似的日志：
# IngestV2: Identified potential template in chunk 15 (score=75)
```

---

## 📞 技术支持

如果问题仍未解决，请收集以下信息：

1. 诊断报告输出
2. 项目ID
3. 招标文档文件名
4. `/app/tender_service_debug.log` 中的相关日志

然后联系开发团队进行深入排查。

---

## 🎉 成功标志

修复成功后，您应该看到：

- ✅ 诊断报告显示"所有项目的范本功能正常"
- ✅ 目录节点有 `body_content` 字段内容
- ✅ 前端编辑器中节点展开后显示范本内容
- ✅ 日志中有 "Template auto-fill done - X/Y nodes filled"

祝您使用顺利！🚀

