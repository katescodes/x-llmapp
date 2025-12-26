# 前端展示组件更新 - V3 九大类自动适配

## 📦 新增组件

### `ProjectInfoV3View.tsx`

**位置**: `frontend/src/components/tender/ProjectInfoV3View.tsx`

**特性**:
- ✅ **自动检测** schema_version，判断是 V3 还是旧版
- ✅ **V3 结构**：自动展示九大类，无需手动适配
- ✅ **旧版结构**：显示警告并回退到 JSON 视图
- ✅ **证据链支持**：每个类别和字段都可以查看证据
- ✅ **视图切换**：卡片视图 ↔ JSON 视图

---

## 🚀 使用方法

### 方法 1: 替换现有组件（推荐）

在 `TenderWorkspace.tsx` 中：

```typescript
// 旧代码（第 1662 行）
import ProjectInfoView from './tender/ProjectInfoView';  // ❌ 旧组件

// 新代码
import ProjectInfoV3View from './tender/ProjectInfoV3View';  // ✅ 新组件

// 使用（无需修改其他代码）
<ProjectInfoV3View info={projectInfo.data_json} onEvidence={showEvidence} />
```

### 方法 2: 共存使用（测试阶段）

```typescript
import ProjectInfoView from './tender/ProjectInfoView';      // 旧组件
import ProjectInfoV3View from './tender/ProjectInfoV3View';  // 新组件
import { isTenderInfoV3 } from '@/types/tenderInfoV3';

// 根据数据格式动态选择组件
{projectInfo && (
  <div style={{ marginTop: '16px' }}>
    {isTenderInfoV3(projectInfo.data_json) ? (
      <ProjectInfoV3View info={projectInfo.data_json} onEvidence={showEvidence} />
    ) : (
      <ProjectInfoView info={projectInfo.data_json} onEvidence={showEvidence} />
    )}
  </div>
)}
```

---

## 🎨 展示效果

### V3 九大类展示

```
┌─────────────────────────────────────────────────┐
│ 招标信息 ✓ V3 九大类              [🔍 JSON 视图] │
├─────────────────────────────────────────────────┤
│                                                 │
│ 📋 项目概况                    [📎 查看证据 (5)] │
│ ┌───────────────────────────────────────────┐   │
│ │ 项目名称: XX政府采购项目                    │   │
│ │ 项目编号: 2025-XXX-001                     │   │
│ │ 预算金额: 1000000                          │   │
│ │ 招标控制价: 980000                         │   │
│ │ ...                                        │   │
│ └───────────────────────────────────────────┘   │
│                                                 │
│ 📦 范围与标段                  [📎 查看证据 (3)] │
│ ┌───────────────────────────────────────────┐   │
│ │ 采购内容: ...                              │   │
│ │ 标段划分: [标段1, 标段2]                   │   │
│ └───────────────────────────────────────────┘   │
│                                                 │
│ 📅 进度与提交                  [📎 查看证据 (4)] │
│ ...                                             │
│                                                 │
│ 共 9 个类别...                                   │
└─────────────────────────────────────────────────┘
```

### 旧版数据展示

```
┌─────────────────────────────────────────────────┐
│ 招标信息 ⚠️ 旧版格式              [🔍 JSON 视图] │
├─────────────────────────────────────────────────┤
│ ⚠️ 当前数据使用旧版格式。                         │
│    请重新抽取项目信息以使用新版 V3 九大类结构。   │
│                                                 │
│ [JSON 数据显示...]                               │
└─────────────────────────────────────────────────┘
```

---

## 🔧 自定义配置

### 1. 修改字段显示顺序

编辑 `tenderInfoV3.ts` 中的 `TENDER_INFO_V3_CATEGORIES` 数组：

```typescript
export const TENDER_INFO_V3_CATEGORIES = [
  "project_overview",          // 第一个显示
  "bidder_qualification",      // 第二个显示
  // ... 调整顺序
];
```

### 2. 修改类别中文名称

编辑 `tenderInfoV3.ts` 中的 `TENDER_INFO_V3_CATEGORY_LABELS`：

```typescript
export const TENDER_INFO_V3_CATEGORY_LABELS: Record<string, string> = {
  project_overview: "项目概况",              // 修改这里
  scope_and_lots: "采购范围与标段划分",      // 更详细的名称
  // ...
};
```

### 3. 自定义字段渲染

在 `ProjectInfoV3View.tsx` 中的 `renderV3Category` 函数中添加自定义逻辑：

