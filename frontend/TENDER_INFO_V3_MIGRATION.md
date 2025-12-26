# 前端迁移指南：Tender Info V3

## 概述

后端招标信息抽取已从旧的 4 阶段结构（base/technical/business/scoring）升级为 **V3 九大类结构**。

前端需要相应更新以适配新的数据结构。

## 数据结构变更

### 旧结构（已废弃）

```typescript
interface OldTenderInfo {
  base: { ... };
  technical_parameters: { ... };
  business_terms: { ... };
  scoring_criteria: { ... };
}
```

### 新结构（V3）

```typescript
interface TenderInfoV3 {
  schema_version: "tender_info_v3";
  project_overview: { ... };        // 项目概况
  scope_and_lots: { ... };          // 范围与标段
  schedule_and_submission: { ... }; // 进度与提交
  bidder_qualification: { ... };    // 投标人资格
  evaluation_and_scoring: { ... };  // 评审与评分
  business_terms: { ... };          // 商务条款
  technical_requirements: { ... };  // 技术要求
  document_preparation: { ... };    // 文件编制
  bid_security: { ... };            // 投标保证金
}
```

详细类型定义见 `frontend/src/types/tenderInfoV3.ts`。

## 迁移步骤

### 1. 导入新类型定义

```typescript
import {
  TenderInfoV3,
  isTenderInfoV3,
  TENDER_INFO_V3_CATEGORIES,
  TENDER_INFO_V3_CATEGORY_LABELS,
} from '@/types/tenderInfoV3';
```

### 2. 更新组件 props 和 state

```typescript
// 旧代码
const [tenderInfo, setTenderInfo] = useState<any>(null);

// 新代码
const [tenderInfo, setTenderInfo] = useState<TenderInfoV3 | null>(null);
```

### 3. 使用类型守卫检查版本

```typescript
// API 返回的数据
const response = await fetch(`/api/projects/${projectId}/project-info`);
const data = await response.json();

if (isTenderInfoV3(data.data_json)) {
  // V3 结构
  setTenderInfo(data.data_json);
} else {
  // 旧结构或错误
  console.error("Unexpected data structure");
}
```

### 4. 更新渲染逻辑

#### 旧代码（基于4阶段）

```typescript
// 显示基本信息
<div>
  <h3>基本信息</h3>
  <p>项目名称：{tenderInfo.base?.project_name}</p>
  <p>预算：{tenderInfo.base?.budget}</p>
</div>

// 显示技术参数
<div>
  <h3>技术参数</h3>
  {/* ... */}
</div>
```

#### 新代码（基于9大类）

```typescript
// 使用类别常量遍历
{TENDER_INFO_V3_CATEGORIES.map((category) => (
  <div key={category}>
    <h3>{TENDER_INFO_V3_CATEGORY_LABELS[category]}</h3>
    {renderCategory(tenderInfo[category], category)}
  </div>
))}

// 或者单独渲染
<div>
  <h3>项目概况</h3>
  <p>项目名称：{tenderInfo.project_overview?.project_name}</p>
  <p>预算金额：{tenderInfo.project_overview?.budget_amount}</p>
  <p>招标控制价：{tenderInfo.project_overview?.control_price}</p>
</div>

<div>
  <h3>投标人资格</h3>
  <ul>
    {tenderInfo.bidder_qualification?.qualification_requirements?.map((req, idx) => (
      <li key={idx}>{req}</li>
    ))}
  </ul>
</div>
```

### 5. 更新表单编辑逻辑

```typescript
// 旧代码
const updateBase = (field: string, value: any) => {
  setTenderInfo({
    ...tenderInfo,
    base: {
      ...tenderInfo.base,
      [field]: value,
    },
  });
};

// 新代码
const updateCategory = (category: keyof TenderInfoV3, field: string, value: any) => {
  if (category === 'schema_version') return; // 不可编辑
  
  setTenderInfo({
    ...tenderInfo,
    [category]: {
      ...tenderInfo[category],
      [field]: value,
    },
  });
};

// 示例：更新项目名称
updateCategory('project_overview', 'project_name', '新项目名称');
```

