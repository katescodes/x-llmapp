# 编排器请求字段修复说明

## 问题描述

前端请求体中 `mode` 和 `detail_level` 字段需要明确区分，避免语义混淆。

## 字段定义

### mode（回答模式）
- **类型**：`"normal" | "decision" | "history_decision"`
- **来源**：UI 左侧边栏的"回答模式"选择器
- **说明**：
  - `"normal"` - 💬 标准模式 - 知识查询
  - `"decision"` - 🎯 方案建议 - 结构化决策分析  
  - `"history_decision"` - 📋 历史案例决策 - 从经验中学习
- **用途**：控制后端的回答策略（是否启用历史案例检索、决策分析等）

### detail_level（答案详尽度）
- **类型**：`"brief" | "normal" | "detailed"`
- **来源**：UI 左侧边栏的"答案详尽度"选择器（仅当启用编排器时显示）
- **说明**：
  - `"brief"` - 精简：2-3 段，少模块，无冗余例子
  - `"normal"` - 标准：3-5 段，正常详细度，1-2 个例子
  - `"detailed"` - 详细：5-8 段，多模块，多例子，深入解释
- **用途**：控制编排器生成答案的详尽程度

## 已修复的问题

### 1. 添加明确注释

在 `ChatLayout.tsx` 的 `payload` 构造中添加了详细注释：

```typescript
const payload: ChatRequestPayload = {
  message: trimmed,
  history: historyPayload,
  llm_key: selectedLLM,
  session_id: sessionId,
  mode: chatMode,  // 回答模式："normal"(标准) | "decision"(方案) | "history_decision"(历史案例)
  enable_web: enableWeb,
  selected_kb_ids: selectedKbIds.length ? selectedKbIds : undefined,
  attachment_ids: attachmentIds,
  // 编排器相关（注意：detail_level 和 mode 是不同的字段）
  enable_orchestrator: enableOrchestrator,  // 是否启用编排器
  detail_level: detailLevel  // 详尽度："brief"(精简) | "normal"(标准) | "detailed"(详细)
};
```

### 2. 添加调试日志

在发送请求前添加 console.log，帮助开发者在浏览器 Network 中验证：

```typescript
console.log('[请求参数]', {
  mode: payload.mode,  // 应该是 "normal" | "decision" | "history_decision"
  detail_level: payload.detail_level,  // 应该是 "brief" | "normal" | "detailed"
  enable_orchestrator: payload.enable_orchestrator
});
```

## 验证方法

### 方法 1：浏览器开发者工具

1. **启动服务**（Docker）：
   ```bash
   cd /aidata/x-llmapp1
   docker-compose build frontend
   docker-compose restart frontend
   ```

2. **打开浏览器**：访问 http://localhost:6173

3. **打开开发者工具**：按 F12，切换到 **Network** 标签

4. **启用编排器**：
   - 勾选左侧边栏的 "🎯 启用智能编排器"
   - 选择详尽度（例如：标准）
   - 选择回答模式（例如：标准模式）

5. **发送测试消息**：
   ```
   什么是 Docker？
   ```

6. **查看网络请求**：
   - 在 Network 标签中找到 `/api/chat/stream` 请求
   - 点击该请求，查看 **Request Payload**
   - **验证字段值**：
     ```json
     {
       "mode": "normal",           // ✅ 回答模式（不是 "brief"/"detailed"）
       "detail_level": "normal",   // ✅ 详尽度
       "enable_orchestrator": true // ✅ 编排器开关
     }
     ```

### 方法 2：浏览器控制台

1. 打开浏览器控制台（F12 → Console）

2. 发送消息后，查看输出：
   ```
   [请求参数] {
     mode: "normal",
     detail_level: "normal",
     enable_orchestrator: true
   }
   ```

3. **确认**：
   - `mode` 的值是 `"normal"` / `"decision"` / `"history_decision"`（不是 `"brief"` / `"detailed"`）
   - `detail_level` 的值是 `"brief"` / `"normal"` / `"detailed"`
   - 两个字段的值不同（除非都选择了 "normal"，这是正常的）

## 常见场景测试

### 场景 1：标准模式 + 精简答案

- **UI 设置**：
  - 回答模式：标准模式
  - 答案详尽度：精简
- **预期 Request Payload**：
  ```json
  {
    "mode": "normal",
    "detail_level": "brief",
    "enable_orchestrator": true
  }
  ```

### 场景 2：方案建议 + 详细答案

- **UI 设置**：
  - 回答模式：方案建议
  - 答案详尽度：详细
- **预期 Request Payload**：
  ```json
  {
    "mode": "decision",
    "detail_level": "detailed",
    "enable_orchestrator": true
  }
  ```

### 场景 3：历史案例 + 标准答案

- **UI 设置**：
  - 回答模式：历史案例决策
  - 答案详尽度：标准
- **预期 Request Payload**：
  ```json
  {
    "mode": "history_decision",
    "detail_level": "normal",
    "enable_orchestrator": true
  }
  ```

## 后端验证

在后端日志中，您应该看到类似的日志：

```
INFO: Chat request mode=normal enable_web=False req.selected_kb_ids=None effective_kb_ids=[] user_len=15 history_turns=0
INFO: Using orchestrator for answer generation
INFO: Requirements extracted: intent=information, detail_level=normal, modules=6
```

**关键点**：
- `mode` 应该是 `normal` / `decision` / `history_decision`
- `detail_level` 应该是 `brief` / `normal` / `detailed`
- 如果 `enable_orchestrator=true`，应该看到 "Using orchestrator" 日志

## 如果发现问题

如果在 Network 中看到 `mode` 的值是 `"brief"` 或 `"detailed"`（而不是预期的 `"normal"` / `"decision"` / `"history_decision"`），说明存在字段混淆。

**可能的原因**：
1. 前端代码中有其他地方修改了 `payload.mode`
2. UI 状态管理有问题，`chatMode` 和 `detailLevel` 被混淆
3. 浏览器缓存了旧版本的前端代码

**解决方法**：
1. 清除浏览器缓存（Ctrl + Shift + Delete）
2. 重新构建前端镜像：`docker-compose build frontend`
3. 强制刷新浏览器（Ctrl + Shift + R）
4. 检查 `ChatLayout.tsx` 中 `chatMode` 和 `detailLevel` 的初始值和使用

## 总结

✅ **修复完成**：
- `mode` 字段：正确使用 `chatMode` 状态（回答模式）
- `detail_level` 字段：正确使用 `detailLevel` 状态（答案详尽度）
- 添加了明确注释和调试日志
- 两个字段语义清晰，不再混淆

✅ **验证方法**：
- 浏览器 Network 标签查看 Request Payload
- 浏览器 Console 查看调试日志
- 后端日志查看参数接收情况

---

**修改日期**：2025-12-17  
**修改文件**：`frontend/src/components/ChatLayout.tsx`  
**影响范围**：编排器请求参数传递