```typescript
const renderV3Category = (categoryKey, categoryData, onEvidence) => {
  // ... 现有代码 ...

  // 特殊处理某些类别
  if (categoryKey === 'evaluation_and_scoring') {
    return <CustomScoringView data={categoryData} />;
  }

  // 默认渲染
  return (/* ... */);
};
```

---

## 📊 数据流示例

### 后端 API 返回（V3）

```json
{
  "id": "info_001",
  "project_id": "proj_001",
  "data_json": {
    "schema_version": "tender_info_v3",
    "project_overview": {
      "project_name": "XX政府采购项目",
      "budget_amount": 1000000,
      "evidence_chunk_ids": ["chunk_001", "chunk_002"]
    },
    "scope_and_lots": {
      "procurement_content": "...",
      "evidence_chunk_ids": ["chunk_010"]
    },
    // ... 其他 7 个类别
  }
}
```

### 组件自动检测

```typescript
// 1. 组件接收数据
<ProjectInfoV3View info={projectInfo.data_json} />

// 2. 自动检测版本
const isV3 = isTenderInfoV3(dataJson);  // true

// 3. 遍历九大类
TENDER_INFO_V3_CATEGORIES.forEach(category => {
  renderV3Category(category, dataJson[category]);
});

// 4. 渲染结果：9 个卡片，每个卡片展示一个类别
```

---

## 🧪 测试

### 1. 测试 V3 数据

```typescript
const mockV3Data = {
  schema_version: "tender_info_v3",
  project_overview: {
    project_name: "测试项目",
    budget_amount: 100000,
    evidence_chunk_ids: ["chunk_1"]
  },
  // ... 其他类别
};

<ProjectInfoV3View info={mockV3Data} onEvidence={(ids) => console.log(ids)} />
```

### 2. 测试旧版数据

```typescript
const mockOldData = {
  base: { projectName: "旧项目", budget: 100000 },
  technical_parameters: [...],
  business_terms: [...]
};

<ProjectInfoV3View info={mockOldData} />
// 应该显示 "⚠️ 旧版格式" 警告
```

### 3. 测试证据链

```typescript
const onEvidence = (chunkIds: string[]) => {
  console.log('查看证据:', chunkIds);
  // 调用原有的 showEvidence 函数
  showEvidence(chunkIds);
};

<ProjectInfoV3View info={data} onEvidence={onEvidence} />
```

---

## ⚠️ 注意事项

### 1. CSS 样式依赖

组件使用了以下 CSS 类（需要确保样式文件中已定义）：

- `.source-card` - 卡片容器
- `.tender-kv-grid` - KV 网格布局
- `.tender-kv-item` - KV 项目
- `.tender-kv-label` - KV 标签
- `.tender-kv-value` - KV 值
- `.link-button` - 链接按钮
- `.md-pre` - Markdown 预格式化

如果样式缺失，可以添加：

```css
.tender-kv-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.tender-kv-item {
  display: flex;
  flex-direction: column;
}

.tender-kv-label {
  font-weight: 600;
  color: #666;
  margin-bottom: 4px;
}

.tender-kv-value {
  color: #333;
}
```

### 2. 类型导入

确保 `tsconfig.json` 中配置了路径别名：

```json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

### 3. 向后兼容

- ✅ 新组件完全兼容旧数据（显示警告 + JSON 视图）
- ✅ 可以与旧组件共存（条件渲染）
- ✅ 渐进式升级（先测试，再替换）

---

## 📈 性能优化

### 1. 使用 React.memo

```typescript
export default React.memo(ProjectInfoV3View);
```

### 2. 懒加载大数据

```typescript
const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());

// 只渲染展开的类别
{expandedCategories.has(categoryKey) && renderV3Category(...)}
```

---

## 🔗 相关文档

- **类型定义**: `frontend/src/types/tenderInfoV3.ts`
- **迁移指南**: `frontend/TENDER_INFO_V3_MIGRATION.md`
- **后端 Schema**: `backend/app/works/tender/schemas/tender_info_v3.py`
- **重构报告**: `REFACTORING_COMPLETION_REPORT.md`

---

## ✅ 检查清单

完成前端集成后，请确认：

- [ ] 导入了 `tenderInfoV3.ts` 类型定义
- [ ] 创建了 `ProjectInfoV3View.tsx` 组件
- [ ] 在 `TenderWorkspace.tsx` 中使用新组件
- [ ] 测试了 V3 数据展示
- [ ] 测试了旧版数据回退
- [ ] 测试了证据链功能
- [ ] 检查了 CSS 样式
- [ ] 在开发环境验证通过

---

**最后更新**: 2025-12-26  
**组件版本**: 1.0  
**兼容性**: 支持 V3 + 向后兼容旧版