### 6. 更新 API 调用

API 路由不变，但返回的 `data_json` 结构变为 V3：

```typescript
// GET /api/projects/{project_id}/project-info
// Response:
{
  "id": "info_001",
  "project_id": "proj_001",
  "data_json": {
    "schema_version": "tender_info_v3",
    "project_overview": { ... },
    "scope_and_lots": { ... },
    // ... 其他 7 个类别
  },
  "created_at": "2025-12-26T12:00:00Z",
  "updated_at": "2025-12-26T12:00:00Z"
}
```

### 7. 更新搜索和过滤逻辑

```typescript
// 旧代码：在 base 中搜索
const searchInBase = (query: string) => {
  return JSON.stringify(tenderInfo.base).includes(query);
};

// 新代码：在所有类别中搜索
const searchInAllCategories = (query: string) => {
  return TENDER_INFO_V3_CATEGORIES.some((category) => 
    JSON.stringify(tenderInfo[category]).includes(query)
  );
};
```

## 主要影响的组件（示例）

### TenderWorkspace 组件

- **位置**：`frontend/src/components/TenderWorkspace.tsx`（假设）
- **修改内容**：
  - 更新 state 类型为 `TenderInfoV3`
  - 使用 `isTenderInfoV3()` 检查数据版本
  - 更新所有引用旧字段的地方

### TenderInfoDisplay 组件

- **位置**：`frontend/src/components/TenderInfoDisplay.tsx`（假设）
- **修改内容**：
  - 使用 `TENDER_INFO_V3_CATEGORIES` 遍历类别
  - 使用 `TENDER_INFO_V3_CATEGORY_LABELS` 显示中文名称
  - 更新字段映射

### TenderInfoEditor 组件

- **位置**：`frontend/src/components/TenderInfoEditor.tsx`（假设）
- **修改内容**：
  - 更新表单字段
  - 更新验证逻辑
  - 更新提交逻辑

## 向后兼容性

如果需要支持旧数据，可以添加适配器：

```typescript
function adaptOldToV3(oldData: any): TenderInfoV3 {
  return {
    schema_version: "tender_info_v3",
    project_overview: {
      project_name: oldData.base?.project_name,
      budget_amount: oldData.base?.budget,
      // ... 其他字段映射
    },
    technical_requirements: {
      technical_specifications: oldData.technical_parameters?.specifications,
      // ... 其他字段映射
    },
    business_terms: {
      contract_terms: oldData.business_terms?.terms,
      // ... 其他字段映射
    },
    evaluation_and_scoring: {
      evaluation_method: oldData.scoring_criteria?.method,
      // ... 其他字段映射
    },
    // 其他类别填充默认值
    scope_and_lots: {},
    schedule_and_submission: {},
    bidder_qualification: {},
    document_preparation: {},
    bid_security: {},
  };
}
```

## 测试建议

1. **单元测试**：验证类型守卫和适配器
2. **集成测试**：验证 API 调用和数据渲染
3. **端到端测试**：验证完整的用户流程

## 常见问题

### Q: 旧数据怎么办？

**A**: 后端会自动迁移旧数据到 V3 结构。前端只需检查 `schema_version` 字段。

### Q: 如果某个类别为空怎么办？

**A**: 所有类别字段都是可选的。前端应优雅处理空值（使用 `?.` 操作符）。

### Q: 如何快速找到需要修改的组件？

**A**: 搜索关键字：`base`、`technical_parameters`、`business_terms`、`scoring_criteria`

## 总结

- ✅ 使用新的类型定义 `TenderInfoV3`
- ✅ 使用类型守卫 `isTenderInfoV3()` 检查数据版本
- ✅ 使用 `TENDER_INFO_V3_CATEGORIES` 和 `TENDER_INFO_V3_CATEGORY_LABELS` 遍历和显示
- ✅ 更新所有引用旧字段的地方
- ✅ 添加单元测试和集成测试
- ✅ 优雅处理空值和兼容性问题

---

**文档版本**: 1.0  
**最后更新**: 2025-12-26

