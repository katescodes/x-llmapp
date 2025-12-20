# v2 抽取改造说明

## 📋 改造内容

### 1. 四块信息全覆盖

**基础信息 (12 字段)**:
- projectName, ownerName, agencyName
- bidDeadline, bidOpeningTime
- budget, maxPrice, bidBond
- schedule, quality, location, contact

**技术参数 (数组)**:
- category, item, requirement, parameters[]
- 每项带 evidence_chunk_ids

**商务条款 (数组)**:
- term (条款名称), requirement (内容)
- 每项带 evidence_chunk_ids

**评分标准 (对象)**:
- evaluationMethod (评标办法)
- items[] (评分项: category, item, score, rule)
- 每项带 evidence_chunk_ids

---

### 2. 多查询召回策略

```python
# 4个专门查询，覆盖不同维度
queries = [
    ("base", "招标公告 项目名称 项目编号 预算金额 采购人..."),
    ("technical", "技术要求 技术规范 技术参数 设备参数..."),
    ("business", "商务条款 合同条款 付款方式 交付期..."),
    ("scoring", "评分标准 评标办法 评审办法 评分细则..."),
]

# 每个查询返回 top_k_per_query (默认30)
# 合并去重后截断到 top_k_total (默认120)
```

---

### 3. 关键特性

✅ **字段级 evidence**: 每个条目都有 chunk_ids  
✅ **可复现**: temperature=0.0  
✅ **可配置**: top_k 环境变量可调  
✅ **可观测**: 完整 retrieval_trace  
✅ **向后兼容**: 输出格式与旧版一致  
✅ **写旧表**: 保证前端正常显示

---

## ⚙️ 配置参数

### 环境变量

```bash
# docker-compose.yml 或 .env
V2_RETRIEVAL_TOPK_PER_QUERY=30    # 每个查询返回的最大 chunks 数
V2_RETRIEVAL_TOPK_TOTAL=120       # 合并后的总 chunks 数上限
EXTRACT_TRACE_ENABLED=true        # 启用 trace 记录
```

### 推荐配置

| 文档复杂度 | PER_QUERY | TOTAL | 说明 |
|-----------|-----------|-------|------|
| 简单 | 20 | 80 | 小型招标文件 |
| 中等 | 30 | 120 | 常规项目（默认） |
| 复杂 | 50 | 200 | 大型复杂项目 |

---

## 🚀 使用方法

### 1. API 调用

```bash
# 使用 X-Force-Mode 强制 NEW_ONLY
curl -X POST "http://localhost:9001/api/apps/tender/projects/{id}/extract/project-info" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Force-Mode: NEW_ONLY" \
  -H "Content-Type: application/json"
```

### 2. 环境变量控制

```bash
# docker-compose.yml
EXTRACT_MODE=NEW_ONLY
```

### 3. Python 调用

```python
import requests

headers = {
    "Authorization": f"Bearer {token}",
    "X-Force-Mode": "NEW_ONLY",  # 强制使用 v2
    "Content-Type": "application/json"
}

resp = requests.post(
    f"{base_url}/api/apps/tender/projects/{project_id}/extract/project-info",
    headers=headers,
    json={}
)
```

---

## 📊 返回格式

### data 结构

