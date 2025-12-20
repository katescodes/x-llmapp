# 编排器默认启用 & 折叠效果移除

## 修复日期
2025-12-17

## 目标概述

1. **去掉前端"启用智能编排器"开关**：界面删除 + 状态删除
2. **编排器变成默认行为**：每次对话都执行意图识别 + 任务归类 + sections 返回
3. **去掉折叠效果**：sections 按顺序平铺展示，无交互

---

## A. 前端：移除"启用智能编排器"开关

### 1️⃣ 删除状态和 UI

**文件**: `frontend/src/components/ChatLayout.tsx`

#### 删除 enableOrchestrator 状态（第 84 行）

**修改前**：
```typescript
const [enableWeb, setEnableWeb] = useState(false);
const [chatMode, setChatMode] = useState<ChatMode>("normal");
// 编排器相关
const [enableOrchestrator, setEnableOrchestrator] = useState(false);
const [detailLevel, setDetailLevel] = useState<DetailLevel>("normal");
```

**修改后**：
```typescript
const [enableWeb, setEnableWeb] = useState(false);
const [chatMode, setChatMode] = useState<ChatMode>("normal");
// 编排器相关（编排器已默认启用，不再需要开关）
const [detailLevel, setDetailLevel] = useState<DetailLevel>("normal");
```

---

#### 删除开关 UI（第 554-567 行）

**删除的代码**：
```tsx
{/* 编排器配置 */}
<div className="sidebar-section">
  <label className="checkbox-option">
    <input
      type="checkbox"
      checked={enableOrchestrator}
      onChange={(e) => setEnableOrchestrator(e.target.checked)}
    />
    <span>🎯 启用智能编排器（实验性）</span>
  </label>
  <div className="sidebar-hint">
    开启后会提供：需求理解、模块化答案、详尽度控制、少追问、结构化渲染
  </div>
</div>
```

**结果**：左侧边栏不再显示"启用智能编排器"开关

---

#### 详尽度选择器移出条件渲染（第 569 行）

**修改前**：
```tsx
{enableOrchestrator && (
  <div className="sidebar-section">
    <div className="sidebar-label">答案详尽度：</div>
    <!-- 详尽度选择器 -->
  </div>
)}
```

**修改后**：
```tsx
{/* 答案详尽度配置（编排器已默认启用，直接显示）*/}
<div className="sidebar-section">
  <div className="sidebar-label">答案详尽度：</div>
  <!-- 详尽度选择器 -->
</div>
```

**结果**：详尽度选择器始终可见，不再依赖开关

---

### 2️⃣ 固定 Payload 为 `enable_orchestrator: true`

**文件**: `frontend/src/components/ChatLayout.tsx` (第 267 行)

**修改前**：
```typescript
const payload: ChatRequestPayload = {
  // ...
  enable_orchestrator: enableOrchestrator,  // 从 UI 状态读取
  detail_level: detailLevel
};
```

**修改后**：
```typescript
const payload: ChatRequestPayload = {
  // ...
  enable_orchestrator: true,  // 固定为 true，编排器默认启用
  detail_level: detailLevel
};
```

**结果**：
- ✅ 每次请求都发送 `enable_orchestrator: true`
- ✅ 不再依赖 UI 状态

---

## B. 后端：编排器默认启用

### 1️⃣ 修改 Schema 默认值

**文件**: `backend/app/schemas/chat.py` (第 41 行)

**修改前**：
```python
class ChatRequest(BaseModel):
    # ...
    enable_orchestrator: Optional[bool] = None  # 默认 False
    detail_level: Optional[DetailLevelType] = None
```

**修改后**：
```python
class ChatRequest(BaseModel):
    # ...
    enable_orchestrator: Optional[bool] = True  # 默认 True
    detail_level: Optional[DetailLevelType] = None
```

**说明**：
- ✅ API 层面默认启用编排器
- ✅ 即使前端未传 `enable_orchestrator`，后端也默认为 `True`

---

### 2️⃣ 修改路由逻辑

**文件**: `backend/app/routers/chat.py` (第 894 行)

**修改前**：
```python
# ==================== 编排器集成 ====================
use_orchestrator = req.enable_orchestrator or False

if use_orchestrator:
```

**修改后**：
```python
# ==================== 编排器集成 ====================
# 编排器默认启用（除非明确设置为 False）
use_orchestrator = req.enable_orchestrator if req.enable_orchestrator is not None else True

if use_orchestrator:
```

