# 方案D修复2：parameters数组问题

## 问题发现
**用户反馈**：技术实际的参数和商务参数没有出来

## 问题分析

### 前端展示逻辑
前端有一个专门的"参数"列来显示parameters数组：

```typescript
// frontend/src/components/tender/ProjectInfoView.tsx
<td className="tender-cell">
  {t.parameters.length === 0 ? (
    "—"  // 如果parameters为空，显示破折号
  ) : (
    <div>
      {t.parameters.slice(0, 6).map((p: any, i: number) => (
        <div key={i}>
          {String(p?.name || "参数")}：{String(p?.value || "")}
          {p?.unit ? ` ${p.unit}` : ""}
          {p?.remark ? `（${p.remark}）` : ""}
        </div>
      ))}
    </div>
  )}
</td>
```

### 实际数据
查询数据库发现：

```json
{
  "item": "主要设备授权要求",
  "category": "商务/技术交叉",
  "requirement": "投标人须提供制造商对PLC设备和超融合一体机的授权文件...",
  "evidence_chunk_ids": ["seg_1"]
  // ❌ 缺少parameters数组！
}
```

**结果**：
- ✅ requirement有内容（前端"要求"列能显示）
- ❌ parameters数组缺失（前端"参数"列显示"—"）

### 根本原因
之前的prompt没有强调parameters的重要性，LLM可能认为：
- 只填requirement就够了
- parameters是可选的，可以不填
- 或者不知道什么时候该填parameters

---

## 修复方案

### 核心修改：强调parameters必须提取具体参数值

**修改重点**：
1. **明确什么算"具体参数值"**
2. **给出大量提取示例**
3. **在多个地方强调parameters的重要性**

---

## 具体修改内容

### 1. JSON格式示例
将parameters提到更显眼的位置，并添加注释：

```json
{
  "item": "条目标题（必填）",
  "category": "分类（可选）",
  "requirement": "要求描述（必填）",
  "parameters": [
    // 重要：如果有具体的参数值（电压、功率、尺寸等），必须提取到这里
    {"name": "参数名", "value": "参数值", "unit": "单位", "remark": "备注"}
  ],
  "evidence_chunk_ids": ["CHUNK_xxx"]
}
```

### 2. 字段使用说明
新增"什么算具体参数值"的详细说明：

```markdown
**什么算"具体的参数值"**（必须提取到parameters）：
- 电气参数：电压（380V）、电流（50A）、功率（≥55kW）、频率（50Hz）
- 物理参数：尺寸（2000×1000mm）、重量（≤100kg）、容量（500L）
- 性能参数：转速（1450rpm）、流量（≥100m³/h）、压力（0.4MPa）、精度（±0.1%）
- 环境参数：温度（-20~60℃）、湿度（≤85%）、防护等级（IP55）
- 配置参数：CPU（i7-12700）、内存（32GB）、硬盘（512GB SSD）
- 质量参数：厚度（≥3mm）、材质（304不锈钢）
```

### 3. 提取示例
更新为6个示例，大部分都有parameters：

**示例1：有明确参数值→必须提取**
```json
{
  "item": "电机功率要求",
  "requirement": "较大功率电机（≥55kW）应配置软启动器",
  "parameters": [
    {"name": "功率下限", "value": "55", "unit": "kW", "remark": "需配软启动器"}
  ]
}
```

**示例2：多个参数值→全部提取**
```json
{
  "item": "中央操作计算机配置",
  "requirement": "CPU不低于i7-12700，内存不低于32GB",
  "parameters": [
    {"name": "CPU", "value": "i7-12700", "unit": "", "remark": ""},
    {"name": "内存", "value": "≥32", "unit": "GB", "remark": ""}
  ]
}
```

**示例3：带比较符→保留比较符**
```json
{
  "item": "电压降要求",
  "requirement": "电压降应在10%以内",
  "parameters": [
    {"name": "电压降上限", "value": "≤10", "unit": "%", "remark": ""}
  ]
}
```

**示例4：温度范围**
```json
{
  "item": "工作温度要求",
  "requirement": "设备应能在-20℃至60℃范围内正常工作",
  "parameters": [
    {"name": "工作温度范围", "value": "-20~60", "unit": "℃", "remark": ""}
  ]
}
```

**示例5：只有文字描述→parameters可以为空**
```json
{
  "item": "钢结构焊接规范",
  "requirement": "所有钢结构件应进行金属电弧焊接，并满足BS5135标准",
  "parameters": []  // 没有具体数值，可以为空
}
```

### 4. 提取原则
新增第2条原则，专门强调parameters：

```markdown
2. **必须提取具体参数值**：
   - 看到"功率55kW"、"电压380V"等具体数值→必须提取到parameters
   - 看到"不低于"、"≥"、"≤"、"范围"等带数值的→必须提取到parameters
   - 看到"尺寸"、"重量"、"容量"等物理量→必须提取到parameters
```

### 5. 最后提醒
新增"什么情况必须填写parameters"的专门说明：

```markdown
### 什么情况必须填写parameters（重要！）

**必须填写**（有具体数值）：
- ✅ "功率≥55kW" → parameters: [{"name": "功率", "value": "≥55", "unit": "kW"}]
- ✅ "电压380V" → parameters: [{"name": "电压", "value": "380", "unit": "V"}]
- ✅ "温度-20~60℃" → parameters: [{"name": "温度范围", "value": "-20~60", "unit": "℃"}]
- ✅ "内存不低于32GB" → parameters: [{"name": "内存", "value": "≥32", "unit": "GB"}]
- ✅ "防护等级IP55" → parameters: [{"name": "防护等级", "value": "IP55", "unit": ""}]

**可以不填写**（纯文字描述，无具体数值）：
- ❌ "应满足国家标准" → parameters: []
- ❌ "质量合格" → parameters: []
```

