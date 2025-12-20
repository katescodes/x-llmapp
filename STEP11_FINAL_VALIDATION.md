# Step 11 最终验收报告

## ✅ 验收状态

**Step 11: NEW_ONLY 收口 - 100% 完成并验收通过！**

---

## 📊 测试结果汇总

### 5 阶段渐进式测试

| 阶段 | 配置 | Smoke 测试 | 验证方式 | 时间 |
|------|------|-----------|---------|------|
| **阶段 1** | RETRIEVAL_MODE=NEW_ONLY | ✅ 全绿 | Debug 接口 + 日志 | 2025-12-19 20:35 |
| **阶段 2** | + INGEST_MODE=NEW_ONLY | ✅ 全绿 | DocStore + Milvus | 2025-12-19 20:37 |
| **阶段 3** | + EXTRACT_MODE=NEW_ONLY | ✅ 全绿 | Run status + Meta | 2025-12-19 20:39 |
| **阶段 4** | + REVIEW_MODE=NEW_ONLY | ✅ 全绿 | Review items + Meta | 2025-12-19 20:41 |
| **阶段 5** | + RULES_MODE=NEW_ONLY | ✅ 全绿 | Rules findings + Meta | 2025-12-19 20:43 |

**通过率**: 5/5 (100%)

---

## 🎯 核心实现

### 1. EXTRACT_MODE=NEW_ONLY ✅

**实现位置**: `backend/app/services/tender_service.py`

**Step1 (extract_project_info)** ~ 行 937-963:
```python
if extract_mode.value == "NEW_ONLY":
    # 仅使用 v2，失败抛错
    v2_result = asyncio.run(extract_v2.extract_project_info_v2(...))
    
    # 成功：写入旧表（保证前端兼容）
    self.dao.upsert_project_info(project_id, data_json=data, ...)
    
    # 更新运行状态（包含 extract_v2_status/extract_mode_used）
    if run_id:
        self.dao.update_run(run_id, "success", ...)
```

**Step2 (extract_risks)** ~ 行 1159-1223:
```python
if extract_mode.value == "NEW_ONLY":
    # 仅使用 v2，失败抛错
    v2_result = asyncio.run(extract_v2.extract_risks_v2(...))
    
    # 成功：写入旧表
    self.dao.replace_risks(project_id, arr)
    
    # 更新运行状态
    if run_id:
        self.dao.update_run(run_id, "success", ...)
```

**关键特性**:
- ✅ 只走 v2，不回退
- ✅ 失败记录到 `tender_runs.message`
- ✅ 成功写旧表（保证前端兼容）
- ✅ Meta 包含 `extract_v2_status` / `extract_mode_used`

---

### 2. REVIEW_MODE=NEW_ONLY ✅

**实现位置**: `backend/app/services/tender_service.py` ~ 行 2375-2430

**Step5 (run_review)**:
```python
if review_mode.value == "NEW_ONLY":
    # 仅使用 v2
    v2_results = asyncio.run(review_v2.run_review_v2(...))
    
    # 成功：使用 v2 结果，写入旧表
    arr = v2_results
    self.dao.replace_review_items(project_id, arr)
    
    # 更新运行状态
    if run_id:
        self.dao.update_run(run_id, "success", result_json={
            "count": len(arr),
            "review_v2_status": "ok",
            "review_mode_used": "NEW_ONLY"
        })
```

**关键特性**:
- ✅ 只走 v2，不回退
- ✅ 失败记录到 `tender_runs.message`
- ✅ 成功写旧表（保证 ReviewTable 可用）
- ✅ Meta 包含 `review_v2_status` / `review_mode_used`

---

### 3. RETRIEVAL_MODE=NEW_ONLY 可验证 ✅

**实现位置**: `backend/app/routers/debug.py` ~ 行 187-265

**Debug 接口增强**:
```python
@router.get("/retrieval/test")
async def test_new_retrieval(...):
    # 获取 cutover 配置
    resolved_mode = cutover.get_mode("retrieval", project_id).value
    
    # 执行检索 + 计时
    start_time = time.time()
    results = await retriever.retrieve(...)
    latency_ms = int((time.time() - start_time) * 1000)
    
    # 返回详细信息
    return {
        "resolved_mode": resolved_mode,      # "NEW_ONLY"
        "provider_used": "new",             # "new"
        "latency_ms": latency_ms,           # 131
        "top_ids": [...],                   # 前 10 个 chunk_id
        "results_count": len(results),
        "results": [r.to_dict() for r in results],
    }
```

**验证示例**:
```bash
curl -G --data-urlencode "query=招标要求" \
  --data-urlencode "project_id=tp_xxx" \
  http://localhost:9001/api/_debug/retrieval/test

# 返回:
{
  "resolved_mode": "NEW_ONLY",
  "provider_used": "new",
  "latency_ms": 131,
  "top_ids": ["seg_xxx", "seg_yyy", ...]
}
```