**逻辑变化**：
| 情况 | 修改前 | 修改后 |
|------|--------|--------|
| `enable_orchestrator=True` | ✅ 使用 | ✅ 使用 |
| `enable_orchestrator=False` | ❌ 不使用 | ❌ 不使用 |
| `enable_orchestrator=None` | ❌ 不使用 | ✅ 使用（默认）|

**结果**：
- ✅ "normal" 模式也走编排器
- ✅ 所有模式默认返回 `sections/followups/orchestrator_meta`

---

## C. 前端：去掉折叠效果，改为平铺展示

### 完全重写 `ModularAnswer.tsx`

**文件**: `frontend/src/components/ModularAnswer.tsx`

#### 删除的功能

**1. 删除折叠状态管理**：
```typescript
// ❌ 删除
const [collapsedState, setCollapsedState] = useState<Record<string, boolean>>(...);
const toggleSection = (sectionId: string) => { ... };
```

**2. 删除折叠交互**：
```tsx
{/* ❌ 删除：可点击的标题 */}
<div onClick={() => toggleSection(section.id)}>
  <h3>{section.title}</h3>
  <span>▼</span> {/* 删除箭头 */}
</div>

{/* ❌ 删除：条件渲染 */}
{!isCollapsed && (
  <div className="section-content">
    <ReactMarkdown>{section.markdown}</ReactMarkdown>
  </div>
)}
```

---

#### 新增的平铺展示

**修改后的结构**：
```tsx
<div className="modular-answer">
  {sections.map((section) => (
    <div key={section.id} className="answer-section">
      {/* 标题：纯展示，无交互 */}
      <h3>{section.title}</h3>

      {/* 内容：直接展示，无条件渲染 */}
      <div className="section-content">
        <ReactMarkdown>{section.markdown}</ReactMarkdown>
      </div>
    </div>
  ))}

  {/* followups 保持不变 */}
</div>
```

**关键变化**：
- ✅ 删除 `onClick` 事件
- ✅ 删除折叠箭头 `▼`
- ✅ 删除 `isCollapsed` 条件
- ✅ 删除 `section.collapsed` 的读取
- ✅ 所有 sections 按顺序平铺展示
- ✅ 样式适配暗色主题

---

#### 样式更新

**标题样式**（无边框卡片，改为简单分隔线）：
```tsx
<h3
  style={{
    margin: '0 0 0.75rem 0',
    fontSize: '1.125rem',
    fontWeight: 600,
    color: '#e5e7eb',
    borderBottom: '2px solid rgba(148, 163, 184, 0.3)',
    paddingBottom: '0.5rem',
  }}
>
  {section.title}
</h3>
```

**内容样式**（去掉背景色和边框）：
```tsx
<div
  className="section-content"
  style={{
    paddingLeft: '0.5rem', // 轻微缩进
  }}
>
  <ReactMarkdown ...>
    {section.markdown}
  </ReactMarkdown>
</div>
```

**Markdown 元素颜色**（适配暗色主题）：
- 所有文本：`color: '#e5e7eb'`
- 表格背景：`rgba(51, 65, 85, 0.5)`
- 代码块：`#1f2937` 背景
- 引用：`rgba(148, 163, 184, 0.5)` 边框

---

## D. 验收清单

### ✅ 前端 UI
- [x] 左侧边栏不再显示"启用智能编排器"开关
- [x] 详尽度选择器始终可见（不依赖开关）
- [x] sections 平铺展示，无折叠/展开按钮
- [x] 无箭头图标，无点击交互
- [x] 样式适配暗色主题

### ✅ 请求 Payload
- [x] `enable_orchestrator` 恒为 `true`
- [x] `mode` 保持为 "normal" / "decision" / "history_decision"
- [x] `detail_level` 正常传递

### ✅ 后端逻辑
- [x] Schema 默认 `enable_orchestrator=True`
- [x] 路由默认 `use_orchestrator=True`
- [x] "normal" 模式也执行编排器

### ✅ SSE 响应
- [x] `orchestrator_meta.used == true`
- [x] `sections` 为数组（len > 0）
- [x] `followups` 为数组（可为空）
- [x] `orchestrator_meta.modules` 有值

---

## 测试步骤

### 1. 前端 UI 测试
```
1. 打开聊天界面
2. 确认：左侧边栏无"启用智能编排器"开关
3. 确认：详尽度选择器正常显示（精简/标准/详细）
```

