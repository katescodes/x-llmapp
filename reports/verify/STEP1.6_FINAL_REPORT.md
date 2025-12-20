# Step 1.6 - 稳定 NEW_ONLY Smoke（门槛版）- 最终报告

## 🎯 任务目标

将 NEW_ONLY 全链路测试从"超时失控"改造为"稳定可控的门槛验收"，让 `make verify-docker` 全绿。

## ✅ 完成成果

### 核心突破：**全部 6 个 Gate 通过！**

```
  compileall                     ✓ PASS
  boundary                       ✓ PASS
  smoke_old                      ✓ PASS
  smoke_newonly                  ✓ PASS  ⭐️ (门槛版，164秒完成)
  extract_regression             ✓ PASS
  rules_must_hit                 ✓ PASS  ⭐️ (真实 DB 验证)
```

---

## 📋 实施内容

### 1. ✅ 创建门槛版 Smoke 脚本

**文件**: `scripts/smoke/tender_newonly_gate.py`

**关键路径**（A→H，缺一不可）：
- A. 登录
- B. 创建项目
- C. 上传招标文件
- D. 等待 DocStore 就绪（preflight check，180s 超时）
- E. Step1: 提取项目信息（同步执行）
- F. Step2: 提取风险（同步执行）
- G. Step5: 运行审查（同步执行）
- H. 验证 review items 已入库

**性能表现**:
```
总耗时: 164.1s (< 3分钟)
  - DocStore 等待: 0.0s  (已就绪)
  - Step1 抽取:   86.1s
  - Step2 抽取:   41.3s
  - Step5 审查:   27.6s
  - 其他:          8.7s
```

**关键特性**:
- ✅ 真实端到端：登录→上传→入库→抽取→审查→验证
- ✅ 同步执行：无需轮询，直接返回结果
- ✅ Fail-fast：任何步骤失败立即退出
- ✅ 详细计时：每步耗时可追踪

---

### 2. ✅ 给 Step5 审查添加同步执行能力

**文件**: `backend/app/routers/tender.py`

**修改**: `POST /api/apps/tender/projects/{project_id}/review/run`
- 新增 `sync: int = 0` 参数
- 支持 `X-Run-Sync: "1"` header
- 同步模式：直接执行并返回 `{run_id, status, progress, message}`
- 异常处理：写入 `tender_runs.message` 并返回明确错误

**对齐**: 与 Step1/Step2 的同步执行模式保持一致

---

### 3. ✅ 修改 verify 脚本使用门槛 smoke

**文件**: `scripts/ci/verify_cutover_and_extraction.py`

**Gate 4 改造**:
- **旧**: 跑完整 `tender_e2e.py`（超时 300s，经常不够）
- **新**: 跑门槛版 `tender_newonly_gate.py`（超时 900s，足够稳定）
- **成功判据**: 日志包含 `✓ ALL PASS` 和详细耗时统计

**Gate 4 日志**:
```
/aidata/x-llmapp1/reports/verify/smoke_newonly_gate.log (2009 bytes)
```

---

### 4. ✅ Gate6 改为直接查询数据库验证

**文件**: `scripts/ci/verify_cutover_and_extraction.py`

**验证方式**:
1. 从 `smoke_newonly_gate.log` 提取 `project_id`
2. 用 `docker-compose exec postgres psql` 直接查询：
   ```sql
   SELECT COUNT(*) FROM tender_review_items WHERE project_id='xxx';
   ```
3. 判断：`count >= 1` 则 PASS

**数据源**: PostgreSQL via psql（不可作假）

**Gate 6 日志**:
```
project_id: tp_282a159ea7ec47f6a9f1fe3bb8eec6ec
count: 3
✓ Review items found (count=3)
data_source: PostgreSQL via psql
结论: PASS
```

---

### 5. ✅ 锁定 allowlist 不允许膨胀

**文件**: `scripts/ci/check_platform_work_boundary.py`

**硬限制**:
```python
MAX_ALLOWLIST_HITS = 11
```

**当前白名单**（11 项，精确到文件路径）:
```
backend/app/platform/ingest/v2_service.py          -> 4 项
backend/app/platform/retrieval/new_retriever.py    -> 4 项
backend/app/platform/retrieval/facade.py           -> 2 项
backend/app/platform/rules/evaluator_v2.py         -> 1 项
```

**防膨胀机制**: 若命中数 > 11，则 `boundary` Gate 直接 FAIL

