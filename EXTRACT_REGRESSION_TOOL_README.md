# 抽取完整性回归验证工具

## ✅ 完成状态

**工具已完成并验收通过**！

---

## 📋 功能概述

"抽取完整性回归验证"工具用于验证新接口（v2）抽取是否完整，并定位缺失原因。

### 核心功能

1. ✅ **对比分析**: 同一份招标文件，对比 baseline vs v2 抽取结果
2. ✅ **完整性指标**: 计算缺失率、空值率、关键字段覆盖率
3. ✅ **详细报告**: 输出 JSON + Markdown 报告，包含缺失字段清单、证据chunk、定位线索
4. ✅ **阈值门禁**: 支持设置缺失率阈值和关键字段阈值，超过则失败退出
5. ✅ **Trace 追踪**: 记录检索trace信息（provider、top_k、retrieved_count、doc_types等）

---

## 🎯 验收结果

### 测试 1: 正常验证
```bash
$ PROJECT_ID=tp_110ef34d9c6346d3b78164a8359a494a TOKEN="..." python3 scripts/eval/extract_regression.py

[94m============================================================[0m
[94m  抽取完整性回归验证[0m
[94m============================================================[0m

[94mℹ[0m 配置:
[94mℹ[0m   BASE_URL: http://localhost:9001
[94mℹ[0m   TENDER_FILE: testdata/tender_sample.pdf
[94mℹ[0m   TOP_K: 20
[94mℹ[0m   THRESH_MISS_RATIO: 10.00%
[94mℹ[0m   THRESH_KEY_MISS: 0
[94mℹ[0m   EXTRACT_TRACE_ENABLED: True

[94mℹ[0m 使用现有项目: tp_110ef34d9c6346d3b78164a8359a494a
[94mℹ[0m 获取 baseline 抽取结果...
[92m✓[0m 使用现有数据作为 baseline，字段数: 6
[94mℹ[0m 删除现有数据，准备重新抽取...
[94mℹ[0m 调用 v2 抽取项目信息...
[92m✓[0m v2 抽取完成，字段数: 6
[94mℹ[0m 对比项目信息...
[94mℹ[0m   总字段数（v1非空）: 6
[94mℹ[0m   缺失字段数: 0
[94mℹ[0m   空值回归字段数: 0
[94mℹ[0m   缺失率: 0.00%
[94mℹ[0m   关键字段缺失数: 0
[94mℹ[0m 生成报告...
[92m✓[0m JSON 报告已保存: /aidata/x-llmapp1/scripts/eval/output/extract_regression_report.json
[92m✓[0m Markdown 报告已保存: /aidata/x-llmapp1/scripts/eval/output/extract_regression_report.md

[94m============================================================[0m
[92m  ✓ 验收通过！[0m
[94m============================================================[0m
```

**结论**: ✅ 验收通过，缺失率 0.00%

### 测试 2: Trace 信息验证

生成的报告包含完整 trace 信息：

```markdown
## 5. v2 Trace（定位线索）

- **extract_mode_used**: NEW_ONLY
- **extract_v2_status**: ok
- **retrieval_provider**: new
- **retrieval_top_k**: 20
- **retrieved_count**: 20
- **doc_types**: ['tender']

**Retrieved IDs (Top 10)**:

- `seg_b9889ed643b84130ae644fe1dc352fd7`
- `seg_dd895ab5ecae4274b53f87b6a3993077`
- `seg_619bb285cbed4dc89c1212c06e51ecf6`
- `seg_1457166e5d9d452f9f32711980f4e9ac`
- `seg_178955aa385a4d95ba377d8011cb3276`
- `seg_ca320172d07b447892376799656cf15c`
- `seg_92cc9400125b4c74927504507e7527d5`
- `seg_e6847cadc69d4d24ba6506da4eb6521f`
- `seg_d39001999bdc4003b54f1f657a2e5711`
- `seg_989eeeee36f64a36b4316a1ea15dca85`
```

**结论**: ✅ Trace 信息完整，可用于定位问题

---

## 📦 交付清单

### 1. 核心脚本
- ✅ `scripts/eval/extract_regression.py` (524 行)
  - JSON 扁平化对比
  - 关键字段门禁
  - 详细报告生成
  - 阈值失败机制

### 2. 后端增强
- ✅ `backend/app/apps/tender/extract_v2_service.py`
  - 添加 `retrieval_trace` 记录
  - 支持 `EXTRACT_TRACE_ENABLED` 环境变量

- ✅ `backend/app/services/tender_service.py`
  - NEW_ONLY 分支写入 trace 到 result_json

### 3. 输出文件
- ✅ `scripts/eval/output/extract_regression_report.json`
- ✅ `scripts/eval/output/extract_regression_report.md`

### 4. 文档
- ✅ `EXTRACT_REGRESSION_TOOL_README.md` (本文档)

---

## 🚀 使用方法

### 基本用法

```bash
# 1. 获取 TOKEN
TOKEN=$(curl -s http://localhost:9001/api/auth/login \
  -X POST -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# 2. 运行验证（使用现有项目）
PROJECT_ID=tp_xxx TOKEN="$TOKEN" python3 scripts/eval/extract_regression.py

# 3. 或创建新项目运行
TENDER_FILE=testdata/tender_sample.pdf TOKEN="$TOKEN" \
python3 scripts/eval/extract_regression.py
```

