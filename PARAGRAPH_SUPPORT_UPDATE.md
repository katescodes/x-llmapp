# PDF语义搜索优化 - 支持文本型内容

## 🎯 问题描述

**用户反馈**: "投标函"的内容不是表格，而是一段文本，但系统将包含了"投标函"文字的其余表格放进来了

**根本原因**: 
- 之前的语义搜索**只支持`table`类型**
- 对于文本型内容（如投标函、承诺书、声明等），系统会错误地匹配到包含该关键词的表格
- 缺少内容类型匹配机制

---

## ✅ 解决方案

### 核心改进

1. **支持`paragraph`类型** ✅
   - 扩展语义搜索，同时支持`table`和`paragraph`
   - 根据节点标题自动判断期望的内容类型

2. **智能类型推断** ✅
   - 文本型指示词：函、声明、承诺、说明、简介、概述、方案、计划
   - 表格型：默认（报价、清单、一览表等）

3. **类型匹配加成** ✅
   - 文本型节点匹配到paragraph：+15%得分
   - 表格型节点匹配到table：+5%得分

4. **内容质量过滤** ✅
   - 表格：跳过内容少于10字符的（避免只是标题行）
   - 段落：跳过少于20字符的（避免短标题）

---

## 🔧 技术实现

### 修改文件

**文件**: `backend/app/services/fragment/semantic_matcher.py`

### 关键代码

#### 1. 类型推断逻辑

```python
# 根据标题判断期望的内容类型
text_type_indicators = ["函", "声明", "承诺", "说明", "简介", "概述", "方案", "计划"]
prefer_text = any(indicator in node_title for indicator in text_type_indicators)
```

#### 2. 扩展搜索支持

```python
for idx, item in enumerate(pdf_items):
    item_type = item.get("type")
    
    # ✅ 支持table和paragraph两种类型
    if item_type == "table":
        table_data = item.get("tableData", [])
        if not table_data or len(table_data) < 2:
            continue
        
        # 提取表格内容文本
        content_text = "\n".join([" ".join(row) for row in table_data])
        
        # 跳过内容过少的表格（可能只是标题行）
        if len(content_text.strip()) < 10:
            continue
            
    elif item_type == "paragraph":
        text = item.get("text", "")
        if not text or len(text.strip()) < 20:  # 段落至少20字符
            continue
        content_text = text
    else:
        continue
```

#### 3. 类型匹配加成

```python
# 内容类型匹配度加成
type_bonus = 0.0
if prefer_text and item_type == "paragraph":
    type_bonus = 0.15  # 文本类型节点匹配到paragraph，加15%
elif not prefer_text and item_type == "table":
    type_bonus = 0.05  # 表格类型节点匹配到table，加5%

initial_score += type_bonus
```

#### 4. LLM验证Prompt优化

```python
# 根据item类型调整Prompt描述
item_type = table_item.get("type", "table")
if item_type == "paragraph":
    content_desc = "文本段落"
    type_check = "文本内容是否符合该类型文档的特征（如正文、声明等）"
else:
    content_desc = "表格"
    type_check = "表格内容是否包含该类型文档的典型字段"

prompt = f"""任务：判断该{content_desc}是否为"{node_title}"

{content_desc}上下文（包含前后内容）：
{context[:1000]}

请根据以下标准判断：
1. {type_check}
2. 前后的内容是否提到相关标题
3. 内容的完整性和实质性（避免只是标题行或目录项）
"""
```

---

## 📊 预期效果

### 修改前

| 节点 | 匹配类型 | 匹配内容 | 问题 |
|-----|---------|---------|------|
| 投标函 | table | 包含"投标函"字样的表格 | ❌ 错误 |

### 修改后

| 节点 | 匹配类型 | 匹配内容 | 结果 |
|-----|---------|---------|------|
| 投标函 | **paragraph** | 投标函的文本正文 | ✅ 正确 |
| 开标一览表 | table | 开标一览表表格 | ✅ 正确 |

---

## 🎯 文本型内容识别列表

以下节点将优先匹配`paragraph`类型：

1. **投标函** ✅
   - 关键词：函、承诺、签字、盖章
   - 内容：一段文字正文

2. **承诺书/声明** ✅
   - 关键词：承诺、声明、保证
   - 内容：文字说明

3. **技术方案** ✅
   - 关键词：方案、说明、计划
   - 内容：多段文字描述

4. **项目简介/概述** ✅
   - 关键词：简介、概述、说明
   - 内容：文字叙述

---

## 🧪 测试建议

### 测试用例

1. **投标函**（文本型）
   - 应匹配到：包含"致：XXX"、"我方承诺"等文字的段落
   - 不应匹配到：目录中的"投标函"表格行

2. **开标一览表**（表格型）
   - 应匹配到：包含"总投标价"、"大写/小写"的表格
   - 不应匹配到：只有标题的表格行

3. **技术方案**（文本型）
   - 应匹配到：多段技术描述文字
   - 不应匹配到：技术参数表格

---

## 📝 验证步骤

1. 在界面点击"自动填充范本"
2. 等待完成后，点击"投标函"节点
3. 查看内容：
   - ✅ 应该是完整的文字段落
   - ✅ 包含"致：XXX"、"我方承诺"等投标函典型内容
   - ❌ 不应该是表格

4. 查看后端日志：
```bash
docker-compose logs backend --tail=50 | grep "投标函"
```

预期日志：
```
[attach_from_pdf_semantic] Filling '投标函' (confidence=0.XX, llm=True, type=paragraph)
```

注意`type=paragraph`而不是`type=table`。

---

## 🔄 兼容性

- ✅ 向后兼容：所有表格型内容仍然正常工作
- ✅ 自动判断：无需手动配置，系统自动识别类型
- ✅ LLM验证：仍然使用LLM验证匹配准确性

---

## 📚 相关文档

- **PDF语义搜索总结**: `PDF_SEMANTIC_SEARCH_FINAL.md`
- **实施细节**: `PLAN_A_C_IMPLEMENTATION.md`
- **修复日志**: `HOTFIX_2025-12-26.md`

---

**部署时间**: 2025-12-26 09:39 UTC+8  
**状态**: ✅ 已部署  
**影响范围**: 所有PDF招标文件的范本自动填充

