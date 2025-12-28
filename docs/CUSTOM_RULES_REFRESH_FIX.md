# 自定义规则包"刷新后消失"问题修复

## 问题描述
用户创建自定义规则包后，刷新页面规则包就消失了。

## 根本原因

### 逻辑不一致
1. **创建时**：前端传 `project_id: projectId || null`，如果在项目页面中创建，会传递项目ID
2. **加载时**：前端不传 `project_id` 参数
3. **后端过滤**：不传 `project_id` 时，只返回 `project_id IS NULL` 的共享规则包

### 结果
- 在项目页面创建的规则包有 `project_id`（不是NULL）
- 刷新后查询时，后端只返回 `project_id IS NULL` 的规则包
- 因此新创建的规则包不会被返回，看起来"消失"了

## 解决方案

根据之前的需求："**规则包是对招投标项目都共享的，不属于特定项目**"

### 前端修改
修改 `CustomRulesPage.tsx`，创建规则包时**始终传 `project_id: null`**：

```typescript
// 之前（错误）
project_id: projectId || null,

// 之后（正确）
project_id: null,  // 规则包是共享的，不属于特定项目
```

### 数据库修复
将现有的自定义规则包的 `project_id` 设置为 NULL：

```sql
UPDATE tender_rule_packs
SET project_id = NULL
WHERE pack_type = 'custom' AND project_id IS NOT NULL;
```

## 验证

修复后：
1. 创建规则包时，`project_id` 为 NULL
2. 加载规则包时，后端返回所有 `project_id IS NULL` 的规则包
3. 刷新页面后，规则包仍然可见

## 相关文件
- `frontend/src/components/CustomRulesPage.tsx` - 前端创建逻辑
- `backend/app/services/custom_rule_service.py` - 后端查询逻辑（第310-311行）
- `backend/app/routers/custom_rules.py` - API路由

## 测试步骤
1. 刷新前端页面
2. 创建一个新的自定义规则包
3. 刷新页面
4. 确认规则包仍然存在

