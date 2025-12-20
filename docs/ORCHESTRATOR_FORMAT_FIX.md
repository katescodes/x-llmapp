# 编排器 KeyError 修复说明

## 问题描述

**症状**：
```
orchestrator_meta.error: KeyError "'\n  \"intent\"'"
```

**根本原因**：

Python 的 `.format()` 方法会将字符串中的花括号 `{}` 视为占位符。当 Prompt 模板包含 JSON 示例时：

```python
EXTRACTOR_PROMPT = """
...
**必须输出的 JSON 格式**：
```json
{
  "intent": "information",  # ❌ 这里的 { 和 } 会被 .format() 解析
  "goal": "...",
  ...
}
```
...
用户输入：{user_message}  # ✅ 这是合法的占位符
""".strip()

# 调用 .format() 时
prompt = EXTRACTOR_PROMPT.format(
    user_message="什么是 Docker？",
    ui_detail_level="normal",
    history_text=""
)
# ❌ Python 会尝试解析 JSON 示例中的 { "intent": "information" }
# ❌ 导致 KeyError: '\n  "intent"'
```

## 已修复的文件

### 1. `backend/app/services/orchestrator/orchestrator_service.py`

**修复前**：使用 `.format()` 方法

```python
# ❌ 错误做法
prompt = EXTRACTOR_PROMPT.format(
    user_message=user_message,
    ui_detail_level=final_ui_level,
    history_text=history_text,
)
```

**修复后**：使用字符串拼接

```python
# ✅ 正确做法
prompt = EXTRACTOR_PROMPT + f"""

用户输入：{user_message}

UI详尽度设置：{final_ui_level}

历史对话：
{history_text}

输出JSON：
"""
```

**修复的三个方法**：

1. `extract_requirements()` - 需求抽取（第 82 行）
2. `generate_modular_answer()` - 模块化答案生成（第 168 行）
3. `repair_structure()` - 结构修复（第 222 行）

### 2. `backend/app/services/orchestrator/prompts.py`

**修改**：将 Prompt 模板末尾的占位符部分移除，改为在调用时动态拼接

**修改的三个 Prompt**：

1. `EXTRACTOR_PROMPT` - 移除末尾的 `{user_message}` 等占位符
2. `MODULAR_SYSTEM_PROMPT` - 移除末尾的 `{user_message}` 等占位符
3. `REPAIR_PROMPT` - 移除末尾的 `{raw_answer}` 等占位符

### 3. 增强的异常处理

**添加**：在 `extract_requirements()` 中增加完整堆栈日志

```python
except Exception as exc:
    logger.exception("[orchestrator] extractor failed")  # 完整堆栈
    logger.error(f"Extract requirements failed: {exc}", exc_info=True)
    return self._build_default_requirements(user_message, final_ui_level)
```

## 技术说明

### 为什么会有这个问题？

Python 的 `.format()` 方法使用花括号作为占位符：

```python
template = "Hello {name}, you are {age} years old"
result = template.format(name="Alice", age=30)
# 输出：Hello Alice, you are 30 years old
```

但是，如果字符串中包含 **非占位符** 的花括号（如 JSON），就会出错：

```python
template = """
Output JSON:
{
  "name": "{name}",
  "age": {age}
}
"""
result = template.format(name="Alice", age=30)
# ❌ KeyError: '\n  "name"'
# Python 认为 { "name": ... } 是一个占位符
```

### 两种解决方案对比

#### 方案 A：不使用 .format()（本次采用）

**优点**：
- 简单直接，不需要修改 Prompt 模板中的所有花括号
- 更易维护，新增 JSON 示例时不会出错
- 性能略好（少一次 format 解析）

**缺点**：
- 需要在调用时手动拼接字符串

**示例**：

```python
# Prompt 模板（保持 JSON 示例不变）
PROMPT = """
Output JSON:
{
  "intent": "information"
}

Now analyze:
"""

# 调用时拼接
prompt = PROMPT + f"""
User input: {user_message}
"""
```

#### 方案 B：双花括号转义（未采用）

**优点**：
- 仍可使用 `.format()` 方法
- 调用代码不需要修改

**缺点**：
- 需要修改 Prompt 模板中的 **所有** 花括号
- 容易遗漏，维护困难
- Prompt 可读性下降

**示例**：

```python
# Prompt 模板（所有花括号需要转义）
PROMPT = """
Output JSON:
{{
  "intent": "information",
  "goal": "{{goal}}"
}}

User input: {user_message}
"""

# 调用
prompt = PROMPT.format(user_message="...", goal="...")
# 输出：{ "intent": "information", "goal": "..." }
```

## 验证方法

### 1. 检查后端日志

```bash
cd /aidata/x-llmapp1
docker-compose build backend
docker-compose restart backend
docker-compose logs -f backend | grep orchestrator
```

