# 方案D详细实施方案

## 系统架构分析

### 数据流程
```
LLM(prompt) → JSON → tender_project_info.data_json(JSONB) → 前端读取
```

### 关键代码位置

1. **Prompt定义**：`backend/app/works/tender/prompts/project_info_v2.md`
2. **数据存储**：`backend/app/services/dao/tender_dao.py::upsert_project_info()`
3. **前端展示**：`frontend/src/components/tender/ProjectInfoView.tsx`
4. **Schema定义**：`backend/app/works/tender/schemas/project_info_v2.py`（未实际使用）

### 兼容性确认

✅ **数据存储兼容**：
```python
def upsert_project_info(self, project_id: str, data_json: Dict[str, Any], evidence_chunk_ids: List[str]):
    """插入或更新项目信息"""
    self._execute(
        """
        INSERT INTO tender_project_info (project_id, data_json, evidence_chunk_ids_json, updated_at)
        VALUES (%s, %s::jsonb, %s::jsonb, NOW())
        ...
        """
    )
```
- 直接将Dict存入JSONB，无Schema校验
- 任意新字段都能存储

✅ **前端展示兼容**：
```typescript
const technical = useMemo(() => {
  const arr = asArray(dataJson?.technical_parameters || dataJson?.technicalParameters);
  return arr.map((x, idx) => ({
    category: String(x?.category || ""),
    item: String(x?.item || ""),
    requirement: String(x?.requirement || ""),
    parameters: asArray(x?.parameters),
    description: String(x?.description || ""),      // 新字段，自动处理
    structured: x?.structured || null,              // 新字段，自动处理
    evidence: asArray(x?.evidence_chunk_ids),
    _idx: idx,
  }));
}, [dataJson]);
```
- 使用`?.`和`|| ""`处理缺失字段
- 新字段即使存在也不会破坏现有展示
- 后续可以增强展示逻辑

---

## 方案D修改详情

### 修改1：扩展base字段（支持自定义字段）

**当前结构**：
```json
{
  "base": {
    "projectName": "项目名称",
    "ownerName": "招标人",
    "budget": "预算金额",
    ...
  }
}
```

**修改后结构**：
```json
{
  "base": {
    // 核心字段（保持不变，前端依赖）
    "projectName": "项目名称",
    "ownerName": "招标人",
    "agencyName": "代理机构",
    "bidDeadline": "投标截止时间",
    "bidOpeningTime": "开标时间",
    "budget": "预算金额",
    "maxPrice": "最高限价",
    "bidBond": "投标保证金",
    "schedule": "工期要求",
    "quality": "质量要求",
    "location": "项目地点",
    "contact": "联系人",
    
    // 自定义字段（LLM自由添加）
    "项目规模": "xxx",
    "建设地点详细": "xxx",
    "资金来源": "xxx",
    "项目性质": "xxx",
    "建设单位": "xxx",
    ...任何LLM认为是基本信息的字段
  }
}
```

**兼容性**：✅ 完全兼容
- 前端只读取已定义的BASIC_FIELDS，自定义字段不影响
- 后续可以在"查看原始JSON"中看到所有字段

---

### 修改2：增强technical_parameters（增加description和structured字段）

**当前结构**：
```json
{
  "category": "设备参数",
  "item": "条目标题",
  "requirement": "要求描述",
  "parameters": [
    {"name": "参数名", "value": "参数值", "unit": "单位", "remark": "备注"}
  ],
  "evidence_chunk_ids": ["..."]
}
```

**修改后结构**：
```json
{
  "category": "设备参数（LLM自由定义）",
  "item": "条目标题",
  
  // 方式1：自由文字描述
  "description": "详细描述内容，可以是段落、列表等（如果内容复杂或难以结构化）",
  
  // 方式2：结构化信息（LLM自己决定结构）
  "structured": {
    // 可以是任意结构：对象、数组、嵌套等
    // 示例1：参数列表
    "parameters": [
      {"name": "功率", "value": "≥55kW", "remark": "需配软启动器"}
    ],
    // 示例2：自由组织
    "适用标准": ["BS5135", "GB50017"],
    "工艺要求": "焊接必须满足规范",
    "关键指标": {
      "电压": "380V",
      "频率": "50Hz"
    }
  },
  
  // 旧的parameters字段（保留兼容，可选）
  "parameters": [...],
  
  // 旧的requirement字段（保留兼容，可选）
  "requirement": "...",
  
  "evidence_chunk_ids": ["..."]
}
```

