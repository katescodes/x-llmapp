# 投标响应查询问题修复

## 问题描述

用户报告："测试2"项目抽取投标响应后，显示"抽取完成！共抽取 0 条投标响应数据"，但状态显示为 success。

## 问题诊断

### 1. 数据库检查

```sql
-- 查询测试2项目的投标响应数据
SELECT COUNT(*) as count FROM tender_bid_response_items 
WHERE project_id = 'tp_259c05d1979e402db656a58a930467e2';

-- 结果：24 条记录 ✅ 数据已入库
```

```sql
-- 查询投标人名称
SELECT DISTINCT bidder_name FROM tender_bid_response_items 
WHERE project_id = 'tp_259c05d1979e402db656a58a930467e2';

-- 结果：未提供投标人名称 ⚠️ 关键发现
```

```sql
-- 查看数据样本
SELECT id, dimension, bidder_name, response_text 
FROM tender_bid_response_items 
WHERE project_id = 'tp_259c05d1979e402db656a58a930467e2' 
LIMIT 5;

-- 结果：24条数据完整，包含dimension、response_text等字段 ✅
```

### 2. 后端日志检查

```bash
docker logs localgpt-backend 2>&1 | tail -200 | grep "GET /api/apps/tender/projects/.*/bid-responses"
```

发现日志：
```
INFO: "GET /api/apps/tender/projects/tp_259c05d1979e402db656a58a930467e2/bid-responses?bidder_name=123 HTTP/1.1" 200 OK
```

**关键发现**：前端传了 `bidder_name=123`，但数据库中存的是 `bidder_name=未提供投标人名称`

### 3. 问题根源

**流程分析**：
1. ✅ **抽取阶段**：`BidResponseService.extract_bid_response_v1()` 成功从投标文件中抽取了24条响应数据
2. ✅ **入库阶段**：数据成功写入 `tender_bid_response_items` 表
3. ✅ **LLM提取**：LLM从文档中提取的投标人名称为 "未提供投标人名称"（因为文档中可能没有明确的投标人信息）
4. ❌ **查询阶段**：前端传了用户选择的 `bidder_name=123`，但与数据库中的实际值不匹配，导致查询结果为空

**根本原因**：
- 前端 `loadBidResponses` 使用了 `state.selectedBidder` 作为查询条件
- `state.selectedBidder` 是用户在前端选择的投标人名称（如 "123"）
- 但实际入库的 `bidder_name` 是 LLM 从投标文件中提取的值（"未提供投标人名称"）
- 两者不一致，导致 `WHERE bidder_name = %s` 查询不到任何结果

## 修复方案

### 修改前端查询逻辑

**修改文件**: `/aidata/x-llmapp1/frontend/src/components/TenderWorkspace.tsx`

**修改内容**：
```typescript
// 修改前：传入用户选择的bidder_name
const loadBidResponses = useCallback(async (forceProjectId?: string) => {
  // ...
  try {
    const selectedBidderName = state.selectedBidder;
    const params = selectedBidderName ? `?bidder_name=${encodeURIComponent(selectedBidderName)}` : '';
    const data = await api.get(`/api/apps/tender/projects/${projectId}/bid-responses${params}`);
    // ...
  }
}, [currentProject, state.selectedBidder]);

// 修改后：不传bidder_name参数，获取所有数据
const loadBidResponses = useCallback(async (forceProjectId?: string) => {
  // ...
  try {
    // 注意：这里不传bidder_name参数，获取所有投标响应数据
    // 因为实际的bidder_name可能是"未提供投标人名称"或其他LLM提取的值
    // 与用户选择的投标人名称可能不一致
    const data = await api.get(`/api/apps/tender/projects/${projectId}/bid-responses`);
    // ...
  }
}, [currentProject]);
```

