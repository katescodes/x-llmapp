# GOAL 1-3 改造 - 使用指南

## 核心改动速查

### 1. 同步代码调用 async 函数

**之前**:
```python
import asyncio
result = asyncio.run(async_function(...))  # ❌ 在 async 环境中会报错
```

**现在**:
```python
from app.platform.utils.async_runner import run_async
result = run_async(async_function(...))  # ✅ 任何环境都安全
```

### 2. 更新 run 状态时绑定 job

**之前**:
```python
dao.update_run(run_id, "running", progress=0.5, message="处理中")
```

**现在**:
```python
dao.update_run(
    run_id,
    "running",
    progress=0.5,
    message="处理中",
    platform_job_id=job_id  # ✅ 绑定 platform job
)
```

### 3. Schema 校验 - 不再静默失败

**之前**:
```python
try:
    obj = extract_json(llm_output)
except:
    obj = {}  # ❌ 静默返回空对象，任务"假成功"
```

**现在**:
```python
from app.platform.extraction.exceptions import ExtractionParseError

try:
    obj = extract_json(llm_output)
except Exception as e:
    raise ExtractionParseError(
        "JSON parse failed",
        raw_output=llm_output[:2000]
    )  # ✅ 明确失败，记录原始输出
```

---

## 快速验证

### 测试 async_runner

```bash
# 在 Docker 容器中运行
cd /aidata/x-llmapp1
docker-compose exec backend bash -lc "cd /repo/backend && pytest -xvs tests/test_async_runner.py"
```

### 验证数据库字段

```bash
docker-compose exec postgres psql -U localgpt -d localgpt \
    -c "SELECT column_name FROM information_schema.columns WHERE table_name='tender_runs' AND column_name='platform_job_id';"
```

### 端到端测试

```bash
cd /aidata/x-llmapp1
./verify_goal_1-3.sh
```

---

## 常见问题

### Q1: 为什么要用 run_async 而不是 asyncio.run？

**A**: `asyncio.run()` 在已有 event loop 的环境中会报错：
```
RuntimeError: asyncio.run() cannot be called from a running event loop
```

`run_async()` 会自动检测环境：
- 无 loop: 直接用 `asyncio.run()`
- 有 loop: 在独立线程中执行，避免冲突

### Q2: platform_job_id 什么时候会被使用？

**A**: 当 `PLATFORM_JOBS_ENABLED=true` 时：
1. TenderService 创建 platform job 并绑定到 run
2. GET /runs/{run_id} 优先返回 job 状态
3. job 完成时自动同步回 run 表

如果 jobs 未启用，`platform_job_id` 为空，维持旧行为。

### Q3: Schema 校验失败后如何排查？

**A**: 检查 `result_json.error` 字段：

```json
{
  "error": {
    "error_type": "ExtractionSchemaError",
    "message": "Schema validation failed: ...",
    "validation_errors": [
      {
        "loc": ["data", "technical_parameters"],
        "msg": "value is not a valid list",
        "type": "type_error.list"
      }
    ],
    "raw_output_snippet": "LLM 原始输出前 500 字符..."
  }
}
```

**排查步骤**:
1. 查看 `error_type` 判断是解析错误还是校验错误
2. 查看 `validation_errors` 了解具体哪个字段有问题
3. 查看 `raw_output_snippet` 检查 LLM 输出格式

### Q4: 如何临时禁用 Schema 校验？

**A**: 不建议禁用。如果必须，可以修改 `engine.py`:

```python
# 临时跳过校验（仅用于调试）
if os.getenv("SKIP_SCHEMA_VALIDATION") == "true":
    logger.warning("Schema validation skipped")
else:
    validated_model = ProjectInfoV2.model_validate(obj)
    obj = validated_model.to_dict_exclude_none()
```

但生产环境应始终启用校验，避免"假成功"。

---

## 迁移检查清单

如果你在其他服务中使用了类似模式，请检查：

- [ ] 同步代码中使用 `asyncio.run()` → 改为 `run_async()`
- [ ] 创建 platform job 但未绑定到 run → 添加 `platform_job_id` 参数
- [ ] LLM 输出解析失败返回空对象 → 改为抛出异常
- [ ] 缺少 Schema 校验 → 添加 Pydantic 模型校验
- [ ] 错误信息不完整 → 记录 error_type/validation_errors/raw_output

---

## 性能影响

### run_async() 性能
- **无 loop**: 与 `asyncio.run()` 相同（无额外开销）
- **有 loop**: 在独立线程执行，有线程切换开销（约 1-5ms）

**建议**: 对于高频调用，考虑重构为纯 async 或纯 sync，避免混用。

### Schema 校验性能
- **开销**: 约 1-10ms（取决于数据复杂度）
- **优化**: Pydantic 已高度优化，通常可忽略

**建议**: 如果数据量极大（>10MB），考虑增量校验或异步校验。

### 数据库查询（GOAL-2）
- **额外查询**: 如果启用 jobs，`get_run()` 会额外查询 platform job（1 次）
- **缓存**: 可添加 Redis 缓存 job 状态（未实现）

---

## 进一步阅读

- `backend/app/platform/utils/async_runner.py` - async_runner 实现
- `backend/app/works/tender/schemas/project_info_v2.py` - Schema 定义
- `backend/app/platform/extraction/exceptions.py` - 异常类型
- `GOAL_1-3_COMPLETION_REPORT.md` - 完整改造报告