**字段说明**：
- `category`：分类（LLM自由定义，不限制）
- `item`：条目标题（必填）
- `description`：自由文字描述（新增，可选）
- `structured`：结构化信息（新增，可选，LLM自己决定内部结构）
- `parameters`：旧的参数数组（保留，可选）
- `requirement`：旧的要求描述（保留，可选）

**使用原则**：
- `description`和`structured`可以同时使用，也可以只用一个
- 如果能结构化，优先用`structured`
- 如果内容复杂，用`description`
- `parameters`和`requirement`保留用于向后兼容

**兼容性**：✅ 完全兼容
- 前端现有逻辑读取`item`, `requirement`, `parameters`
- 新字段`description`, `structured`不影响现有展示
- 后续可以增强前端显示这些新字段

---

### 修改3：增强business_terms（增加description和structured字段）

**当前结构**：
```json
{
  "term": "付款方式",
  "requirement": "条款内容",
  "evidence_chunk_ids": ["..."]
}
```

**修改后结构**：
```json
{
  "term": "付款方式（或LLM自定义的条款类型）",
  
  // 方式1：自由文字描述
  "description": "详细描述条款内容",
  
  // 方式2：结构化信息
  "structured": {
    // LLM自己决定结构
    // 示例：
    "预付款": "30%",
    "进度款": "60%",
    "尾款": "10%",
    "付款条件": "验收合格后"
  },
  
  // 旧的requirement字段（保留兼容）
  "requirement": "...",
  
  "evidence_chunk_ids": ["..."]
}
```

**兼容性**：✅ 完全兼容

---

### 修改4：Prompt修改策略

#### 保持核心结构 + 增加自由度

**原则**：
1. **核心字段保持**：base的核心字段仍然明确列出
2. **增加自由字段**：允许LLM添加额外字段
3. **双模式支持**：description（自由）+ structured（结构化）
4. **减少约束**：去掉过于详细的分类要求，让LLM自己判断

**Prompt结构**：
```markdown
## JSON格式（核心结构）

{
  "data": {
    "base": {
      // 核心字段（尽量填写）
      "projectName": "...",
      "ownerName": "...",
      ...
      
      // 自定义字段（自由添加）
      "任何你认为是基本信息的字段": "..."
    },
    
    "technical_parameters": [
      {
        "item": "条目标题（必填）",
        "category": "分类（可选，自由定义）",
        
        // 内容描述（两种方式，二选一或同时使用）
        "description": "自由文字描述",
        "structured": {/* LLM自己决定结构 */},
        
        // 兼容字段（可选）
        "requirement": "...",
        "parameters": [...],
        
        "evidence_chunk_ids": [...]
      }
    ],
    
    "business_terms": [
      {
        "term": "条款类型（自由定义）",
        "description": "自由文字描述",
        "structured": {/* LLM自己决定结构 */},
        "requirement": "...",  // 兼容字段
        "evidence_chunk_ids": [...]
      }
    ]
  }
}
```

**提取原则**：
1. **核心字段优先**：base的核心字段尽量按规定填写
2. **自由扩展**：可以在base中添加任何其他基本信息字段
3. **灵活组织**：technical/business可以用description自由描述，也可以用structured结构化
4. **宁可多提取**：不要遗漏信息
5. **自主判断**：分类、结构由LLM自己决定

---

## 实施步骤

### 步骤1：备份当前Prompt
```bash
cp backend/app/works/tender/prompts/project_info_v2.md backend/app/works/tender/prompts/project_info_v2.md.backup
```

### 步骤2：修改Prompt
- 修改base字段说明（增加自定义字段说明）
- 修改technical_parameters结构（增加description和structured）
- 修改business_terms结构（增加description和structured）
- 简化分类要求（去掉过于详细的枚举）
- 增加"LLM自主组织"的指导原则