**修改理由**：
1. LLM 提取的 `bidder_name` 是非结构化的，可能为 "未提供投标人名称"、"投标人A"、"某某公司" 等各种值
2. 用户在前端选择的投标人名称（用于过滤投标文件）与 LLM 提取的投标人名称不一定匹配
3. 投标响应数据应该展示该项目下的所有投标响应，不应该按 `bidder_name` 过滤
4. 如果需要区分不同投标人的响应，应该在前端UI层面进行展示上的分组，而不是在API查询时过滤

### 后端API保持不变

后端API `/api/apps/tender/projects/{project_id}/bid-responses` 已经支持：
- 不传 `bidder_name` 参数：返回该项目下所有投标响应
- 传 `bidder_name` 参数：返回指定投标人的响应（但不建议使用，因为名称可能不匹配）

## 验证结果

修复后重新测试：

```bash
# 1. 构建前端
cd /aidata/x-llmapp1/frontend && npm run build

# 2. 重启前端容器
docker-compose restart frontend

# 3. 访问前端，切换到"测试2"项目的Tab⑤投标响应抽取
```

**预期结果**：
- ✅ 抽取统计显示：总计 24 条投标响应数据
- ✅ 抽取详情显示：24 条响应的详细信息
- ✅ 每条响应显示：维度、类型、投标人名称（"未提供投标人名称"）、响应内容

## 数据样本

从数据库中查到的数据示例：

```
| dimension | bidder_name      | response_text (摘要)                    |
|-----------|------------------|----------------------------------------|
| technical | 未提供投标人名称 | 端到端闭环：从数据接入到预警输出...       |
| technical | 未提供投标人名称 | 整体方案围绕"统一接入、分层解耦"...       |
| technical | 未提供投标人名称 | 数据进入 → 接入校验 → 入队缓冲...        |
| ...       | ...              | ...                                    |
```

共24条记录，涵盖多个维度（technical等）。

## 深层问题与改进建议

### 问题1：投标人名称不一致

**现状**：
- 用户上传投标文件时选择投标人名称（存在 `tender_project_assets.bidder_name`）
- LLM 抽取投标响应时重新从文档中提取投标人名称（存在 `tender_bid_response_items.bidder_name`）
- 两者可能不一致

**改进建议**：
1. **方案A（推荐）**：在抽取投标响应时，直接使用前端传入的 `bidder_name`，不依赖 LLM 提取
   ```python
   # BidResponseService.extract_bid_response_v1()
   # 修改：extracted_bidder_name = bidder_name（使用传入的值）
   # 而不是：extracted_bidder_name = result.data.get("bidder_name", bidder_name)
   ```

2. **方案B（可选）**：在投标文件上传时，将投标人名称写入文档的元数据，LLM抽取时可以读取
   ```python
   # 上传时在 meta_json 中存储
   meta_json = {"bidder_name": "123", ...}
   # 抽取时从 meta_json 读取
   ```

### 问题2：前端展示优化

**建议**：
- 在抽取详情中按 `bidder_name` 分组展示
- 如果 `bidder_name` 为 "未提供投标人名称"，提示用户该字段由LLM自动提取
- 提供手动修正 `bidder_name` 的功能（批量更新）

## 相关文件

- `/aidata/x-llmapp1/frontend/src/components/TenderWorkspace.tsx` - 前端主文件（已修改）
- `/aidata/x-llmapp1/backend/app/routers/tender.py` - 后端API路由
- `/aidata/x-llmapp1/backend/app/works/tender/bid_response_service.py` - 投标响应抽取服务
- `/aidata/x-llmapp1/backend/app/works/tender/extraction_specs/bid_response_v1.py` - 抽取规范

## 总结

**问题本质**：前端查询条件与数据库实际数据不匹配

**修复方法**：移除前端查询时的 `bidder_name` 过滤条件，返回所有投标响应数据

**后续优化**：统一投标人名称的来源，建议直接使用用户上传时指定的投标人名称，而不是依赖LLM提取

