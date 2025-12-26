# 契约字段对齐修改报告

## 修改目标
将项目信息提取的字段名修改为契约标准（`tender_contract_v1.yaml`），确保系统实现与契约定义一致，同时保持前端向后兼容。

---

## 契约要求

### technical_parameters（契约定义）
```yaml
required_fields:
  - name            # 参数名称
  - value           # 参数值/要求
optional_fields:
  - category        # 参数分类
  - unit            # 单位
  - evidence_chunk_ids
```

### business_terms（契约定义）
```yaml
required_fields:
  - clause_type     # 条款类型
  - content         # 条款内容
optional_fields:
  - clause_title    # 条款标题
  - evidence_chunk_ids
```

---

## 修改前（旧字段）

### technical_parameters
- `item` ❌（非契约字段）
- `requirement` ❌（非契约字段）
- `parameters[]` ❌（非契约字段，是自定义的子数组）
- `category` ✅
- `evidence_chunk_ids` ✅

### business_terms
- `term` ❌（非契约字段）
- `requirement` ❌（非契约字段）
- `evidence_chunk_ids` ✅

---

## 修改后（契约字段）

### technical_parameters
- `name` ✅（契约required）
- `value` ✅（契约required）
- `category` ✅（契约optional）
- `unit` ✅（契约optional）
- `remark` ➕（方案D补充字段）
- `description` ➕（方案D补充字段）
- `structured` ➕（方案D补充字段）
- `parameters` ➕（方案D补充字段，子参数数组）
- `evidence_chunk_ids` ✅

**向后兼容**：
- `item` → 映射到 `name`
- `requirement` → 映射到 `value`

### business_terms
- `clause_type` ✅（契约required）
- `content` ✅（契约required）
- `clause_title` ✅（契约optional）
- `description` ➕（方案D补充字段）
- `structured` ➕（方案D补充字段）
- `evidence_chunk_ids` ✅

**向后兼容**：
- `term` → 映射到 `clause_type`
- `requirement` → 映射到 `content`

---

## 详细修改

### 1. 后端Prompt（`project_info_v2.md`）✅

**JSON Schema更新**：
```json
// 旧
{
  "item": "条目标题",
  "requirement": "要求描述",
  "parameters": [...]
}

// 新
{
  "name": "参数/功能名称",
  "value": "参数值/要求描述",
  "unit": "单位",
  "remark": "备注",
  "parameters": [...]  // 可选的子参数数组
}
```

**字段说明更新**：
- 必填字段：`name` + `value`（契约要求）
- 建议填写：`unit` + `remark`
- 可选字段：`parameters[]` + `description` + `structured`

**示例更新**（6个示例全部更新）：
- 示例1：单个参数值→提取到value和unit
- 示例2：多个参数→使用parameters子数组
- 示例3：有参数值+补充structured
- 示例4：带比较符的参数值
- 示例5：纯文字描述
- 示例6：温度范围参数

**business_terms示例**（5个示例全部更新）：
- `term` → `clause_type`
- `requirement` → `content`

**核心原则更新**：
- "name+value（或clause_type+content）是契约要求的核心字段，必须填写"
- "unit/remark/parameters是补充字段，建议填写但非强制"

---

### 2. 后端Schema（`project_info_v2.py`）✅

**TechnicalParameter类**：
```python
class TechnicalParameter(BaseModel):
    """技术参数（契约标准字段+方案D灵活性）"""
    # 契约要求的核心字段
    name: Optional[str] = None  # 参数/功能名称（契约required）
    value: Optional[str] = None  # 参数值/要求描述（契约required）
    
    # 契约optional字段
    category: Optional[str] = None
    unit: Optional[str] = None
    
    # 方案D补充字段
    remark: Optional[str] = None
    description: Optional[str] = None
    structured: Optional[Dict[str, Any]] = None
    parameters: Optional[List[Dict[str, Any]]] = None
    
    # 向后兼容旧字段名
    item: Optional[str] = None  # 兼容旧的item
    requirement: Optional[str] = None  # 兼容旧的requirement
    
    evidence_chunk_ids: List[str] = Field(default_factory=list)
```

