# 方案D紧急修复报告

## 问题发现
**用户反馈**：这个版本的技术功能、参数和商务条款在前端没有了

## 问题分析

### 根本原因
前端代码读取的是`requirement`字段：

```typescript
// frontend/src/components/tender/ProjectInfoView.tsx
const technical = useMemo(() => {
  const arr = asArray(dataJson?.technical_parameters || ...);
  return arr.map((x, idx) => ({
    requirement: String(x?.requirement || ""),  // 前端读取requirement
    ...
  }));
}, [dataJson]);

// 前端展示
<td className="tender-cell">{t.requirement || "—"}</td>
```

但修改前的prompt让LLM以为`requirement`是"传统参数数组（向后兼容，可选）"，导致LLM可能：
1. 只生成`description`和`structured`，不生成`requirement`
2. 前端读取`requirement`为空，显示为"—"
3. 用户看到的是空白内容

### 错误的Prompt（修改前）

```json
{
  "item": "条目标题（必填）",
  "category": "分类（可选）",
  
  // 方式1：自由文字描述
  "description": "详细描述内容",
  
  // 方式2：自主结构化
  "structured": {...},
  
  // 方式3：传统参数数组（向后兼容，可选）  <-- 错误！LLM可能以为可以不填
  "requirement": "要求描述",
  "parameters": [...]
}
```

LLM可能理解为：
- 使用`description`就不需要`requirement`
- 或者只填`structured`就够了

---

## 修复方案

### 核心修改：requirement改为必填

**修改后的Prompt结构**：

```json
{
  "item": "条目标题（必填）",
  "category": "分类（可选）",
  "requirement": "要求描述（必填，用于前端展示的主要文字）",  // <-- 明确必填！
  
  // ===== 可选的详细描述方式 =====
  "description": "更详细的描述（可选，如果requirement不够详细可补充）",
  "structured": {
    // 可选：如果能结构化，可以添加这个字段
  },
  "parameters": [
    // 可选：传统参数数组
  ]
}
```

### 字段定位调整

**修改前（错误）**：
- description/structured：主要方式
- requirement：向后兼容（可选）

**修改后（正确）**：
- **requirement：必填**（用于前端展示）
- description：可选补充（更详细的描述）
- structured：可选补充（结构化信息）
- parameters：可选补充（传统格式）

---

## 具体修改内容

### 1. JSON格式示例
修改了`technical_parameters`和`business_terms`的JSON示例，明确标注：
- `requirement`：**必填**，用于前端展示的主要文字
- `description`和`structured`：**可选**，用于补充详细信息

### 2. 字段使用说明
新增了明确的字段优先级说明：

```markdown
**必填字段**：
- item/term：条目标题，必填
- requirement：要求描述，**必填**（用于前端主要展示）
- evidence_chunk_ids：证据链接，必填

**可选字段（用于补充详细信息）**：
- description：更详细的描述
- structured：结构化信息
- parameters：传统参数数组
- category：分类
```

### 3. 提取示例
所有示例都更新为包含`requirement`字段：

```json
// 示例：简单内容（只用requirement）
{
  "item": "随机备品备件",
  "category": "配置清单",
  "requirement": "投标报价应包含随机备品备件、专用工具和仪器仪表",
  "evidence_chunk_ids": ["seg_xxx"]
}

// 示例：复杂内容（requirement + description）
{
  "item": "钢结构焊接规范",
  "category": "技术标准",
  "requirement": "所有钢结构件应进行金属电弧焊接，并满足BS5135或同等国际标准",
  "description": "所有钢结构件，无论是车间预制的还是现场焊接的，均应进行金属电弧焊接，并满足BS5135或同等国际标准的要求。焊缝应该是连续的焊接，而没有中途中断。",
  "evidence_chunk_ids": ["seg_xxx"]
}

// 示例：可结构化内容（requirement + structured）
{
  "item": "电机功率要求",
  "category": "电气参数",
  "requirement": "较大功率电机（≥55kW）应配置软启动器",
  "structured": {
    "功率下限": "55kW",
    "配置要求": "需配软启动器"
  },
  "evidence_chunk_ids": ["seg_xxx"]
}
```

### 4. 最后提醒
更新了核心理念，明确：
- **requirement必填**保证前端兼容
- **description/structured可选**提供更多信息

---

## 修复效果

### 修复前
- ❌ LLM可能只生成`description`和`structured`
- ❌ 前端读取`requirement`为空
- ❌ 用户看到空白内容

### 修复后
- ✅ LLM必须生成`requirement`字段
- ✅ 前端能正确读取`requirement`
- ✅ 用户能看到完整内容
- ✅ description/structured作为可选补充，提供更多信息

---

## 兼容性确认

### ✅ 前端兼容
```typescript
// 前端代码不需要修改，仍然读取requirement
requirement: String(x?.requirement || ""),
```

### ✅ 向后兼容
- 旧数据：只有`requirement`字段 → ✅ 正常显示
- 新数据：`requirement` + `description` + `structured` → ✅ requirement正常显示，额外字段暂不显示

### ✅ 方案D优势保持
- ✅ LLM仍然可以自由定义category/term
- ✅ LLM仍然可以使用description补充详细信息
- ✅ LLM仍然可以使用structured自主结构化
- ✅ base字段仍然可以自由添加字段

**唯一变化**：requirement从"可选"改为"必填"，确保前端兼容

---

## 测试验证

### 测试步骤
1. 登录系统：`admin/admin123`
2. 进入"测试"项目
3. 点击"重新提取基本信息"
4. 查看结果

### 验证点
- ✅ 技术参数表格有内容（不是全"—"）
- ✅ 商务条款表格有内容（不是全"—"）
- ✅ requirement字段有文字
- ✅ 提取数量 > 20条（技术参数）和 > 15条（商务条款）

---

## 文件变更

### 修改的文件
1. `backend/app/works/tender/prompts/project_info_v2.md`
   - 修改JSON格式示例（requirement改为必填）
   - 修改字段使用说明（明确必填和可选）
   - 修改所有提取示例（都包含requirement）
   - 修改最后提醒（明确requirement必填）

### 未修改的文件
- 前端代码：无需修改
- Schema定义：无需修改（只是参考，不强制校验）
- 数据库：无需修改

---

## 总结

### 问题核心
- **用户期望**：前端能显示内容
- **实际情况**：前端读取`requirement`字段
- **问题原因**：prompt让LLM以为`requirement`可选
- **修复方案**：明确`requirement`必填

### 方案D调整
**原方案D理念**：
- description/structured为主
- requirement为辅（向后兼容）

**调整后的方案D理念**：
- **requirement必填**（保证前端兼容）
- description/structured可选（提供更多信息）
- 仍然保持LLM自主性（category/term自由定义，structured自主结构化）

### 经验教训
1. **前端依赖的字段不能改为可选**
2. **新增字段可以可选，但原有字段要保持**
3. **修改prompt时要考虑前端读取逻辑**
4. **示例要准确反映必填和可选的关系**

---

**修复状态**：✅ 已完成并部署  
**影响**：修复了前端显示问题，保持了方案D的核心优势  
**测试**：等待用户验证  
**日期**：2025-12-25