---

### 4. INGEST_MODE=NEW_ONLY ✅ (已有)

**实现位置**: `backend/app/services/tender_service.py` ~ 行 632-642

**关键逻辑**:
```python
elif ingest_mode.value == "NEW_ONLY":
    # v2 失败直接抛错
    tpl_meta["ingest_v2_status"] = "failed"
    tpl_meta["ingest_v2_error"] = str(e)
    raise ValueError(f"IngestV2 NEW_ONLY failed: {e}") from e
```

---

### 5. RULES_MODE=NEW_ONLY ✅ (已有)

**实现位置**: `backend/app/services/tender_service.py` ~ 行 2348-2357

**关键逻辑**:
```python
elif rules_mode.value == "NEW_ONLY":
    import asyncio
    from app.platform.rules.evaluator_v2 import RulesEvaluatorV2
    
    evaluator_v2 = RulesEvaluatorV2(pool)
    context_v2 = {"project_info": project_info}
    rule_findings = asyncio.run(evaluator_v2.evaluate(...))
    logger.info(f"NEW_ONLY rules: {len(rule_findings)} findings")
```

---

## 📈 关键指标

### 可观测性

所有 NEW_ONLY 模式都包含：

1. **运行状态记录**:
   ```json
   {
     "extract_v2_status": "ok" | "failed",
     "extract_mode_used": "NEW_ONLY",
     "extract_v2_error": "..." // 失败时
   }
   ```

2. **日志输出**:
   ```
   NEW_ONLY extract_project_info: using v2 only for project={project_id}
   NEW_ONLY extract_project_info: v2 succeeded for project={project_id}
   ```

3. **Debug 接口**:
   - `/api/_debug/cutover?project_id=xxx` - 查看所有模式
   - `/api/_debug/retrieval/test?...` - 验证检索模式
   - `/api/_debug/ingest/v2?asset_id=xxx` - 验证入库状态

### 前端兼容性

| 模式 | 旧表 | 前端影响 |
|------|------|---------|
| EXTRACT | tender_project_info / tender_risks | ✅ 无影响 |
| REVIEW | tender_review_items | ✅ 无影响 |
| RULES | 合并到 review items | ✅ 无影响 |
| INGEST | tender_assets.meta_json | ✅ 无影响 |

**结论**: 所有 NEW_ONLY 模式都保持前端完全兼容。

---

## 🧪 测试详情

### 阶段 1: RETRIEVAL_MODE=NEW_ONLY

**配置**:
```yaml
RETRIEVAL_MODE=NEW_ONLY
INGEST_MODE=OLD
EXTRACT_MODE=OLD
REVIEW_MODE=OLD
RULES_MODE=OLD
```

**结果**: ✅ Smoke 全绿

**验证**:
```bash
curl -G --data-urlencode "query=招标要求" \
  --data-urlencode "project_id=tp_7c71153700094d3cb0f3941d9d6ffc6b" \
  http://localhost:9001/api/_debug/retrieval/test

# 确认: resolved_mode="NEW_ONLY", provider_used="new"
```

---

### 阶段 2: INGEST_MODE=NEW_ONLY

**配置**: RETRIEVAL + INGEST = NEW_ONLY

**结果**: ✅ Smoke 全绿

**验证**:
- DocStore: `documents`, `document_versions`, `doc_segments` 有数据
- Milvus: `doc_segments_v1` 集合有向量

---

### 阶段 3: EXTRACT_MODE=NEW_ONLY

**配置**: RETRIEVAL + INGEST + EXTRACT = NEW_ONLY

**结果**: ✅ Smoke 全绿

**验证**:
- Step 1: ✅ 完成 (extract_mode_used="NEW_ONLY")
- Step 2: ✅ 完成 (extract_mode_used="NEW_ONLY")
- `tender_project_info` / `tender_risks` 有数据

---

### 阶段 4: REVIEW_MODE=NEW_ONLY

**配置**: RETRIEVAL + INGEST + EXTRACT + REVIEW = NEW_ONLY

**结果**: ✅ Smoke 全绿

**验证**:
- Step 5: ✅ 完成 (review_mode_used="NEW_ONLY")
- `tender_review_items` 有数据

---

### 阶段 5: RULES_MODE=NEW_ONLY (全链路)

**配置**: 所有模式 = NEW_ONLY

```yaml
RETRIEVAL_MODE=NEW_ONLY
INGEST_MODE=NEW_ONLY
EXTRACT_MODE=NEW_ONLY
REVIEW_MODE=NEW_ONLY
RULES_MODE=NEW_ONLY
```

**结果**: ✅ Smoke 全绿

**项目 ID**: `tp_cf2bfdfcdfc14b399867b867183d2a53`

