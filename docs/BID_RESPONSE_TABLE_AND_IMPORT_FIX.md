# 投标响应表格展示与导入路径修复

## 1. 表格展示改造

### 问题
投标响应抽取结果原本使用卡片列表展示，不便于查看和对比大量数据。

### 解决方案
创建专门的表格组件 `BidResponseTable`，参考系统中风险识别和审核结果的表格样式。

### 新增文件
**`/aidata/x-llmapp1/frontend/src/components/tender/BidResponseTable.tsx`**

#### 功能特性

1. **统计信息展示**
   - 绿色卡片显示按维度统计的数量
   - 总计显示
   - 视觉上与数据表格区分

2. **筛选功能**
   - 维度筛选：下拉框选择特定维度
   - 关键词搜索：支持搜索维度/类型/内容/投标人
   - 实时显示筛选后的数量

3. **表格列**
   | 列名 | 宽度 | 说明 |
   |------|------|------|
   | # | 50px | 序号 |
   | 投标人 | 120px | 投标人名称 |
   | 维度 | 110px | 响应维度（带标签） |
   | 类型 | 90px | 响应类型（文本/文档引用/结构化/数值） |
   | 响应内容 | 自适应 | 可滚动查看，最高100px |
   | 证据 | 120px | 查看证据按钮 |

4. **类型标签**
   ```typescript
   const typeMap = {
     text: { bg: "#3b82f6", text: "文本" },
     document_ref: { bg: "#8b5cf6", text: "文档引用" },
     structured: { bg: "#10b981", text: "结构化" },
     number: { bg: "#f59e0b", text: "数值" },
   };
   ```

5. **维度标签**
   - 浅蓝色背景 (`#e0f2fe`)
   - 深蓝色文字 (`#0369a1`)

### 修改的文件

**`/aidata/x-llmapp1/frontend/src/components/TenderWorkspace.tsx`**

#### 1. 导入新组件
```typescript
import BidResponseTable from './tender/BidResponseTable';
```

#### 2. 简化Tab⑤的展示逻辑
```typescript
// 修改前：卡片列表（约60行代码）
{bidResponseStats.length > 0 && (
  <div style={{ marginTop: '16px' }}>
    <h5>抽取统计</h5>
    {/* 统计展示 */}
  </div>
)}
{bidResponses.length > 0 && (
  <div style={{ marginTop: '16px' }}>
    <h5>抽取详情</h5>
    {/* 卡片列表 */}
  </div>
)}

// 修改后：表格组件（1个组件调用）
{bidResponses.length > 0 ? (
  <BidResponseTable
    responses={bidResponses}
    stats={bidResponseStats}
    onOpenEvidence={showEvidence}
  />
) : (
  <div className="kb-empty">暂无数据</div>
)}
```

### 展示效果对比

#### 修改前（卡片列表）
```
抽取统计
• 投标人A - technical: 15 条
• 投标人A - price: 8 条
总计: 23 条

抽取详情
┌─────────────────────────────┐
│ 1. technical                │
│ 类型: text | 投标人: A公司   │
│ 响应内容文本...              │
│ [查看证据 (3 条)]            │
└─────────────────────────────┘
┌─────────────────────────────┐
│ 2. price                    │
│ ...                         │
└─────────────────────────────┘
```

#### 修改后（表格）
```
┌──────────────────────────────────────────┐
│ 📊 抽取统计                              │
│ [technical: 15条] [price: 8条]          │
│ 总计: 23 条投标响应数据                  │
└──────────────────────────────────────────┘

投标响应详情  [全部维度▼]  [搜索...] 共23条

┌───┬────────┬──────────┬──────┬─────────────────┬────────┐
│ # │ 投标人 │   维度   │ 类型 │   响应内容      │  证据  │
├───┼────────┼──────────┼──────┼─────────────────┼────────┤
│ 1 │ A公司  │technical │ 文本 │ 端到端闭环...   │查看(3) │
│ 2 │ A公司  │technical │ 文本 │ 整体方案...     │查看(2) │
│ 3 │ A公司  │  price   │ 数值 │ 报价明细...     │查看(1) │
└───┴────────┴──────────┴──────┴─────────────────┴────────┘
```

### 优势

1. ✅ **更高效**：一屏展示更多数据
2. ✅ **易对比**：表格形式便于横向对比
3. ✅ **可筛选**：支持按维度筛选和关键词搜索
4. ✅ **统一风格**：与风险识别、审核结果表格保持一致
5. ✅ **可滚动**：内容超长时自动滚动，不破坏布局

## 2. 导入路径修复

### 问题
审核功能报错：`No module named 'app.works.tender.dao'`

### 根本原因
`TenderDAO` 已迁移到 `app.services.dao.tender_dao`，但 `review_v3_service.py` 仍使用旧路径。

### 修复

**文件**: `/aidata/x-llmapp1/backend/app/works/tender/review_v3_service.py`

```python
# 修改前（错误）
from app.works.tender.dao import TenderDAO

# 修改后（正确）
from app.services.dao.tender_dao import TenderDAO
```

### 验证
重启后端后，审核功能应该正常工作。

## 3. 测试步骤

### 测试表格展示
1. 进入"测试2"项目
2. 进入Tab⑤投标响应抽取
3. 选择投标人（如"123"）
4. 点击"开始抽取"
5. 查看表格展示效果

**预期结果**：
- ✅ 顶部显示统计卡片（绿色背景）
- ✅ 表格显示所有投标响应数据
- ✅ 可以按维度筛选
- ✅ 可以搜索关键词
- ✅ 点击"查看证据"按钮能打开证据侧边栏

### 测试审核功能
1. 进入Tab⑥审核
2. 选择投标人
3. 选择自定义规则包（可选）
4. 点击"开始审核"

**预期结果**：
- ✅ 不再报 `No module named 'app.works.tender.dao'` 错误
- ✅ 审核任务正常运行

## 4. 相关文件

### 新增
- `/aidata/x-llmapp1/frontend/src/components/tender/BidResponseTable.tsx` - 投标响应表格组件

### 修改
- `/aidata/x-llmapp1/frontend/src/components/TenderWorkspace.tsx` - 使用表格组件
- `/aidata/x-llmapp1/backend/app/works/tender/review_v3_service.py` - 修复导入路径

## 5. 样式说明

表格使用系统已有的CSS类：
- `.source-card` - 外层容器
- `.tender-table-wrap` - 表格容器
- `.tender-table` - 表格本身
- `.tender-badge` - 标签样式
- `.tender-cell` - 单元格样式
- `.link-button` - 链接按钮样式
- `.kb-doc-meta` - 元信息样式
- `.kb-empty` - 空状态样式

无需额外CSS，直接复用现有样式系统。

## 6. 总结

1. **表格展示**：投标响应数据现在以表格形式展示，更专业、更高效
2. **导入路径**：修复了审核功能的模块导入错误
3. **用户体验**：统一了系统中数据展示的风格，提升了整体一致性

前端和后端都已重启，修改已生效。