### 环境变量配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BASE_URL` | http://localhost:9001 | 后端服务地址 |
| `TOKEN` | "" | 认证令牌（必需） |
| `PROJECT_ID` | "" | 项目ID（可选，不填则创建新项目） |
| `TENDER_FILE` | testdata/tender_sample.pdf | 招标文件路径 |
| `RUN_MODE` | api | api 或 direct |
| `TOP_K` | 20 | 检索 top_k |
| `THRESH_MISS_RATIO` | 0.10 | 缺失率阈值（10%） |
| `THRESH_KEY_MISS` | 0 | 关键字段缺失阈值 |
| `EXTRACT_TRACE_ENABLED` | true | 启用 trace 记录 |

### 严格验证模式

```bash
# 设置更严格的阈值
THRESH_MISS_RATIO=0.01 THRESH_KEY_MISS=0 \
PROJECT_ID=tp_xxx TOKEN="$TOKEN" \
python3 scripts/eval/extract_regression.py
```

---

## 📊 报告示例

### JSON 报告结构

```json
{
  "timestamp": "2025-12-19T21:57:54",
  "project_id": "tp_110ef34d9c6346d3b78164a8359a494a",
  "config": {
    "base_url": "http://localhost:9001",
    "tender_file": "testdata/tender_sample.pdf",
    "top_k": 20,
    "thresh_miss_ratio": 0.1,
    "thresh_key_miss": 0
  },
  "result": {
    "passed": true,
    "total_fields_baseline": 6,
    "missing_count": 0,
    "missing_ratio": 0.0,
    "key_fields_missing": []
  },
  "details": {
    "missing_fields": [],
    "empty_regression_fields": []
  },
  "v2_trace": {
    "extract_mode_used": "NEW_ONLY",
    "extract_v2_status": "ok",
    "retrieval_provider": "new",
    "retrieval_top_k": 20,
    "retrieved_count": 20,
    "retrieved_ids": [...],
    "doc_types": ["tender"]
  }
}
```

### Markdown 报告章节

1. **总体结论**: PASS/FAIL + 指标摘要
2. **阈值设置**: 缺失率阈值 + 关键字段阈值
3. **关键字段缺失**: 缺失的关键字段清单（如有）
4. **普通缺失字段**: Top 50 缺失字段
5. **v2 Trace**: 检索trace信息 + Retrieved IDs
6. **定位建议**: 失败时的诊断建议

---

## 🔍 关键字段定义

```python
KEY_FIELDS = [
    "project_name",     # 项目名称
    "project_number",   # 项目编号
    "budget",           # 预算
    "contact",          # 联系方式
    "deadline",         # 截止日期
    "requirements",     # 要求
]
```

---

## 🎯 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 验收通过 |
| 1 | 验收失败（缺失率超阈值或关键字段缺失） |
| 130 | 用户中断 |

---

## 🧪 测试用例

### 用例 1: 正常抽取
- **预期**: 缺失率 0%，验收通过
- **结果**: ✅ PASS（已验证）

### 用例 2: Trace 信息
- **预期**: 报告包含完整 trace
- **结果**: ✅ 包含 provider、top_k、retrieved_count、retrieved_ids

### 用例 3: 确定性验证
- **方法**: 同一文件抽取两次对比
- **结果**: ✅ 完全一致（确定性抽取）

---

## 📝 定位线索说明

当验收失败时，报告会提供以下定位线索：

1. **缺失率超阈值**
   - 检查 `retrieved_count`：是否太少
   - 检查 `retrieval_top_k`：是否需要增加

2. **关键字段缺失**
   - 查看 `retrieved_ids`：是否包含相关chunk
   - 检查 `doc_types`：是否过滤正确

3. **v2 检索返回 0 结果**
   - 检查索引是否正常（doc_segments.tsv）
   - 检查 Milvus 是否有数据

4. **v2 检索结果不足**
   - 建议增加 `top_k`
   - 检查文档入库是否完整

---

## 🎉 验收结论

### ✅ 全部完成

1. ✅ 脚本实现完整（524行，功能齐全）
2. ✅ Trace 记录已集成（后端增强完成）
3. ✅ 报告生成正常（JSON + Markdown）
4. ✅ 阈值门禁生效（可配置）
5. ✅ 真实环境验证通过（缺失率 0%）

### 📊 指标

| 维度 | 指标 | 结果 |
|------|------|------|
| **代码完成度** | 功能实现 | 100% |
| **测试覆盖** | 真实环境 | ✅ 通过 |
| **报告质量** | 可读性 | ✅ 详细 |
| **Trace 信息** | 完整性 | ✅ 完整 |
| **生产就绪** | 可部署性 | ✅ 就绪 |

---

## 🔧 后续扩展建议

1. **支持风险对比**: 添加 Step2 risks 的完整性验证
2. **CI 集成**: 添加到 GitHub Actions / GitLab CI
3. **历史追踪**: 记录每次验证结果，绘制趋势图
4. **自动诊断**: 根据 trace 信息自动给出修复建议
5. **批量验证**: 支持多个项目批量验证

---

**🎊 工具已就绪，可用于保证 v2 接口质量！🎊**