### 2. Payload 测试
```
1. 打开 DevTools → Network
2. 发送消息
3. 查看 Request Payload
4. 确认：enable_orchestrator: true（固定）
```

### 3. 平铺展示测试
```
1. 发送问题："介绍一下人工智能"
2. 观察回答
3. 确认：
   - 显示多个 section（如"需求理解"、"核心答案"等）
   - 标题下方直接显示内容，无折叠
   - 无展开/收起按钮
   - 无箭头图标
   - 所有内容平铺展示
```

### 4. SSE 响应测试
```
1. 打开 DevTools → Network
2. 发送消息
3. 找到 /api/chat/stream 请求
4. 查看 SSE 事件
5. 找到 event: result
6. 确认 data JSON 包含：
   - sections: [...]
   - orchestrator_meta: { used: true, modules: [...] }
   - followups: [...]
```

---

## 修改文件清单

### 前端（3 个文件）

1. **frontend/src/components/ChatLayout.tsx**
   - 删除 `enableOrchestrator` 状态（第 84 行）
   - 删除开关 UI（第 554-567 行）
   - 详尽度选择器移出条件渲染（第 569 行）
   - 固定 `enable_orchestrator: true`（第 267 行）

2. **frontend/src/components/ModularAnswer.tsx**
   - 完全重写：删除折叠逻辑，改为平铺展示
   - 删除 `useState`、`toggleSection`
   - 删除折叠箭头、`onClick` 事件
   - 删除条件渲染 `{!isCollapsed && ...}`
   - 样式适配暗色主题

3. **frontend/src/types/index.ts**
   - 保持不变（`enable_orchestrator` 类型定义保留）

---

### 后端（2 个文件）

1. **backend/app/schemas/chat.py**
   - 修改 `enable_orchestrator` 默认值为 `True`（第 41 行）

2. **backend/app/routers/chat.py**
   - 修改 `use_orchestrator` 逻辑（第 894 行）
   - 改为：`req.enable_orchestrator if req.enable_orchestrator is not None else True`

---

## 关键 Diff 总结

### 前端

| 位置 | 修改前 | 修改后 |
|------|--------|--------|
| ChatLayout 状态 | `const [enableOrchestrator, setEnableOrchestrator] = useState(false)` | （删除） |
| ChatLayout UI | 开关 + 条件渲染 | （删除开关，详尽度始终显示） |
| ChatLayout payload | `enable_orchestrator: enableOrchestrator` | `enable_orchestrator: true` |
| ModularAnswer 状态 | `useState<Record<string, boolean>>` | （删除） |
| ModularAnswer UI | 折叠卡片 + 箭头 + onClick | 平铺展示 + 纯标题 |

### 后端

| 位置 | 修改前 | 修改后 |
|------|--------|--------|
| ChatRequest.enable_orchestrator | `Optional[bool] = None` | `Optional[bool] = True` |
| use_orchestrator 计算 | `req.enable_orchestrator or False` | `req.enable_orchestrator if ... else True` |

---

## 常见问题

### Q1: 如果用户真的想关闭编排器怎么办？
**A**: 可以通过 API 手动传 `enable_orchestrator: false`，但前端 UI 不再提供这个选项。

### Q2: "normal" 模式也会返回 sections 吗？
**A**: 是的，所有模式（normal / decision / history_decision）都会执行编排器并返回 sections。

### Q3: 如果后端编排器失败会怎样？
**A**: 会回退到 `answer` 字段，前端会正常显示（MessageList 有降级逻辑）。

### Q4: sections 的顺序由谁决定？
**A**: 后端 `blueprint_modules` 决定顺序，前端按顺序平铺展示。

### Q5: 能否恢复折叠功能？
**A**: 可以，但需要恢复 ModularAnswer.tsx 的折叠逻辑（版本控制中可以找到之前的代码）。

---

## 相关文档

- [编排器关键词优先级](./ORCHESTRATOR_KEYWORD_OVERRIDE.md)
- [编排器快速入门](./LLM_ORCHESTRATOR_QUICKSTART.md)
- [编排器测试用例](./LLM_ORCHESTRATOR_TESTS.md)

---

**修复完成时间**: 2025-12-17  
**影响范围**: 编排器开关移除、平铺展示、默认启用  
**向后兼容**: API 仍支持 `enable_orchestrator` 字段，但前端固定为 `true`

