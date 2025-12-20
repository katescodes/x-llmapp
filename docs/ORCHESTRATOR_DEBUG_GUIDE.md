# 编排器调试与验证指南

## 问题背景

即使 `enable_orchestrator=true`，但 `sections/followups/orchestrator_meta` 仍为 `null` 或 `sections` 为空数组。

## 已修复的问题

### 1. 可观测性增强

**添加的日志**：

```python
# 请求入口
[orchestrator] req enable=True mode=normal detail=normal

# 编排器执行成功
[orchestrator] SUCCESS: sections=5 followups=2 meta_used=True

# 最终响应
[orchestrator] FINAL RESPONSE: sections=5 followups=2 meta_used=True meta_modules=['align_summary', 'core_answer', ...]
```

### 2. orchestrator_meta 始终有值

**修改前**：`orchestrator_meta` 可能为 `None`

**修改后**：始终包含以下字段（用于 Network 直接验证）

```python
orchestrator_meta = {
    "enabled": bool,        # 是否请求启用编排器
    "used": bool,           # 是否实际使用了编排器
    "mode": str,            # 回答模式
    "detail_level": str,    # 详尽度级别
    "modules": list,        # 生成的模块列表
    # 如果使用了编排器，还包含：
    "intent": str,          # 识别的意图
    "blueprint_modules": list,  # 蓝图模块
    "assumptions": list,    # 假设
    # 如果失败，包含：
    "error": str            # 错误信息（截断）
}
```

### 3. 错误处理改进

- 编排器失败时，`orchestrator_meta["used"]` 明确设为 `False`
- 记录错误信息到 `orchestrator_meta["error"]`（截断到 200 字符）

## 验证方法

### 方法 1：后端日志验证

1. **重启后端**（Docker）：
   ```bash
   cd /aidata/x-llmapp1
   docker-compose build backend
   docker-compose restart backend
   
   # 查看日志
   docker-compose logs -f backend
   ```

2. **发送测试请求**：
   - 启用编排器
   - 选择详尽度：标准
   - 输入：`什么是 Docker？`

3. **查看日志输出**（应包含以下内容）：

   ```log
   INFO: [orchestrator] req enable=True mode=normal detail=normal
   INFO: Using orchestrator for answer generation
   INFO: Orchestrator: Extracting requirements
   INFO: Requirements extracted: intent=information, detail_level=normal, modules=['align_summary', 'core_answer', ...]
   INFO: Orchestrator: Generating modular answer
   INFO: Orchestrator: Parsing sections from answer
   INFO: Orchestrator: Generated 5 sections
   INFO: [orchestrator] SUCCESS: sections=5 followups=2 meta_used=True
   INFO: [orchestrator] FINAL RESPONSE: sections=5 followups=2 meta_used=True meta_modules=['align_summary', 'core_answer', ...]
   ```

### 方法 2：浏览器 Network 验证

#### 非流式 `/api/chat`

1. **发送请求**（禁用流式）

2. **查看响应 JSON**：

   ```json
   {
     "answer": "完整答案文本...",
     "sources": [...],
     "sections": [
       {
         "id": "align_summary",
         "title": "理解确认",
         "markdown": "...",
         "collapsed": false
       },
       {
         "id": "core_answer",
         "title": "核心答案",
         "markdown": "...",
         "collapsed": false
       }
     ],
     "followups": [
       "你的使用场景是什么？",
       "需要与其他工具集成吗？"
     ],
     "orchestrator_meta": {
       "enabled": true,
       "used": true,
       "mode": "normal",
       "detail_level": "normal",
       "modules": ["align_summary", "core_answer", "concepts", "next_steps"],
       "intent": "information",
       "blueprint_modules": ["align_summary", "core_answer", ...],
       "assumptions": [...]
     }
   }
   ```

#### 流式 `/api/chat/stream`

1. **打开 Network 标签**，找到 `/api/chat/stream` 请求

2. **查看 SSE 事件流**：

   ```
   event: delta
   data: {"text": "## 理解确认\n\n你想..."}

   event: delta
   data: {"text": "了解 Docker 技术..."}

   ...

   event: result
   data: {
     "answer": "完整答案...",
     "sources": [...],
     "sections": [
       {"id": "align_summary", "title": "理解确认", ...},
       {"id": "core_answer", "title": "核心答案", ...}
     ],
     "followups": [...],
     "orchestrator_meta": {
       "enabled": true,
       "used": true,
       "mode": "normal",
       "detail_level": "normal",
       "modules": [...]
     }
   }
   ```

### 方法 3：浏览器 Console 验证

打开浏览器控制台（F12 → Console），查看调试输出：

```
[请求参数] {
  mode: "normal",
  detail_level: "normal",
  enable_orchestrator: true
}
```

## 问题排查清单

### ✅ 问题 1：sections 为 null

**原因**：编排器未执行或执行失败

**检查**：
1. 查看后端日志，是否有 `[orchestrator] req enable=True`
2. 是否有 `Using orchestrator for answer generation`
3. 是否有异常堆栈（`Orchestrator failed, fallback to normal mode`）

**解决**：
- 如果未执行：检查前端是否传递 `enable_orchestrator=true`
- 如果执行失败：查看异常信息，可能是 LLM 调用失败、JSON 解析失败等