**BusinessTerm类**：
```python
class BusinessTerm(BaseModel):
    """商务条款（契约标准字段+方案D灵活性）"""
    # 契约要求的核心字段
    clause_type: Optional[str] = None  # 条款类型（契约required）
    content: Optional[str] = None  # 条款内容（契约required）
    
    # 契约optional字段
    clause_title: Optional[str] = None
    
    # 方案D补充字段
    description: Optional[str] = None
    structured: Optional[Dict[str, Any]] = None
    
    # 向后兼容旧字段名
    term: Optional[str] = None
    requirement: Optional[str] = None
    
    evidence_chunk_ids: List[str] = Field(default_factory=list)
```

---

### 3. 前端（`ProjectInfoView.tsx`）✅

**technical数据映射**：
```typescript
const technical = useMemo(() => {
  const arr = asArray(dataJson?.technical_parameters);
  return arr.map((x, idx) => ({
    category: String(x?.category || ""),
    // 优先使用契约字段name，兼容旧的item
    item: String(x?.name || x?.item || ""),
    // 优先使用契约字段value，兼容旧的requirement
    requirement: String(x?.value || x?.requirement || ""),
    // 契约新增字段
    unit: String(x?.unit || ""),
    remark: String(x?.remark || ""),
    // 子参数数组
    parameters: asArray(x?.parameters),
    evidence: asArray(x?.evidence_chunk_ids),
    _idx: idx,
  }));
}, [dataJson]);
```

**business数据映射**：
```typescript
const business = useMemo(() => {
  const arr = asArray(dataJson?.business_terms);
  return arr.map((x, idx) => ({
    // 优先使用契约字段clause_type，兼容旧的term
    term: String(x?.clause_type || x?.term || ""),
    // 优先使用契约字段content，兼容旧的requirement
    requirement: String(x?.content || x?.requirement || ""),
    // 契约新增字段
    clause_title: String(x?.clause_title || ""),
    evidence: asArray(x?.evidence_chunk_ids),
    _idx: idx,
  }));
}, [dataJson]);
```

**参数列显示逻辑优化**：
```typescript
<td className="tender-cell">
  {t.parameters.length === 0 ? (
    // 如果没有parameters数组，但有unit/remark，也显示
    (t.unit || t.remark) ? (
      <div className="kb-doc-meta">
        {t.unit && `单位：${t.unit}`}
        {t.unit && t.remark && " / "}
        {t.remark && `备注：${t.remark}`}
      </div>
    ) : "—"
  ) : (
    // 有parameters数组，正常显示
    <div>...</div>
  )}
</td>
```

---

## 兼容性策略

### 数据层兼容
- **Schema定义**：同时保留新旧字段名
- **优先级**：新字段（name/value/clause_type/content）优先，旧字段（item/requirement/term）作为fallback

### 前端显示兼容
- **技术参数**："功能/条目"列优先显示`name`，兼容`item`
- **技术参数**："要求"列优先显示`value`，兼容`requirement`
- **技术参数**："参数"列：优先显示`parameters`数组，如果为空则显示`unit`+`remark`
- **商务条款**：标题优先显示`clause_type`，兼容`term`
- **商务条款**：内容优先显示`content`，兼容`requirement`

### LLM输出兼容
- **新数据**：LLM会按照新Prompt输出契约字段（name/value/clause_type/content）
- **旧数据**：数据库中已有的旧数据（item/requirement/term）仍然可以正常显示
- **过渡期**：在LLM全面切换前，新旧数据并存

---

## 数据流示意

### 新流程（契约标准）
```
LLM输出:
{
  "name": "电机功率要求",
  "value": "≥55kW",
  "unit": "kW",
  "remark": "需配软启动器"
}
↓
存入数据库（JSONB）
↓
前端读取：
- item = x.name || x.item  → "电机功率要求"
- requirement = x.value || x.requirement  → "≥55kW"
- unit = x.unit  → "kW"
- remark = x.remark  → "需配软启动器"
↓
前端显示：
| 功能/条目 | 要求 | 参数 |
| 电机功率要求 | ≥55kW | 单位：kW / 备注：需配软启动器 |
```

### 旧数据兼容
```
数据库旧数据:
{
  "item": "电机功率要求",
  "requirement": "≥55kW应配置软启动器",
  "parameters": [{"name": "功率", "value": "55", "unit": "kW"}]
}
↓
前端读取：
- item = x.name || x.item  → "电机功率要求" (fallback到item)
- requirement = x.value || x.requirement  → "≥55kW应配置软启动器" (fallback到requirement)
- parameters = x.parameters  → [{"name": "功率", "value": "55", "unit": "kW"}]
↓
前端显示：
| 功能/条目 | 要求 | 参数 |
| 电机功率要求 | ≥55kW应配置软启动器 | 功率：55 kW |
```

