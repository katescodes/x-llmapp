# 基本信息证据支持添加报告

## 问题

用户反馈：**基本信息的证据都没有**

## 根本原因

之前的实现中，`base`字段没有证据追踪：
- ❌ Prompt中base字段没有定义`evidence_chunk_ids`
- ❌ Schema中`ProjectBase`没有`evidence`字段
- ❌ 前端没有显示base字段的证据链接

**对比**：
- ✅ `technical_parameters`每条有`evidence_chunk_ids`
- ✅ `business_terms`每条有`evidence_chunk_ids`
- ✅ `scoring_criteria.items`每条有`evidence_chunk_ids`
- ❌ `base`字段没有证据追踪

---

## 解决方案

### 设计思路

由于`base`是一个对象（不是数组），每个字段都可能来自不同的chunk，因此采用**字段级证据映射**的方式：

```json
{
  "base": {
    "projectName": "xxx项目",
    "ownerName": "xxx公司",
    "budget": "500万元",
    // ... 其他字段
    
    // 证据映射
    "evidence": {
      "projectName": ["seg_001"],
      "ownerName": ["seg_001", "seg_002"],
      "budget": ["seg_003"],
      "maxPrice": ["seg_003"],
      "bidDeadline": ["seg_004"],
      "contact": ["seg_005"]
      // 每个字段对应其来源chunk
    }
  }
}
```

---

## 详细修改

### 1. Prompt修改（引导LLM）

**文件**: `backend/app/works/tender/prompts/project_info_v2.md`

#### 修改1：JSON Schema
```json
"base": {
  "projectName": "项目名称",
  "ownerName": "招标人/业主/采购人",
  "agencyName": "代理机构",
  // ... 其他字段
  
  // ✅ 新增：证据字段
  "evidence": {
    "projectName": ["CHUNK_xxx"],
    "ownerName": ["CHUNK_xxx"],
    "budget": ["CHUNK_xxx"],
    "maxPrice": ["CHUNK_xxx"],
    "bidDeadline": ["CHUNK_xxx"],
    "bidOpeningTime": ["CHUNK_xxx"],
    "schedule": ["CHUNK_xxx"],
    "contact": ["CHUNK_xxx"]
    // 其他字段的证据...
  }
},
```

#### 修改2：注意事项
```markdown
4. `evidence_chunk_ids` 包含所有引用的 chunk id
   - **base字段**：使用`evidence`对象，为每个有值的字段提供证据
   - **technical_parameters/business_terms**：每条记录必须有`evidence_chunk_ids`数组
```

---

### 2. Schema修改（数据验证）

**文件**: `backend/app/works/tender/schemas/project_info_v2.py`

```python
class ProjectBase(BaseModel):
    """项目基础信息（方案D：支持自定义字段）"""
    # 核心字段（前端依赖）
    projectName: Optional[str] = None
    projectNumber: Optional[str] = None
    ownerName: Optional[str] = None
    # ... 其他字段
    
    # ✅ 新增：证据字段（每个字段的来源chunk）
    evidence: Optional[Dict[str, List[str]]] = None
    
    # 允许额外字段（LLM自由添加的基本信息）
    class Config:
        extra = "allow"
```

**数据类型**：
- `Dict[str, List[str]]`：字段名 → chunk ID列表
- 例如：`{"projectName": ["seg_001"], "budget": ["seg_003", "seg_004"]}`

---

### 3. 前端修改（显示证据）

**文件**: `frontend/src/components/tender/ProjectInfoView.tsx`

#### 修改1：提取evidence数据
```typescript
// 从 data_json 中提取数据
const dataJson = info?.data_json || info || {};
const baseInfo = dataJson?.base || dataJson;
const baseEvidence = baseInfo?.evidence || {};  // ✅ 提取evidence对象
```