**边界检查输出**:
```
✓ PASS: platform/ 未违反导入边界
⚠ 临时白名单放行 11 项（待后续 Step 消除）
```

---

## 📊 验收结果

### Docker 完整验收

```bash
make verify-docker
```

**输出**:
```
✓ 所有验收门槛通过！

验收汇总:
  compileall                     ✓ PASS
  boundary                       ✓ PASS
  smoke_old                      ✓ PASS
  smoke_newonly                  ✓ PASS
  extract_regression             ✓ PASS
  rules_must_hit                 ✓ PASS
```

---

### 生成的核心文件

| 文件 | 大小 | 说明 |
|-----|------|-----|
| `smoke_newonly_gate.log` | 2009 bytes | Gate4 门槛测试完整日志 |
| `rules_must_hit_newonly.log` | 594 bytes | Gate6 DB 验证日志 |
| `old_project_info.json` | 540 bytes | OLD 模式抽取结果 |
| `newonly_project_info.json` | 7240 bytes | NEW_ONLY 抽取结果 |
| `extract_regression_diff.json` | 440 bytes | 回归对比 diff |
| `boundary.log` | 1872 bytes | 边界检查（11 项白名单锁定）|

---

## 🔍 关键改进

### 从"超时失控"到"可控稳定"

**Step 1.5 遗留问题**:
- ❌ Gate4: `smoke_newonly` 超时 300s
- ❌ Gate6: 依赖 Gate4，连带失败

**Step 1.6 解决方案**:
- ✅ Gate4: 门槛版 smoke，164s 稳定完成（< 900s 超时限制）
- ✅ Gate6: 独立 DB 验证，不依赖长 e2e

### 真实性 vs 效率的平衡

**不作假**:
- Gate4 真实执行：登录→上传→入库→抽取→审查
- Gate6 真实验证：直连数据库查询 `tender_review_items`

**提速**:
- 同步执行：无需 BackgroundTasks + 长轮询
- Preflight 检查：等待 DocStore 就绪后再抽取
- 门槛路径：只跑核心步骤（Step1/2/5），跳过冗余步骤（Step3/4/导出）

---

## 🎯 Step 1.6 验收判据 ✅

1. ✅ Gate1~Gate6 全部 PASS
2. ✅ `smoke_newonly_gate.log` 包含 `✓ ALL PASS` 和耗时统计
3. ✅ `rules_must_hit_newonly.log` 包含 DB 查询证据（`count >= 1`）
4. ✅ 必须文件存在且 size > 0：
   - old_project_info.json
   - newonly_project_info.json
   - extract_regression_diff.json
5. ✅ 边界检查 allowlist 锁定在 11 项，不允许膨胀

---

## 🚀 后续路线图

### Step 2 (Next): Platformize Document Parser
- 迁移 `parser.py` → `platform/ingest/parser.py`（已完成）
- **预期**: allowlist 可减少 0 项（parser 已无 services 依赖）

### Step 3 (Future): Platformize Vectorstore & Embedding
- 迁移 `milvus_docseg_store`, `http_embedding_client`
- **预期**: allowlist 可减少至 ≤ 6 项

### Step 4 (Future): Platformize RRF & Segmenter
- 迁移 `rrf`, `chunker`
- **预期**: allowlist 可减少至 ≤ 2 项

### Step 5 (Final): 完全清零
- 消除最后的 `db.postgres`, `embedding_provider_store` 依赖
- **预期**: allowlist = 0 项，平台完全独立

---

## 📝 总结

Step 1.6 成功将 NEW_ONLY 验收从"不稳定超时"改造为"稳定可控门槛"，实现了：

1. **稳定性**: Gate4 从频繁超时 → 164s 稳定通过
2. **真实性**: 端到端真实执行 + DB 真实验证
3. **可追溯性**: 每步耗时/状态/project_id 全部可查
4. **防退化**: allowlist 硬锁定 11 项，不允许继续膨胀

**Step 1.6 达成！ 🎉**

---

## 🔗 相关文件

- 门槛 smoke: `scripts/smoke/tender_newonly_gate.py`
- 验收脚本: `scripts/ci/verify_cutover_and_extraction.py`
- 边界检查: `scripts/ci/check_platform_work_boundary.py`
- 路由修改: `backend/app/routers/tender.py` (sync 支持)
- 报告目录: `reports/verify/`

---

**Git HEAD**: `b23adbf71e53fe43b09090336154cba5eb8dfd7b`  
**验收时间**: 2025-12-20  
**验收环境**: Docker Compose (localgpt-backend:local)

