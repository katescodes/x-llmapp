# 编排器关键词优先级与前端渲染增强

## 概述

本文档说明了两个重要的增强功能：
1. **关键词优先级覆盖**：用户文本中的详尽度关键词会覆盖 UI 设置
2. **前端模块化渲染**：根据 `sections` 自动切换渲染方式，并尊重 `collapsed` 状态

---

## 1. 后端：关键词优先级覆盖

### 功能说明

当用户在文本中包含特定关键词时，编排器会自动调整详尽度级别，**优先级高于 UI 选择器的设置**。

### 关键词列表

#### 📉 Brief（简洁）关键词
触发条件：用户文本包含以下任一关键词
```
简短, 只要结论, 一句话, 不要展开, 别解释, 快速, 概括, 
简单说, 不要啰嗦, 直接说, 精简
```

**示例**：
- "简短介绍一下量子计算"
- "一句话总结这个概念"
- "只要结论，不要展开"

#### 📈 Detailed（详细）关键词
触发条件：用户文本包含以下任一关键词
```
详细, 逐条, 每个, 深入, 全面, 展开, 越详细越好, 更细, 
多例子, 更完整, 详细解释, 具体说明, 详尽, 更多细节
```

**示例**：
- "详细介绍一下机器学习"
- "逐条说明每个步骤"
- "越详细越好，我想深入了解"

### 优先级规则

```
用户文本关键词 > UI 详尽度选择器 > 默认值（normal）
```

**流程**：
1. `OrchestratorService._detect_detail_level_from_text()` 检测用户文本
2. 如果检测到关键词 → 使用关键词对应的级别
3. 如果无关键词 → 使用 UI 设置（`req.detail_level`）
4. 如果 UI 也未设置 → 使用默认值 `"normal"`

### 实现位置

**文件**: `backend/app/services/orchestrator/orchestrator_service.py`

**方法**: `_detect_detail_level_from_text(text: str) -> Optional[str]`

```python
def _detect_detail_level_from_text(self, text: str) -> Optional[str]:
    """从用户文本中检测详尽度关键词
    
    优先级：用户文本关键词 > UI 设置
    - 包含 detailed 关键词 => "detailed"
    - 包含 brief 关键词 => "brief"
    - 无关键词 => None（使用 UI 设置或默认值）
    """
    text_lower = text.lower()
    
    # brief 关键词（简洁优先，优先检查）
    brief_keywords = [
        "简短", "只要结论", "一句话", "不要展开",
        "别解释", "快速", "概括", "简单说", 
        "不要啰嗦", "直接说", "精简",
    ]
    for kw in brief_keywords:
        if kw in text_lower:
            return "brief"
    
    # detailed 关键词（详细说明）
    detailed_keywords = [
        "详细", "逐条", "每个", "深入", "全面", "展开", "越详细越好",
        "更细", "多例子", "更完整", "详细解释", 
        "具体说明", "详尽", "更多细节",
    ]
    for kw in detailed_keywords:
        if kw in text_lower:
            return "detailed"
    
    return None
```

### orchestrator_meta 中的 detail_level

**最终生效的详尽度级别**会写入 `orchestrator_meta.detail_level` 字段：

```json
{
  "orchestrator_meta": {
    "enabled": true,
    "used": true,
    "detail_level": "detailed",  // ← 关键词覆盖后的最终值
    "mode": "normal",
    "modules": ["align_summary", "core_answer", "next_steps"]
  }
}
```

**更新位置**: `backend/app/routers/chat.py` line 918

```python
orchestrator_meta.update({
    "used": True,
    "intent": requirements.intent,
    "detail_level": requirements.detail_level,  // ← 包含关键词检测结果
    "blueprint_modules": requirements.blueprint_modules,
    "modules": requirements.blueprint_modules,
    "assumptions": requirements.assumptions,
})
```

---

## 2. 前端：模块化渲染与折叠状态

### 功能说明

前端会根据 `message.sections` 字段的存在自动选择渲染方式：
- **有 sections** → 使用 `<ModularAnswer>` 组件（折叠卡片）
- **无 sections** → 使用 `<MessageBubble>` 组件（传统气泡）

### 实现位置

#### MessageList.tsx

**文件**: `frontend/src/components/MessageList.tsx`

**逻辑**:
```typescript
{msg.role === "assistant" && msg.sections && msg.sections.length > 0 ? (
  // 使用模块化渲染（编排器模式）
  <div className="modular-message">
    <ModularAnswer
      sections={msg.sections}
      followups={msg.followups}
    />
  </div>
) : (
  // 使用传统气泡渲染
  <MessageBubble role={msg.role} content={msg.content} />
)}
```

#### ModularAnswer.tsx