---

## 修复效果

### 修复前
```json
{
  "item": "电机功率要求",
  "requirement": "较大功率电机（≥55kW）应配置软启动器",
  "parameters": []  // ❌ 空数组
}
```
- ✅ requirement有内容
- ❌ parameters为空
- ❌ 前端"参数"列显示"—"

### 修复后
```json
{
  "item": "电机功率要求",
  "requirement": "较大功率电机（≥55kW）应配置软启动器",
  "parameters": [
    {"name": "功率下限", "value": "55", "unit": "kW", "remark": "需配软启动器"}
  ]
}
```
- ✅ requirement有内容
- ✅ parameters有具体参数
- ✅ 前端"参数"列显示："功率下限：55 kW（需配软启动器）"

---

## 前端展示效果

### 技术参数表格

| 分类 | 功能/条目 | 要求 | **参数** | 证据 |
|------|-----------|------|----------|------|
| 电气参数 | 电机功率要求 | 较大功率电机（≥55kW）应配置软启动器 | **功率下限：55 kW（需配软启动器）** ✅ | 证据(1) |
| 配置参数 | 中央操作计算机 | CPU不低于i7-12700，内存不低于32GB | **CPU：i7-12700**<br>**内存：≥32 GB** ✅ | 证据(1) |
| 环境参数 | 工作温度 | 设备应能在-20℃至60℃范围内正常工作 | **工作温度范围：-20~60 ℃** ✅ | 证据(1) |

**修复前**：参数列全是"—"  
**修复后**：参数列显示具体参数值 ✅

---

## 测试验证

### 测试步骤
1. 登录系统：`admin/admin123`
2. 进入"测试"项目
3. 点击"重新提取基本信息"
4. 等待提取完成
5. 查看技术参数表格

### 验证点

#### ✅ requirement列
- 应该有文字内容（不是"—"）
- 示例："较大功率电机（≥55kW）应配置软启动器"

#### ✅ 参数列（重点验证）
- **不应该**全是"—"
- 应该显示具体参数，例如：
  - "功率下限：55 kW"
  - "CPU：i7-12700"
  - "内存：≥32 GB"
  - "电压：380 V"
  - "温度范围：-20~60 ℃"
  - "防护等级：IP55"

#### ✅ 提取数量
- 技术参数数量应该 > 20条
- 其中至少50%应该有parameters数组（不为空）

### SQL验证
```sql
-- 检查parameters字段使用情况
SELECT 
    COUNT(*) as total_count,
    COUNT(*) FILTER (WHERE jsonb_array_length(tp->'parameters') > 0) as has_params,
    COUNT(*) FILTER (WHERE jsonb_array_length(tp->'parameters') = 0) as no_params
FROM tender_project_info,
     jsonb_array_elements(data_json->'technical_parameters') as tp
WHERE project_id = 'tp_9160ce348db444e9b5a3fa4b66e8680a';
```

**预期结果**：
- `total_count`: 20-50
- `has_params`: > 10（至少50%有参数）
- `no_params`: < 50%

---

## 与方案D的关系

### 方案D的核心理念保持不变
- ✅ LLM仍然可以自由定义category
- ✅ LLM仍然可以使用description补充详细信息
- ✅ LLM仍然可以使用structured自主结构化
- ✅ base字段仍然可以自由添加字段

### 修复只是明确了parameters的提取规则
- **之前**：parameters是"可选的"，不清楚何时该填
- **现在**：明确"有具体参数值时必须填写"

**类比**：
- requirement = 主菜（必须有）
- parameters = 具体配料清单（如果主菜里提到了"鸡蛋2个"、"面粉500g"，必须列出来）
- description = 详细做法（可选）
- structured = 其他信息（可选）

---

## 文件变更

### 修改的文件
1. `backend/app/works/tender/prompts/project_info_v2.md`
   - 修改JSON格式示例（parameters位置提前）
   - 修改字段使用说明（明确什么算参数值）
   - 修改提取示例（6个示例，大部分有parameters）
   - 修改提取原则（新增第2条）
   - 修改最后提醒（新增parameters使用说明）

### 未修改的文件
- 前端代码：无需修改
- Schema定义：无需修改
- 数据库：无需修改

---

## 总结

### 问题核心
- **用户看到**：前端"参数"列全是"—"
- **实际原因**：LLM没有填写parameters数组
- **根本原因**：prompt没有明确强调parameters的重要性

### 修复策略
1. **明确定义**：什么算"具体参数值"
2. **大量示例**：6个示例展示如何提取parameters
3. **多处强调**：在字段说明、提取原则、最后提醒中都强调

### 预期效果
- requirement列：有文字内容 ✅
- **parameters列**：显示具体参数值（不再是全"—"）✅
- 提取数量：> 20条技术参数 ✅
- parameters使用率：> 50%的条目有parameters ✅

---

**修复状态**：✅ 已完成并部署  
**影响**：修复了parameters数组缺失问题  
**测试**：等待用户验证  
**日期**：2025-12-25

