# 前端状态复原说明

**日期**: 2025-12-29  
**问题**: 投标响应抽取按钮不可用，但实际没有抽取数据

---

## 🔍 问题分析

### 根本原因
前端缓存了旧的运行状态（`bidResponseRun`），导致按钮禁用逻辑认为存在一个完成的任务。

### 数据清理已完成 ✅
```sql
-- 已清理的数据
DELETE FROM tender_bid_response_items WHERE project_id='...';  -- 删除6条
DELETE FROM tender_review_items WHERE project_id='...';        -- 删除52条
DELETE FROM tender_runs WHERE run_type IN ('review', 'extract_bid_responses'); -- 删除8条
```

### API验证 ✅
```bash
curl http://localhost:9001/api/apps/tender/projects/{project_id}/runs/latest
# 返回: { "extract_bid_responses": null, ... }
```

后端已经正确返回 `null`，说明没有运行记录。

---

## ✅ 解决方案（用户操作）

### 方案1：刷新页面（推荐）
最简单的方法：
- **Windows/Linux**: 按 `F5` 或 `Ctrl+R`
- **Mac**: 按 `Cmd+R`
- **强制刷新**: `Ctrl+F5` (Windows) 或 `Cmd+Shift+R` (Mac)

刷新后，前端会重新从后端加载运行状态，`bidResponseRun` 将变为 `null`，按钮恢复可用。

### 方案2：切换项目
1. 点击切换到其他项目
2. 再切换回当前项目
3. 前端会重新加载运行状态

---

## 🔧 技术细节

### 前端状态管理流程

```typescript
// TenderWorkspace.tsx: 1584-1644
const loadAndRestoreRuns = async () => {
  const data = await api.get(`/api/apps/tender/projects/${projectId}/runs/latest`);
  
  const bidResponseRunData = data.extract_bid_responses || null; // ← 现在是null
  
  updateProjectState(projectId, {
    runs: {
      bidResponse: bidResponseRunData, // ← 更新为null
      // ...
    }
  });
};

// 项目切换时触发
useEffect(() => {
  loadAndRestoreRuns();
}, [currentProject?.id]);
```

### 按钮禁用逻辑

```typescript
// TenderWorkspace.tsx: 2427
<button 
  disabled={bidResponseRun?.status === 'running' || !selectedBidder}
>
  {bidResponseRun?.status === 'running' ? '抽取中...' : '开始抽取'}
</button>
```

**禁用条件**：
- `bidResponseRun?.status === 'running'`: 正在运行时禁用 ✅
- `!selectedBidder`: 未选择投标人时禁用 ✅

**启用条件**：
- `bidResponseRun === null`: 没有运行记录 ✅
- `bidResponseRun.status !== 'running'`: 已完成的任务 ✅

---

## 🎯 验证步骤

刷新页面后，验证以下内容：

### 1. 浏览器控制台
```javascript
// 打开控制台（F12），查看日志
[loadAndRestoreRuns] 收到run状态: { extract_bid_responses: null, ... }
```

### 2. 按钮状态
- ✅ "开始抽取" 按钮应该**可点击**（非灰色）
- ✅ 按钮文字显示 "开始抽取"（不是"抽取中..."）

### 3. 运行状态显示
- 如果有运行状态区域，应该不显示或显示为空

---

## 🚀 后续操作

### 1. 重新抽取投标响应
1. 确保已选择投标人
2. 点击"开始抽取"按钮
3. 等待抽取完成

### 2. 运行审核
抽取完成后，可以点击"开始审核"按钮运行新的审核流程。

新的审核将使用最新代码，正确填充以下字段：
- ✅ `status` (PASS/WARN/FAIL/PENDING)
- ✅ `evaluator` (hard_gate/quant_check/semantic_llm/consistency)
- ✅ `review_run_id` (关联到tender_runs)
- ✅ `requirement_id` 和 `matched_response_id` (可追溯性)
- ✅ `evidence_json` (统一的证据结构，包含role=tender/bid)

---

## 📝 相关修复

### 已修复的问题
1. **UUID类型不匹配** (Migration 039): `review_run_id` 从 UUID 改为 TEXT
2. **投标响应表格样式** (Commit 6845a17): 统一为深色主题
3. **前端资源404** (Commit f11adf4): vite.config.ts base路径修复

### Git提交记录
```bash
f11adf4 - 🐛 修复: 前端资源404错误（base路径配置）
e795dc5 - 🐛 修复: 审核任务失败（review_run_id类型不匹配）
6845a17 - 🎨 优化: 投标响应表格样式与风险识别保持一致
195a807 - 📝 文档: 问题修复总结（404 + 审核失败）
```

---

## ⚠️ 注意事项

### 数据库已清理
以下数据已被清理，需要重新生成：
- ❌ 投标响应数据（需重新抽取）
- ❌ 审核结果（需重新运行审核）

### 保留的数据
以下数据未受影响：
- ✅ 项目信息
- ✅ 招标要求（风险识别结果）
- ✅ 文档目录
- ✅ 上传的文件资产

---

## 🎉 总结

**操作步骤**：
1. ✅ 数据库清理完成
2. ⏳ **用户刷新页面** ← 当前需要做的
3. ⏳ 重新抽取投标响应
4. ⏳ 重新运行审核

**预期结果**：
- 按钮恢复可用
- 可以重新抽取投标响应
- 新的审核结果将包含完整的字段信息