**文件**: `frontend/src/components/ModularAnswer.tsx`

**折叠状态管理**:
```typescript
const [collapsedState, setCollapsedState] = useState<Record<string, boolean>>(
  () => {
    const initial: Record<string, boolean> = {};
    sections.forEach((section) => {
      initial[section.id] = section.collapsed;  // ← 尊重 section.collapsed
    });
    return initial;
  }
);
```

**说明**：
- 初始化时读取每个 section 的 `collapsed` 属性
- 用户点击标题可切换展开/折叠状态
- 状态保存在组件内部（刷新页面会重置）

### ChatSection 数据结构

```typescript
interface ChatSection {
  id: string;           // 模块ID，如 "align_summary"
  title: string;        // 模块标题，如 "需求理解"
  markdown: string;     // 模块内容（Markdown 格式）
  collapsed: boolean;   // 默认是否折叠（true=折叠，false=展开）
}
```

### 折叠状态的默认值

由后端 `parse_sections_from_answer()` 决定：

```python
# backend/app/services/orchestrator/orchestrator_service.py
def parse_sections_from_answer(self, answer: str, module_titles: Dict[str, str]) -> List[ChatSection]:
    sections = []
    # ... 解析逻辑 ...
    sections.append(ChatSection(
        id=module_id,
        title=title,
        markdown=content,
        collapsed=False,  # ← 默认全部展开
    ))
```

**可定制**：如果某些模块（如"背景知识"）需要默认折叠，可以在此处根据 `module_id` 设置不同的 `collapsed` 值。

---

## 3. 验收测试

### 测试用例 1: Brief 关键词覆盖

**操作**：
1. 在 UI 选择"答案详尽度 = 详细"
2. 输入："一句话介绍人工智能"
3. 提交

**预期**：
- `orchestrator_meta.detail_level = "brief"`（关键词覆盖 UI 设置）
- 答案简洁，无冗余展开

---

### 测试用例 2: Detailed 关键词覆盖

**操作**：
1. 在 UI 选择"答案详尽度 = 精简"
2. 输入："详细介绍机器学习的每个步骤"
3. 提交

**预期**：
- `orchestrator_meta.detail_level = "detailed"`（关键词覆盖 UI 设置）
- 答案详细，包含多个模块和示例

---

### 测试用例 3: 前端折叠状态

**操作**：
1. 启用编排器
2. 发送任意问题（如"介绍人工智能"）
3. 观察前端渲染

**预期**：
- 看到折叠卡片样式（而非传统气泡）
- 每个模块有标题和折叠按钮（▼）
- 点击标题可切换展开/折叠
- 初始状态遵循 `section.collapsed`（默认全部展开）

---

### 测试用例 4: 无 sections 时的降级

**操作**：
1. 关闭编排器
2. 发送问题

**预期**：
- 前端使用传统气泡渲染
- 显示 `message.content` 而非 `sections`

---

## 4. 相关文件

### 后端
- `backend/app/services/orchestrator/orchestrator_service.py`
  - `_detect_detail_level_from_text()` - 关键词检测
  - `extract_requirements()` - 调用关键词检测并生成 `requirements.detail_level`
- `backend/app/routers/chat.py`
  - 更新 `orchestrator_meta["detail_level"]` 为最终生效的值

### 前端
- `frontend/src/components/MessageList.tsx`
  - 根据 `sections` 存在性选择渲染组件
- `frontend/src/components/ModularAnswer.tsx`
  - 折叠卡片渲染
  - 尊重 `section.collapsed` 初始状态
- `frontend/src/types/orchestrator.ts`
  - `ChatSection` 类型定义

---

## 5. 常见问题

### Q1: 如果用户文本同时包含 brief 和 detailed 关键词？
**A**: Brief 优先（代码中先检查 brief，匹配后立即返回）。

### Q2: 关键词检测是否区分大小写？
**A**: 不区分，检测前会转为小写（`text.lower()`）。

### Q3: 如何添加新的关键词？
**A**: 编辑 `orchestrator_service.py` 的 `_detect_detail_level_from_text()` 方法，在对应列表中添加新关键词。

### Q4: 前端折叠状态会保存吗？
**A**: 不会，刷新页面后会重置为 `section.collapsed` 的初始值。如需持久化，可以将状态存入 `localStorage`。

### Q5: 如何让某些模块默认折叠？
**A**: 在后端 `parse_sections_from_answer()` 中，根据 `module_id` 设置 `collapsed=True`：
```python
collapsed = (module_id in ["background_context", "optional_details"])
```

---

**修复完成时间**: 2025-12-17  
**影响范围**: 编排器详尽度优先级逻辑 + 前端模块化渲染

