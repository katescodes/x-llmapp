# 格式范本自动填充功能 - 实现说明

## ✅ 已完成部分

### 1. 核心模块 `/backend/app/works/tender/template_matcher.py`

#### **阶段1：轻量级规则识别（待集成）**
```python
identify_potential_template(chunk_text, chunk_meta)
```
- 识别规则：关键词（"格式"、"范本"）+ 内容特征（下划线、空白框）
- 输出：`{is_potential_template: true, template_score: 75}`
- **状态**：代码已完成，需要在文档分片流程中调用（待实现）

#### **阶段2：LLM精确匹配（已完成）**
```python
match_templates_to_nodes(nodes, project_id, pool, llm)
```
- 从数据库查询标记为`potential_template`的chunks
- 批量调用LLM判断节点与范本的匹配关系
- 返回置信度 ≥ 0.7的匹配结果

#### **阶段3：自动填充节点正文（已完成）**
```python
auto_fill_template_bodies(matches, project_id, pool)
```
- 将匹配的范本文本填充到`tender_directory_nodes.body_content`
- 记录`source_chunk_ids`以便追溯

---

## 📊 当前工作流程

```
目录生成完成
  ↓
查询数据库中 meta_json->>'is_potential_template' = 'true' 的chunks
  ↓
【当前限制】如果没有预先标记的chunks，则跳过匹配 ⚠️
  ↓
LLM批量匹配节点与范本
  ↓
自动填充节点正文
  ↓
前端显示统计："📄 格式范本填充：自动填充了X个节点"
```

---

## ⚠️ 当前限制与解决方案

### 限制：阶段1未集成到文档分片流程

**问题：**
- `identify_potential_template()` 函数已实现，但未在文档上传/分片时调用
- 导致数据库中没有标记为`is_potential_template=true`的chunks
- 匹配功能无法找到候选范本

**影响：**
- 现在生成目录后，范本填充功能会显示："未发现可匹配的格式范本"

**解决方案A（临时）：手动标记现有项目的范本**
```python
# 临时脚本：为现有项目标记范本chunks
import psycopg
from template_matcher import identify_potential_template

conn = psycopg.connect("...")
with conn.cursor() as cur:
    # 获取所有招标文档的chunks
    cur.execute("SELECT id, content_text, meta_json FROM doc_segments WHERE ...")
    
    for row in cur.fetchall():
        chunk_id, text, meta = row
        result = identify_potential_template(text, meta or {})
        
        if result:
            # 更新meta_json
            meta.update(result)
            cur.execute(
                "UPDATE doc_segments SET meta_json = %s WHERE id = %s",
                [meta, chunk_id]
            )
    
    conn.commit()
```

**解决方案B（长期）：集成到文档处理流程**
需要找到文档分片的代码位置（可能在`/backend/app/platform/doc_processor/`），在分片时调用`identify_potential_template()`。

---

## 🔧 如何启用功能

### 方式1：为现有项目手动标记范本（快速测试）

运行临时标记脚本（需要实现）：
```bash
python scripts/mark_existing_templates.py --project-id <项目ID>
```

### 方式2：重新上传文档（集成后）

等待阶段1集成到文档处理流程后，重新上传招标书，系统会自动标记范本chunks。

---

## 📈 预期效果（集成后）

```
商务标
  ├─ 投标函及投标函附录
  │   └─ 正文：✅ 已自动填充格式范本（第15页）
  ├─ 授权委托书
  │   └─ 正文：✅ 已自动填充格式范本（第18页）
  ├─ 项目管理机构
      └─ 正文：✅ 已自动填充格式范本（第22页）

技术标
  ├─ 技术方案
      └─ 正文：（无范本，需手动填写）
```

**前端显示：**
```
📄 格式范本填充：自动填充了 3 个节点的格式范本 (投标函、授权书、项目管理机构)
```

---

## 🎛️ 配置选项

### 禁用范本匹配
```python
# 在 extract_v2_service.py
enable_template_matching=False
```

### 调整置信度阈值
```python
# 在 template_matcher.py 的 _match_batch()
if match.get("confidence", 0) < 0.7:  # 默认0.7，可调整为0.8
    continue
```

### 调整匹配批量大小
```python
# 在 template_matcher.py
batch_size = 3  # 默认5，减少可降低单次Token消耗
```

---

## 📋 TODO（待实现）

### 高优先级
- [ ] **阶段1集成**：在文档分片流程中调用`identify_potential_template()`
  - 找到分片代码位置
  - 添加轻量级识别逻辑
  - 测试并验证meta_json更新

### 中优先级
- [ ] 为现有项目创建临时标记脚本
- [ ] 前端增加"范本管理"UI（查看/编辑已匹配的范本）
- [ ] 用户手动调整匹配关系的界面

### 低优先级
- [ ] 范本填充后的预览功能
- [ ] 批量导出已填充的节点正文
- [ ] 范本填充历史记录

---

## 🧪 测试方式

### 当前可测试内容
1. LLM匹配逻辑（需要先手动标记chunks）
2. 自动填充功能
3. 前端统计显示

### 完整功能测试（阶段1集成后）
1. 上传包含格式范本的招标书
2. 生成目录
3. 查看目录工具栏底部统计
4. 展开目录，检查节点正文是否已填充

---

## 💡 优化建议

### 提升匹配准确率
1. **收集训练数据**：标注真实的匹配案例，微调LLM
2. **多轮对话**：对低置信度匹配，让LLM二次确认
3. **用户反馈**：记录用户的调整，持续优化匹配规则

### 降低成本
1. **缓存匹配结果**：同一招标书的范本匹配结果可复用
2. **增量匹配**：目录修改后，只匹配新增/变更的节点
3. **规则优先**：对常见范本（投标函、授权书）使用规则直接匹配

---

## 📞 联系与支持

如需启用此功能或遇到问题，请：
1. 检查数据库中是否有`is_potential_template=true`的chunks
2. 查看日志中`[TemplateMatcher]`相关输出
3. 确认LLM服务正常运行

**核心文件：**
- `/backend/app/works/tender/template_matcher.py` - 核心逻辑
- `/backend/app/works/tender/extract_v2_service.py` - 集成入口（第8步）
- `/frontend/src/components/tender/DirectoryToolbar.tsx` - 前端显示