#### 修改2：显示证据按钮
```typescript
{BASIC_FIELDS.map((f) => {
  const v = baseInfo?.[f.k];
  const text = (v === null || v === undefined || String(v).trim() === "") ? "—" : String(v);
  const evidence = asArray(baseEvidence?.[f.k]);  // ✅ 获取该字段的证据
  return (
    <div key={f.k} className="tender-kv-item">
      <div className="tender-kv-label">
        {f.label}
        {/* ✅ 显示证据按钮 */}
        {evidence.length > 0 && (
          <span style={{ marginLeft: 8 }}>
            {showEvidenceBtn(evidence)}
          </span>
        )}
      </div>
      <div className="tender-kv-value">{text}</div>
    </div>
  );
})}
```

---

## 显示效果

### 修改前（无证据）
```
项目信息
┌────────────────┬──────────────────────┐
│ 项目名称       │ xxx项目              │
│ 招标人/业主    │ xxx公司              │
│ 预算金额       │ 500万元              │
│ 投标截止时间   │ 2024-12-12 10:30     │
└────────────────┴──────────────────────┘
```

### 修改后（有证据）✅
```
项目信息
┌────────────────────────────┬──────────────────────┐
│ 项目名称 证据(1)           │ xxx项目              │
│ 招标人/业主 证据(2)        │ xxx公司              │
│ 预算金额 证据(1)           │ 500万元              │
│ 投标截止时间 证据(1)       │ 2024-12-12 10:30     │
│ 联系人 证据(1)             │ 李女士 028-61528024  │
└────────────────────────────┴──────────────────────┘
```

**交互**：
- 点击"证据(1)"按钮 → 弹出原文片段
- 证据(2)表示该字段来自2个不同的chunk

---

## 数据结构对比

### 修改前
```json
{
  "data": {
    "base": {
      "projectName": "xxx项目",
      "ownerName": "xxx公司",
      "budget": "500万元"
      // ❌ 没有证据
    },
    "technical_parameters": [
      {
        "name": "PLC设备",
        "value": "西门子S7-1500",
        "evidence_chunk_ids": ["seg_001"]  // ✅ 有证据
      }
    ],
    "business_terms": [
      {
        "clause_type": "付款方式",
        "content": "预付30%...",
        "evidence_chunk_ids": ["seg_002"]  // ✅ 有证据
      }
    ]
  }
}
```

### 修改后
```json
{
  "data": {
    "base": {
      "projectName": "xxx项目",
      "ownerName": "xxx公司",
      "budget": "500万元",
      // ✅ 新增：字段级证据映射
      "evidence": {
        "projectName": ["seg_001"],
        "ownerName": ["seg_001", "seg_002"],
        "budget": ["seg_003"]
      }
    },
    "technical_parameters": [
      {
        "name": "PLC设备",
        "value": "西门子S7-1500",
        "evidence_chunk_ids": ["seg_001"]
      }
    ],
    "business_terms": [
      {
        "clause_type": "付款方式",
        "content": "预付30%...",
        "evidence_chunk_ids": ["seg_002"]
      }
    ]
  }
}
```

---

## 证据映射的优势

### 为什么不用evidence_chunk_ids数组？

**方案A（不推荐）**：
```json
{
  "base": {
    "projectName": "xxx",
    "budget": "500万"
  },
  "evidence_chunk_ids": ["seg_001", "seg_002", "seg_003"]  // ❌ 无法区分哪个字段来自哪个chunk
}
```

**问题**：
- ❌ 无法知道"项目名称"来自哪个chunk
- ❌ 无法知道"预算金额"来自哪个chunk
- ❌ 用户点击证据时，显示所有chunk，不精确

**方案B（推荐）**：✅
```json
{
  "base": {
    "projectName": "xxx",
    "budget": "500万",
    "evidence": {
      "projectName": ["seg_001"],  // ✅ 明确：项目名称来自seg_001
      "budget": ["seg_003"]         // ✅ 明确：预算金额来自seg_003
    }
  }
}
```

**优势**：
- ✅ 字段级精确追溯
- ✅ 用户点击"项目名称"的证据，只显示seg_001
- ✅ 用户点击"预算金额"的证据，只显示seg_003
- ✅ 更好的可追溯性