### 步骤3：更新Schema（可选，建议做）
```python
# backend/app/works/tender/schemas/project_info_v2.py

class TechnicalParameter(BaseModel):
    """技术参数"""
    category: Optional[str] = None
    item: Optional[str] = None
    
    # 新增字段
    description: Optional[str] = None
    structured: Optional[Dict[str, Any]] = None
    
    # 兼容字段
    requirement: Optional[str] = None
    parameters: Optional[List[Dict[str, Any]]] = None
    
    evidence_chunk_ids: List[str] = Field(default_factory=list)
```

### 步骤4：部署后端
```bash
docker-compose up -d --no-deps backend
```

### 步骤5：测试验证
1. 重新提取"测试"项目的基本信息
2. 查看data_json，确认新字段存在
3. 查看前端展示，确认不报错
4. （可选）查看原始JSON，确认结构正确

### 步骤6：前端增强（后续可选）
- 增加description字段的展示
- 增加structured字段的动态展示
- 增加base自定义字段的展示

---

## 测试验证计划

### 测试1：基本兼容性测试

**验证点**：
- ✅ 前端能正常加载页面
- ✅ base字段正常显示（核心字段）
- ✅ technical_parameters表格正常显示
- ✅ business_terms表格正常显示
- ✅ 无JavaScript错误

**SQL验证**：
```sql
-- 查看新增字段
SELECT 
    data_json->'base' as base,
    jsonb_pretty(data_json->'technical_parameters'->0) as first_tech
FROM tender_project_info
WHERE project_id = 'tp_9160ce348db444e9b5a3fa4b66e8680a';
```

### 测试2：新字段存在性测试

**验证点**：
- ✅ base中有自定义字段
- ✅ technical_parameters中有description或structured字段
- ✅ business_terms中有description或structured字段

**SQL验证**：
```sql
-- 检查是否有description字段
SELECT 
    COUNT(*) FILTER (WHERE jsonb_typeof(tp->>'description') = 'string') as has_description,
    COUNT(*) FILTER (WHERE tp ? 'structured') as has_structured
FROM tender_project_info,
     jsonb_array_elements(data_json->'technical_parameters') as tp
WHERE project_id = 'tp_9160ce348db444e9b5a3fa4b66e8680a';
```

### 测试3：信息完整性测试

**验证点**：
- ✅ 提取数量增加（技术参数 > 20条，商务条款 > 15条）
- ✅ structured字段内容合理
- ✅ description字段内容完整

---

## 回滚方案

如果测试不通过，可以快速回滚：

```bash
# 恢复Prompt
cp backend/app/works/tender/prompts/project_info_v2.md.backup backend/app/works/tender/prompts/project_info_v2.md

# 重启后端
docker-compose up -d --no-deps backend
```

---

## 风险评估

### ✅ 已确认无风险

1. **数据存储**：JSONB可以存储任意结构 ✅
2. **前端兼容**：使用`?.`和`|| ""`处理缺失字段 ✅
3. **后端处理**：无Schema校验，直接存储 ✅
4. **核心功能**：核心字段保持不变，现有功能不受影响 ✅

### ⚠️ 需要注意

1. **前端展示**：新字段暂时不会显示，需要后续增强
2. **数据一致性**：不同批次提取的结构可能不同（这是预期行为）
3. **LLM理解**：需要测试LLM是否能正确理解新的自由度

---

## 总结

### 方案D的核心优势

1. ✅ **最小侵入**：只修改Prompt，不改代码
2. ✅ **完全兼容**：核心字段保持，前端正常工作
3. ✅ **高度灵活**：LLM有更大自由度
4. ✅ **可渐进增强**：后续可以逐步增强前端展示

### 预期效果

**信息完整性**：
- 技术参数：4条 → 20-50条（提升5-10倍）
- 商务条款：3条 → 15-30条（提升3-5倍）
- base字段：固定11个 → 11个核心 + N个自定义

**LLM自由度**：
- category/term：完全自由定义
- structured：自己决定结构
- description：自由文字描述

---

**实施状态**：📋 待执行  
**预期时间**：15分钟  
**风险等级**：🟢 低风险

