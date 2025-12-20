# Step 8 快速验证指南

## 一键验证命令

```bash
cd /aidata/x-llmapp1

# 1. 确保服务运行
docker-compose ps

# 2. 测试 LLM Ping (应返回 ok:true)
curl -sS http://localhost:9001/api/_debug/llm/ping | python3 -m json.tool

# 3. 查看最近的 LLM 调用日志
docker-compose logs --tail=100 backend | grep -E "ExtractionEngine|SimpleLLMOrchestrator|BEFORE_LLM|AFTER_LLM"
```

## 预期结果

### LLM Ping 输出
```json
{
    "ok": true,
    "mode": "mock",
    "message": "MOCK_LLM enabled, no real LLM call made"
}
```

### Backend 日志示例
```
localgpt-backend  | [DEBUG ExtractionEngine] START project_id=tp_xxx llm_type=SimpleLLMOrchestrator
localgpt-backend  | [DEBUG] About to call LLM: llm=<SimpleLLMOrchestrator>
localgpt-backend  | [DEBUG] LLM returned: out_len=773
```

## 验收判据

- ✅ LLM Ping 返回 200 且 ok:true
- ✅ 日志中能看到 ExtractionEngine START
- ✅ 日志中能看到 LLM 调用和返回

## 切换到 REAL 模式

如需测试真实 LLM（需要配置 llm_models 表）：

```bash
# 1. 修改 docker-compose.yml
# 将 MOCK_LLM=true 改为 MOCK_LLM=false

# 2. 重启服务
docker-compose up -d backend

# 3. 再次测试 ping
curl -sS http://localhost:9001/api/_debug/llm/ping | python3 -m json.tool
```

REAL 模式预期输出：
```json
{
    "ok": true,
    "mode": "real",
    "model": "gpt-oss-120b",
    "latency_ms": 987,
    "response_snippet": "..."
}
```

## 故障排查

### 问题：LLM Ping 返回 ok:false

**原因**: REAL 模式下 llm_models 表未配置

**解决方案**:
1. 切换到 MOCK 模式（MOCK_LLM=true）
2. 或配置 llm_models 表

### 问题：抽取没有产出数据

**检查步骤**:
```bash
# 1. 查看完整日志
docker-compose logs --tail=500 backend

# 2. 查找错误
docker-compose logs backend | grep -i "error\|exception\|failed"

# 3. 查找 run_id
docker-compose logs backend | grep "run_id=tr_"
```

## 详细报告

完整验证报告见：`reports/verify/STEP8_LLM_VERIFICATION_REPORT.md`