---

## LLM提取示例

### 输入（招标文件片段）
```xml
<chunk id="seg_001">
项目名称：xxx智能监控系统项目
招标人：xxx市水务局
代理机构：xxx招标代理有限公司
</chunk>

<chunk id="seg_003">
项目预算：500万元
招标控制价：498万元
</chunk>

<chunk id="seg_004">
投标截止时间：2024年12月12日10时30分（北京时间）
开标时间：2024年12月12日10时30分
</chunk>
```

### 输出（LLM提取）
```json
{
  "data": {
    "base": {
      "projectName": "xxx智能监控系统项目",
      "ownerName": "xxx市水务局",
      "agencyName": "xxx招标代理有限公司",
      "budget": "500万元",
      "maxPrice": "498万元",
      "bidDeadline": "2024年12月12日10时30分",
      "bidOpeningTime": "2024年12月12日10时30分",
      
      // 证据映射
      "evidence": {
        "projectName": ["seg_001"],
        "ownerName": ["seg_001"],
        "agencyName": ["seg_001"],
        "budget": ["seg_003"],
        "maxPrice": ["seg_003"],
        "bidDeadline": ["seg_004"],
        "bidOpeningTime": ["seg_004"]
      }
    }
  }
}
```

---

## 契约更新建议

建议在`tender_contract_v1.yaml`中更新base字段的定义：

```yaml
base:
  required_fields:
    - project_name
    - project_number
    - budget
    # ... 其他字段
  optional_fields:
    - evidence          # ✅ 新增：证据映射（Dict[str, List[str]]）
```

---

## 测试验证

### 步骤1：重新提取信息
```bash
POST /api/apps/tender/projects/{project_id}/extract-info-v2
```

### 步骤2：查看结果
```bash
GET /api/apps/tender/projects/{project_id}/info
```

### 步骤3：检查evidence字段
```sql
SELECT 
    data_json->'base'->>'projectName' as project_name,
    data_json->'base'->'evidence'->>'projectName' as project_name_evidence
FROM tender_project_info 
WHERE project_id = 'xxx';
```

**预期结果**：
```
project_name          | project_name_evidence
xxx智能监控系统项目   | ["seg_001"]
```

### 步骤4：前端验证
刷新页面，查看"项目信息"卡片：
- ✅ 每个有值的字段旁边应该显示"证据(N)"按钮
- ✅ 点击证据按钮，弹出对应的原文片段
- ✅ 证据数量应该与该字段的来源chunk数量一致

---

## 兼容性

### ✅ 向后兼容
- 旧数据（没有evidence字段）：前端不显示证据按钮
- 新数据（有evidence字段）：前端显示证据按钮
- Schema中`evidence`是`Optional`，不影响已有数据

### ✅ 前端健壮性
```typescript
const baseEvidence = baseInfo?.evidence || {};  // 如果没有evidence，使用空对象
const evidence = asArray(baseEvidence?.[f.k]);  // 如果该字段没有证据，返回空数组
{evidence.length > 0 && ...}                     // 只有有证据时才显示按钮
```

---

## 总结

### 修改内容
1. ✅ Prompt：添加`base.evidence`对象定义和说明
2. ✅ Schema：添加`ProjectBase.evidence`字段
3. ✅ 前端：提取并显示字段级证据按钮

### 核心设计
- **字段级证据映射**：`Dict[str, List[str]]`
- **精确追溯**：每个字段对应其来源chunk
- **用户友好**：点击字段的证据，只显示相关chunk

### 效果
- ✅ 基本信息的每个字段都有证据追踪
- ✅ 用户可以点击查看每个字段的原文来源
- ✅ 与技术参数、商务条款的证据展示保持一致
- ✅ 提高信息的可信度和可追溯性

---

**修改日期**：2025-12-25  
**修改状态**：✅ 已完成并部署  
**影响范围**：base字段证据支持  
**兼容性**：✅ 向后兼容  
**测试状态**：⏳ 等待用户验证