**修复前**（错误日志）：

```
ERROR: [orchestrator] extractor failed
ERROR: Extract requirements failed: KeyError "'\n  \"intent\"'"
INFO: [orchestrator] FINAL RESPONSE: sections=0 followups=0 meta_used=False
```

**修复后**（成功日志）：

```
INFO: [orchestrator] req enable=True mode=normal detail=normal
INFO: Using orchestrator for answer generation
INFO: Orchestrator: Extracting requirements
INFO: Requirements extracted: intent=information, detail_level=normal, modules=['align_summary', 'core_answer', ...]
INFO: [orchestrator] SUCCESS: sections=5 followups=2 meta_used=True
INFO: [orchestrator] FINAL RESPONSE: sections=5 followups=2 meta_used=True
```

### 2. 检查 Network 响应

**修复前**：

```json
{
  "orchestrator_meta": {
    "enabled": true,
    "used": false,
    "error": "KeyError \"'\\n  \\\"intent\\\"'\""
  },
  "sections": null,
  "followups": null
}
```

**修复后**：

```json
{
  "orchestrator_meta": {
    "enabled": true,
    "used": true,
    "intent": "information",
    "detail_level": "normal",
    "modules": ["align_summary", "core_answer", "concepts", "next_steps"]
  },
  "sections": [
    {"id": "align_summary", "title": "理解确认", ...},
    {"id": "core_answer", "title": "核心答案", ...}
  ],
  "followups": ["问题1", "问题2"]
}
```

## 测试用例

### 用例 1：基本功能测试

**请求**：
```json
{
  "message": "什么是 Docker？",
  "mode": "normal",
  "enable_orchestrator": true,
  "detail_level": "normal"
}
```

**预期**：
- ✅ `orchestrator_meta.used` = `true`
- ✅ `orchestrator_meta.error` 不存在
- ✅ `sections` 长度 >= 2
- ✅ `followups` 可能有 0-3 个问题

### 用例 2：包含复杂 JSON 的需求

**请求**：
```json
{
  "message": "比较 PostgreSQL 和 MySQL 的性能差异",
  "mode": "normal",
  "enable_orchestrator": true,
  "detail_level": "detailed"
}
```

**预期**：
- ✅ `orchestrator_meta.used` = `true`
- ✅ `orchestrator_meta.intent` = `"decision"` 或 `"information"`
- ✅ `sections` 包含 "对比矩阵" 模块
- ✅ 无 KeyError

### 用例 3：错误回退测试

**模拟**：LLM 返回非 JSON 格式

**预期**：
- ✅ 回退到默认 RequirementJSON
- ✅ `orchestrator_meta.used` = `true`（使用默认配置）
- ✅ `sections` 至少有 2 个（align_summary, core_answer）
- ✅ 日志记录异常但不崩溃

## 常见问题

### Q1: 为什么不用 f-string 而要字符串拼接？

**A**: 其实我们**就是用的 f-string**！

```python
prompt = EXTRACTOR_PROMPT + f"""
用户输入：{user_message}
"""
```

这里的 `f"""..."""` 就是 f-string，只是我们把它和 Prompt 模板用 `+` 拼接起来，而不是对 Prompt 模板本身使用 `.format()`。

### Q2: Prompt 模板中仍然可以包含花括号吗？

**A**: 可以！现在 Prompt 模板是纯字符串常量，不会被 `.format()` 解析，所以 JSON 示例中的花括号完全没问题。

```python
PROMPT = """
Output JSON:
{
  "intent": "information"  # ✅ 完全没问题
}
"""
```

### Q3: 如果未来需要在 Prompt 模板中添加更多占位符怎么办？

**A**: 有两种方式：

**方式 1**（推荐）：继续在调用时拼接

```python
prompt = BASE_PROMPT + f"""
Field 1: {value1}
Field 2: {value2}
"""
```

**方式 2**：使用 `string.Template`

```python
from string import Template

PROMPT = Template("""
Output JSON: { "key": "value" }
User input: $user_message
""")

prompt = PROMPT.substitute(user_message="...")
```

## 总结

✅ **问题**：`.format()` 方法会解析 JSON 示例中的花括号，导致 KeyError

✅ **修复**：
- 不再对包含 JSON 的 Prompt 模板使用 `.format()`
- 改为字符串拼接（使用 `+` 和 f-string）
- 增强异常日志，便于排查问题

✅ **影响范围**：
- `orchestrator_service.py`：3 个方法修改
- `prompts.py`：3 个 Prompt 模板修改
- 无需修改调用方代码（chat.py）

✅ **验证**：
- 后端日志无 KeyError
- `orchestrator_meta.used` = `true`
- `sections` 正常返回

---

**修改日期**：2025-12-17  
**修复类型**：Critical Bug Fix  
**影响范围**：编排器核心功能