```json
{
  "data": {
    // 基础信息 (12个字段)
    "projectName": "...",
    "ownerName": "...",
    "budget": "...",
    ...
    
    // 技术参数 (数组)
    "technicalParameters": [
      {
        "category": "PLC",
        "item": "中控技术",
        "requirement": "...",
        "parameters": [],
        "evidence_chunk_ids": ["seg_11"]
      }
    ],
    
    // 商务条款 (数组)
    "businessTerms": [
      {
        "term": "投标保证金",
        "requirement": "...",
        "evidence_chunk_ids": ["seg_4"]
      }
    ],
    
    // 评分标准 (对象)
    "scoringCriteria": {
      "evaluationMethod": "综合评估法",
      "items": [
        {
          "category": "商务",
          "item": "商务部分",
          "score": "18",
          "rule": "...",
          "evidence_chunk_ids": ["seg_41"]
        }
      ]
    }
  },
  
  // 整体 evidence (所有 chunk_ids 的并集)
  "evidence_chunk_ids": ["seg_1", "seg_4", "seg_6", "seg_11", ...],
  
  // Retrieval trace (可观测性)
  "retrieval_trace": {
    "retrieval_strategy": "multi_query",
    "queries": {
      "base": {"retrieved_count": 30, "top_ids": [...]},
      "technical": {"retrieved_count": 30, "top_ids": [...]},
      "business": {"retrieved_count": 30, "top_ids": [...]},
      "scoring": {"retrieved_count": 30, "top_ids": [...]}
    },
    "retrieved_count_total": 58,
    "top_k_per_query": 30,
    "top_k_total": 120
  }
}
```

---

## 🔍 Trace 信息使用

### 查看 retrieval_trace

```bash
# 获取 run 结果
curl "http://localhost:9001/api/apps/tender/runs/{run_id}" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.result_json.retrieval_trace'
```

### Trace 包含信息

- **retrieval_strategy**: 检索策略 (multi_query)
- **queries**: 每个查询的详情
  - query: 查询文本
  - retrieved_count: 召回数
  - top_ids: Top 5 chunk IDs
- **retrieved_count_total**: 合并后总数
- **top_k_per_query**: 每查询 top_k
- **top_k_total**: 总 top_k 限制

---

## 🐛 故障排查

### 问题 1: 某些字段为空

**原因**: 检索未命中相关内容  
**解决**: 
1. 增加 `V2_RETRIEVAL_TOPK_PER_QUERY`
2. 检查 trace 中对应查询的 retrieved_count
3. 查看 top_ids 对应的 chunks 内容

### 问题 2: 技术参数/商务条款/评分标准为空

**原因**: 对应维度的查询未命中  
**解决**:
1. 检查 trace.queries.technical/business/scoring 的 retrieved_count
2. 如果为0，说明文档中无相关内容或查询不匹配
3. 可以调整查询关键词（修改 extract_v2_service.py）

### 问题 3: 抽取超时

**原因**: LLM 服务慢或 chunks 过多  
**解决**:
1. 减少 `V2_RETRIEVAL_TOPK_TOTAL`
2. 检查 LLM 服务状态
3. 查看后端日志

---

## 📈 性能优化

### 1. 调整 top_k

```bash
# 减少召回数量，加快速度
V2_RETRIEVAL_TOPK_PER_QUERY=20
V2_RETRIEVAL_TOPK_TOTAL=80

# 增加召回数量，提高完整度
V2_RETRIEVAL_TOPK_PER_QUERY=50
V2_RETRIEVAL_TOPK_TOTAL=200
```

### 2. 优化查询文本

修改 `backend/app/apps/tender/extract_v2_service.py`:

```python
queries = [
    ("base", "你的优化后的查询..."),
    ("technical", "你的优化后的查询..."),
    ...
]
```

### 3. 温度控制

已硬编码为 `temperature=0.0`，保证可复现性。

---

## 📝 文件清单

| 文件 | 说明 |
|------|------|
| `backend/app/apps/tender/extract_v2_service.py` | v2 抽取服务（已改造） |
| `backend/app/services/tender_service.py` | 服务层（NEW_ONLY 分支） |
| `backend/env.example` | 环境变量示例 |
| `docker-compose.yml` | Docker 配置 |
| `V2_EXTRACT_VALIDATION_REPORT.md` | 验证报告 |
| `V2_EXTRACT_README.md` | 本文档 |

---

## 🎯 下一步

1. **验证更多项目**: 在不同类型的招标文件上测试
2. **对比新旧结果**: 使用 X-Force-Mode 对比 OLD vs NEW_ONLY
3. **优化查询**: 根据实际效果调整查询关键词
4. **调整参数**: 根据文档复杂度调整 top_k

---

**v2 抽取已完成改造并验证通过！** ✅