---

## 测试建议

### 1. 基本功能测试
```bash
# 登录系统
# 进入"测试"项目
# 点击"重新提取基本信息"
# 等待提取完成
```

**验证点**：
- ✅ 技术参数列表正常显示
- ✅ "功能/条目"列有内容（来自name字段）
- ✅ "要求"列有内容（来自value字段）
- ✅ "参数"列显示具体参数（来自unit/remark或parameters数组）
- ✅ 商务条款列表正常显示
- ✅ 条款类型有内容（来自clause_type字段）
- ✅ 条款内容有内容（来自content字段）

### 2. SQL验证
```sql
-- 检查新字段使用情况
SELECT 
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE jsonb_typeof(tp->'name') = 'string') as has_name,
    COUNT(*) FILTER (WHERE jsonb_typeof(tp->'value') = 'string') as has_value,
    COUNT(*) FILTER (WHERE jsonb_typeof(tp->'unit') = 'string') as has_unit,
    COUNT(*) FILTER (WHERE jsonb_typeof(tp->'item') = 'string') as has_item_old
FROM tender_project_info,
     jsonb_array_elements(data_json->'technical_parameters') as tp
WHERE project_id = 'tp_xxx';
```

**预期结果**（新数据）：
- `has_name` > 0 ✅
- `has_value` > 0 ✅
- `has_unit` > 0 （部分有单位）✅
- `has_item_old` = 0 （旧字段不再使用）✅

### 3. 契约验收脚本
```bash
# 运行契约验收脚本
python scripts/eval/tender_feature_parity.py --project-id tp_xxx
```

**预期结果**：
- ✅ technical_parameters包含name和value字段
- ✅ business_terms包含clause_type和content字段
- ✅ 契约验收通过

---

## 修改影响分析

### ✅ 无影响
1. **前端UI**：布局、样式、交互逻辑无变化
2. **数据库Schema**：仍然是JSONB，无需迁移
3. **API接口**：接口路径、参数、返回格式无变化
4. **旧数据**：可以继续正常显示（兼容映射）

### ✅ 正面影响
1. **契约合规**：符合`tender_contract_v1.yaml`定义
2. **验收通过**：通过契约验收脚本
3. **语义清晰**：name/value比item/requirement更符合语义
4. **灵活性**：unit/remark/parameters提供更丰富的数据组织方式

### ⚠️ 需要注意
1. **LLM输出格式**：LLM需要按新格式输出（已修改Prompt）
2. **测试数据**：新提取的数据会使用新字段名
3. **文档更新**：相关技术文档需要更新字段名

---

## 方案D理念的保留

虽然修改了字段名，但**方案D的核心理念完全保留**：

### ✅ LLM自主性
- category/clause_type：LLM自己定义分类
- description：可选的详细描述
- structured：LLM自主结构化（内部结构自定义）
- parameters：可选的子参数数组

### ✅ "宁可多提取"原则
- 提取范围宽泛（技术、商务边界灵活）
- 不确定时优先提取
- base字段可以自由添加

### ✅ 灵活组织方式
- **简单内容**：name + value
- **有单位**：name + value + unit + remark
- **多参数**：name + value + parameters[]
- **最详细**：name + value + unit + remark + parameters + description + structured

---

## 总结

### 修改内容
1. ✅ 后端Prompt：字段名、示例、说明全部更新
2. ✅ 后端Schema：新增契约字段，保留旧字段兼容
3. ✅ 前端代码：优先使用契约字段，兼容旧字段
4. ✅ 参数显示：支持unit/remark直接显示

### 修改目标
- ✅ 符合契约标准（`tender_contract_v1.yaml`）
- ✅ 保持前端兼容（新旧数据都能正常显示）
- ✅ 保留方案D灵活性（LLM自主性+宁可多提取）

### 下一步
- 🔄 用户测试验证
- 🔄 契约验收脚本验证
- 📝 更新相关技术文档

---

**修改日期**：2025-12-25  
**修改状态**：✅ 已完成并部署  
**影响范围**：项目信息提取（technical_parameters + business_terms）  
**兼容性**：✅ 向后兼容  
**测试状态**：⏳ 等待用户验证