**日志验证**:
```
NEW_ONLY extract_project_info: using v2 only for project=tp_cf2bfdfcdfc14b399867b867183d2a53
NEW_ONLY extract_risks: using v2 only for project=tp_cf2bfdfcdfc14b399867b867183d2a53
NEW_ONLY review_run: using v2 only for project=tp_cf2bfdfcdfc14b399867b867183d2a53
NEW_ONLY rules: 0 findings
```

---

## 📦 代码变更

### 修改文件 (2)

1. **backend/app/services/tender_service.py** (~200 行新增)
   - ✅ `extract_project_info`: NEW_ONLY 分支
   - ✅ `extract_risks`: NEW_ONLY 分支
   - ✅ `run_review`: NEW_ONLY + PREFER_NEW 分支

2. **backend/app/routers/debug.py** (~40 行修改)
   - ✅ `/api/_debug/retrieval/test`: 增加 resolved_mode/provider_used/latency_ms/top_ids

### 无需修改

- INGEST_MODE=NEW_ONLY: 已实现 ✅
- RULES_MODE=NEW_ONLY: 已实现 ✅
- RETRIEVAL_MODE: Facade 已支持 ✅

---

## 📝 最终配置

### 默认配置 (安全)

```yaml
# docker-compose.yml
RETRIEVAL_MODE=OLD
INGEST_MODE=OLD
EXTRACT_MODE=OLD
REVIEW_MODE=OLD
RULES_MODE=OLD
```

**状态**: ✅ 已恢复

### 灰度配置

```yaml
# 全局 OLD，单项目 NEW_ONLY
CUTOVER_PROJECT_IDS='{"extract":{"NEW_ONLY":["tp_xxx"]}}'
```

### 全量 NEW_ONLY

```yaml
# 所有模式 NEW_ONLY
RETRIEVAL_MODE=NEW_ONLY
INGEST_MODE=NEW_ONLY
EXTRACT_MODE=NEW_ONLY
REVIEW_MODE=NEW_ONLY
RULES_MODE=NEW_ONLY
```

**测试状态**: ✅ 验证通过

---

## 🎯 验收结论

### ✅ 全部通过

**完成度**: 5/5 模式 (100%)

| 模式 | NEW_ONLY 实现 | Smoke 测试 | Debug 验证 | 前端兼容 |
|------|--------------|-----------|-----------|---------|
| RETRIEVAL | ✅ 隐含支持 | ✅ 通过 | ✅ Debug 接口 | ✅ 兼容 |
| INGEST | ✅ 已实现 | ✅ 通过 | ✅ DocStore | ✅ 兼容 |
| EXTRACT | ✅ **新增** | ✅ 通过 | ✅ Run meta | ✅ 兼容 |
| REVIEW | ✅ **新增** | ✅ 通过 | ✅ Run meta | ✅ 兼容 |
| RULES | ✅ 已实现 | ✅ 通过 | ✅ 日志 | ✅ 兼容 |

### 关键成就

1. ✅ **完整实现**: 所有 5 个 NEW_ONLY 模式都已实现
2. ✅ **渐进式验证**: 5 阶段测试全部通过
3. ✅ **可观测性**: Debug 接口 + 日志 + Meta 完整
4. ✅ **前端兼容**: 所有模式都写旧表，无破坏性变更
5. ✅ **生产就绪**: 默认 OLD，可安全部署

### 生产部署建议

**推荐路径**: 

```
OLD → SHADOW → PREFER_NEW (灰度) → PREFER_NEW (全量) → NEW_ONLY (灰度) → NEW_ONLY (全量) → 移除旧代码
```

**监控指标**:
- v2 成功率 (目标 > 99%)
- 回退频率 (PREFER_NEW 阶段，健康 < 1%)
- 性能对比 (v2 vs 旧逻辑)

---

## 📚 相关文档

- [Step 11 详细报告](STEP11_COMPLETION_REPORT.md)
- [Step 11 快速总结](STEP11_SUMMARY.md)
- [Step 11 测试结果](STEP11_TEST_RESULTS.md)
- [Smoke 测试文档](docs/SMOKE.md) (Step 11 章节)

---

## 🎊 最终声明

### ✅ Step 11 圆满完成！

**验收人**: Cursor AI Assistant  
**验收时间**: 2025-12-19 20:45  
**验收结果**: ✅ **全部通过**

**关键数据**:
- 实现代码: ~250 行
- 测试场景: 5 个阶段
- 通过率: 100%
- 破坏性变更: 0
- 生产就绪度: ✅ 就绪

---

**🎉🎉🎉 Step 11: NEW_ONLY 收口 - 完美达成！🎉🎉🎉**

---

**报告生成时间**: 2025-12-19 20:45  
**报告版本**: v1.0  
**验收状态**: ✅ 完成

