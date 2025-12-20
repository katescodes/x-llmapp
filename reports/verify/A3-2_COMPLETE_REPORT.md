# A3-2 纠偏完成报告

## 时间
2025-12-20

## ✅ 核心成就

### 四大板块全部通过验证（使用真实LLM）
```
✓ base 板块存在
✓ technical_parameters 板块存在
✓ business_terms 板块存在
✓ scoring_criteria 板块存在
```

## 问题诊断与解决

### 问题 1: LLM 模型配置缺失
**现象**: `Error: No LLM model configured`

**根因**:
1. `/app/data/llm_models.json` 文件不存在
2. 环境变量 `LLM_STORE_PATH=/app/data/llm_models.json` 禁用了 bootstrap
3. 默认配置文件 `/app/app/config_defaults/llm_models.json` 无法自动加载

**解决**:
```bash
# 复制默认配置
cp /app/app/config_defaults/llm_models.json /app/data/llm_models.json

# 验证加载
Models: 1
Default: 本地默认模型
```

### 问题 2: LLM 输出截断
**现象**: `out_len=30` (只有 30 个字符)

**根因**: 未设置 `max_tokens`，使用模型默认值（可能很小）

**解决**:
```python
# backend/app/main.py
payload["max_tokens"] = kwargs.get("max_tokens", 4096)

# backend/app/platform/extraction/engine.py
out_text = await call_llm(messages, llm, model_id, temperature=spec.temperature, max_tokens=4096)
```

### 问题 3: Prompt 输出格式
**现象**: LLM 返回的 JSON 不包含四大板块

**根因**: Prompt 没有强制要求输出四大板块结构

**解决**:
```markdown
# backend/app/apps/tender/prompts/project_info_v2.md
"data": {
  "base": { ... },           # 必须存在
  "technical_parameters": [...],  # 必须存在
  "business_terms": [...],        # 必须存在
  "scoring_criteria": { ... }     # 必须存在
}
```

### 问题 4: API 响应格式
**现象**: 验证逻辑期望 `{base: {}}` 但 API 返回 `{data_json: {base: {}}}`

**根因**: `fetch_project_info` 返回完整 API 响应，未提取 `data_json`

**解决**:
```python
# scripts/eval/tender_feature_parity.py
def fetch_project_info(token: str, project_id: str) -> Dict[str, Any]:
    result = resp.json()
    return result.get("data_json", {}) if isinstance(result, dict) else {}
```

## 关键修改文件

1. ✅ `backend/app/apps/tender/prompts/project_info_v2.md`
2. ✅ `backend/app/main.py`
3. ✅ `backend/app/platform/extraction/engine.py`
4. ✅ `backend/app/platform/extraction/llm_adapter.py`
5. ✅ `backend/app/apps/tender/extract_v2_service.py`
6. ✅ `backend/scripts/eval/tender_feature_parity.py`
7. ✅ `/app/data/llm_models.json` (运行时复制)
8. ✅ `docker-compose.yml` (MOCK_LLM=false)

## 验证结果

### 使用真实 LLM 配置
- 模型: 本地默认模型 (local-llm)
- Base URL: http://host.docker.internal:8001
- Max tokens: 4096

### Gate7 测试输出
```
✓ 板块存在: base
✓ 板块存在: technical_parameters
✓ 板块存在: business_terms
✓ 板块存在: scoring_criteria
✗ 规则未命中: MUST_HIT_001
```

## 当前状态

### ✅ 已完成
- [x] LLM 配置加载成功
- [x] 四大板块全部通过验证
- [x] 使用真实 LLM（非 MOCK）
- [x] Prompt 正确定义四大板块
- [x] API 响应正确提取
- [x] 数据成功落库

### ⏳ 待解决
- [ ] review 抽取失败 (status=failed)
- [ ] MUST_HIT_001 规则未命中

## 下一步

继续 A3-2：
1. 调试 review 抽取失败原因
2. 修复 MUST_HIT_001 规则验证
3. 完成 Gate7 完全 PASS

## Git Commits

- `ede3451` - feat(A3-2): 纠偏四大板块成功
- `[current]` - fix(A3-2): 修复 LLM 配置加载

## 日志文件

- `reports/verify/gate7_with_real_llm.log` - 使用真实LLM的测试日志
- `reports/verify/parity/testdata/new_project_info.json` - 完整数据

---

**进度**: ~80% 完成 A3-2  
**状态**: 四大板块已全部通过！使用真实LLM配置成功 ✅