### ✅ 问题 2：sections 为空数组 `[]`

**原因**：LLM 输出不符合预期格式（没有 `## 标题`）

**检查**：
1. 查看日志 `Orchestrator: Generated 0 sections`
2. 查看 `orchestrator_meta["modules"]` 是否有值

**解决**：
- 检查 LLM 模型质量（推荐 GPT-4、Claude、Qwen2.5、Llama3.1）
- 检查 `MODULAR_SYSTEM_PROMPT` 是否正确传递给 LLM
- 可以手动触发 `repair_structure`（目前未自动触发，需要在代码中添加）

### ✅ 问题 3：orchestrator_meta.used 为 false

**原因**：编排器未被实际使用

**检查**：
1. 查看 `orchestrator_meta["enabled"]` 是否为 `true`
2. 查看后端日志是否有 `Using orchestrator for answer generation`
3. 是否有 `fallback to normal mode` 日志

**解决**：
- 如果 `enabled=true` 但 `used=false`，说明编排器执行失败
- 查看 `orchestrator_meta["error"]` 字段，了解失败原因

### ✅ 问题 4：orchestrator_meta 完全为 null

**原因**：响应构造时没有传递 `orchestrator_meta`（已修复）

**检查**：
- 本次修复后，`orchestrator_meta` 应该始终有值
- 如果仍为 `null`，检查后端版本是否最新

## 常见场景测试

### 场景 1：标准模式 + 编排器

**请求**：
```json
{
  "message": "什么是 Kubernetes？",
  "mode": "normal",
  "enable_orchestrator": true,
  "detail_level": "normal"
}
```

**预期响应**：
- `orchestrator_meta.used` = `true`
- `sections` 长度 >= 2（至少包含 "理解确认" 和 "核心答案"）
- `followups` 可能为空或有 1-3 个问题

### 场景 2：未启用编排器

**请求**：
```json
{
  "message": "什么是 Docker？",
  "mode": "normal",
  "enable_orchestrator": false
}
```

**预期响应**：
- `orchestrator_meta.enabled` = `false`
- `orchestrator_meta.used` = `false`
- `sections` = `null`
- `followups` = `null`

### 场景 3：编排器失败回退

**模拟**：LLM 调用失败或超时

**预期响应**：
- `orchestrator_meta.enabled` = `true`
- `orchestrator_meta.used` = `false`
- `orchestrator_meta.error` = "LLM timeout..." （有错误信息）
- `sections` = `null`（回退到普通模式）
- `answer` 仍然正常返回（使用原有流程）

## 性能监控

### 关键指标

| 指标 | 预期值 | 说明 |
|------|--------|------|
| Extractor 耗时 | < 2 秒 | 需求抽取（非流式） |
| Answer 首 token | < 3 秒 | 流式输出首字到达 |
| Parse Sections 耗时 | < 0.1 秒 | 正则解析 |
| Repair 耗时 | < 3 秒 | 仅在 validate 失败时触发 |

### 日志监控关键字

搜索以下关键字快速定位问题：

```bash
# 编排器启用
grep "\[orchestrator\] req enable=True" backend.log

# 编排器成功
grep "\[orchestrator\] SUCCESS" backend.log

# 编排器失败
grep "Orchestrator failed" backend.log

# 最终响应
grep "\[orchestrator\] FINAL RESPONSE" backend.log
```

## 前端集成检查

### 检查点 1：请求体正确性

在 `ChatLayout.tsx` 中，`payload` 应包含：

```typescript
{
  mode: "normal",  // 不是 "brief" 或 "detailed"
  enable_orchestrator: true,
  detail_level: "normal"  // "brief" | "normal" | "detailed"
}
```

### 检查点 2：响应处理

在 `MessageList.tsx` 中，应正确处理 `sections`：

```typescript
{msg.sections && msg.sections.length > 0 ? (
  <ModularAnswer sections={msg.sections} followups={msg.followups} />
) : (
  <MessageBubble role={msg.role} content={msg.content} />
)}
```

### 检查点 3：类型定义

在 `types/index.ts` 中，`ChatResponsePayload` 应包含：

```typescript
interface ChatResponsePayload {
  answer: string;
  sections?: ChatSection[];
  followups?: string[];
  orchestrator_meta?: Record<string, any>;
}
```

## 总结

✅ **已修复**：
- `orchestrator_meta` 始终有值，包含 `enabled`、`used`、`mode`、`detail_level`、`modules` 字段
- 添加了完整的日志链路，便于追踪编排器执行状态
- 错误处理改进，失败时明确标记并记录错误信息

✅ **验证方式**：
- 后端日志：查看完整执行流程
- Network 标签：验证响应字段
- Console：查看前端请求参数

✅ **如果仍有问题**：
1. 检查后端日志，定位失败原因
2. 检查 `orchestrator_meta["error"]` 字段
3. 验证 LLM 模型配置是否正确
4. 查看 `MODULAR_SYSTEM_PROMPT` 是否生效

---

**修改日期**：2025-12-17  
**修改文件**：`backend/app/routers/chat.py`  
**影响范围**：编排器执行链路、可观测性、错误处理

