# Step A 完成总结

## ✅ 已完成

### 1. 数据库 Schema 更新
- **Migration 038**: `/aidata/x-llmapp1/backend/migrations/038_add_review_items_traceability.sql`
  - 添加 `requirement_id` TEXT 字段（关联 tender_requirements.requirement_id）
  - 添加 `matched_response_id` UUID 字段（关联 tender_bid_response_items.id）
  - 添加 `review_run_id` UUID 字段（审核批次ID）
  - 添加索引以支持查询

### 2. 代码修改
- **review_pipeline_v3.py**:
  - 添加 `from psycopg.rows import dict_row` 确保返回字典
  - `run_pipeline()` 增加 `review_run_id` 参数
  - 所有生成 result 的地方添加 `matched_response_id` 字段
  - `_load_requirements()` 和 `_load_responses()` 使用 `row_factory=dict_row`
  - `_save_review_items()` 保存 `requirement_id`, `matched_response_id`, `review_run_id`

- **review_v3_service.py**:
  - 调用 `pipeline.run_pipeline()` 时传递 `review_run_id`

### 3. Git 提交
- Commit: `bfec95b` "Step A: 添加可追溯性字段"

## 🚧 当前状态

### 问题：固定流水线对旧数据不生成审核项
- **原因**: 旧数据的 `tender_requirements` 表中 `eval_method` 字段为空
- **影响**: `_hard_gate()`, `_quant_checks()` 等方法会跳过所有条款
- **结果**: 审核项数量为 0，无法验收可追溯性字段填充情况

### 数据验证
```sql
-- 查询发现:
SELECT COUNT(*) FROM tender_requirements 
WHERE project_id = 'tp_3f49f66ead6d46e1bac3f0bd16a3efe9' 
AND (eval_method IS NULL OR eval_method = '');
-- 结果: 52 条（全部）

-- 查询发现:
SELECT COUNT(*) FROM tender_bid_response_items 
WHERE project_id = 'tp_3f49f66ead6d46e1bac3f0bd16a3efe9' AND bidder_name = '123';
-- 结果: 6 条
```

## 📋 后续步骤依赖

要让 Step A 的可追溯性字段真正起作用，需要完成:

1. **Step B (P0)**: 修复 Mapping
   - 当前 `_build_candidates()` 只做维度匹配
   - 需要添加兜底逻辑：即使 `eval_method` 为空，也应该生成候选对
   - 否则流水线永远不会产生审核项

2. **Step C (P0)**: 语义审核降级 PENDING
   - 当前 `_llm_semantic_review()` 返回假的 PASS
   - 应改为返回 PENDING

3. **Step D (P1)**: NUMERIC 真实比较
4. **Step E (P1)**: Consistency 归一化

## ✅ 验收标准（待后续步骤完成后）

```sql
SELECT
    count(*) as total,
    sum(case when requirement_id is not null and requirement_id != '' then 1 else 0 end) as has_req_id,
    sum(case when matched_response_id is not null then 1 else 0 end) as has_resp_id,
    sum(case when review_run_id is not null then 1 else 0 end) as has_run_id
FROM tender_review_items
WHERE project_id = '<project_id>' AND bidder_name = '<bidder_name>';

-- 期望:
-- has_req_id / total >= 95%
-- has_resp_id / total > 0 (对于非缺失条款)
-- has_run_id / total = 100%
```

## 🔧 快速修复建议

如果要立即验收 Step A，可以临时修改 `_build_candidates()` 添加兜底逻辑：

```python
def _build_candidates(self, requirements, responses):
    candidates = []
    for req in requirements:
        req_dimension = req.get("dimension", "")
        matched = [r for r in responses if r.get("dimension") == req_dimension]
        best_response = matched[0] if matched else None
        
        candidates.append({
            "requirement": req,
            "response": best_response,
            "requirement_id": req.get("requirement_id"),
            "dimension": req_dimension,
        })
    return candidates
```

并修改 `_hard_gate()` 添加兜底规则：

```python
def _hard_gate(self, candidates):
    results = []
    for candidate in candidates:
        req = candidate["requirement"]
        resp = candidate["response"]
        eval_method = req.get("eval_method") or "PRESENCE"  # 兜底
        is_hard = req.get("is_hard", False) or req.get("must_reject", False)
        
        # 对所有 is_hard=true 的条款进行基本检查
        if is_hard:
            status, remark, rule_trace = self._evaluate_deterministic(req, resp, eval_method)
            result = {
                "requirement_id": req.get("requirement_id"),
                "matched_response_id": str(resp.get("id")) if resp else None,
                # ... 其他字段
            }
            results.append(result)
    return results
```

## 📊 当前 Docker 状态

```
✅ Migration 038 已执行
✅ Backend & Worker 已重启并rebuild
✅ 代码已更新到容器
✅ 固定流水线模式已生效（FIXED_PIPELINE）
❌ 审核项数量为 0（等待 Step B 修复）
```

## 下一步行动

**立即执行 Step B**，修复 Mapping 和 hard_gate 逻辑，使流水线能处理旧数据，然后回来验收 Step A 的可追溯性字段。

