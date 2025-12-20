# Part A & Part B 当前进度（最新）

**更新时间**: 2025-12-20 15:42 UTC+8
**Git commit**: ac0c41b (feat(A3-1): Gate7运行成功，明确发现四大板块缺失)

---

## ✅ 已完成

### A0: 契约定义 ✅
- `backend/app/apps/tender/contracts/tender_contract_v1.yaml` (7.9KB)

### A1: 对比脚本 ✅
- `scripts/eval/tender_feature_parity.py` (完整功能)

### A2: 接入 CI ✅  
- `scripts/ci/verify_cutover_and_extraction.py` (Gate 7 已添加)

### A3-1: Gate7 运行成功并明确问题 ✅
**运行结果**:
```
✓ 登录成功
✓ 项目创建成功
✓ DocStore 就绪 (segments=41)
✓ project-info 抽取完成 (283ms)
✓ risks 抽取完成 (86ms)
✗ review 抽取失败 (47ms)
✗ 契约验证失败：四大板块全部缺失 + MUST_HIT_001 未命中
```

**产出文件** (所有必需文件已生成):
- ✅ `reports/verify/parity/testdata/diff_summary.json` (635 bytes)
- ✅ `reports/verify/parity/testdata/report.md` (634 bytes)
- ✅ `reports/verify/parity/testdata/new_project_info.json` (177 bytes)
- ✅ `reports/verify/gate7_a3_baseline.log` (完整日志)

**发现的问题**:
1. ❌ `project_info.data_json = {}` (四大板块全部缺失)
2. ❌ `review status=failed` (MUST_HIT_001 未命中)

---

## 🚧 进行中：A3-2 纠偏四大板块

### 需要修改的文件

#### 1. `backend/app/apps/tender/extraction_specs/project_info_v2.py`
**当前问题**: queries 未区分四大板块
**修改方案**: 拆成 4 组 queries
```python
QUERIES = {
    "base": [
        {"name": "project_name", "query": "项目名称？", "top_k": 3},
        {"name": "budget", "query": "预算金额？", "top_k": 3},
        # ... 其他 base 字段
    ],
    "technical_parameters": [
        {"name": "tech_specs", "query": "技术参数和规格要求？", "top_k": 10},
    ],
    "business_terms": [
        {"name": "payment", "query": "付款条款？", "top_k": 5},
    ],
    "scoring_criteria": [
        {"name": "scoring", "query": "评分标准？", "top_k": 10},
    ]
}
```

#### 2. `backend/app/apps/tender/prompts/project_info_v2.md`
**当前问题**: 输出格式未明确四大板块
**修改方案**: 强制输出四个 key
```markdown
# 输出 JSON 格式：
{
  "base": { ... },
  "technical_parameters": [ ... ],
  "business_terms": [ ... ],
  "scoring_criteria": [ ... ]
}

## 注意：四个 key 必须存在，未找到输出空数组/空对象
```

#### 3. `backend/app/apps/tender/extract_v2_service.py`
**当前问题**: 落库前未确保四大板块存在
**修改方案**: 在写入 `tender_project_info` 前补全
```python
def extract_project_info(...):
    # ... 调用引擎 ...
    result = engine.extract(...)
    
    # 确保四大板块都存在
    data_json = result.get('data', {})
    for key in ['base', 'technical_parameters', 'business_terms', 'scoring_criteria']:
        if key not in data_json:
            data_json[key] = {} if key == 'base' else []
    
    # 写入数据库
    dao.update_project_info(project_id, data_json)
```

#### 4. Review 失败（待定位）
- 需要检查 `review_v2_service.py` 或相关逻辑
- 可能与 MUST_HIT_001 规则配置有关

---

## 📋 待完成

### A3-2: 纠偏四大板块 🔜
1. 修改 `extraction_specs/project_info_v2.py`
2. 修改 `prompts/project_info_v2.md`
3. 修改 `extract_v2_service.py`
4. 重新运行 Gate7 验证
5. 直到 `diff_summary.json` 显示四大板块都存在

### A3-3: 批量语料测试（可选）
- 挂载 Windows 目录
- 运行 `--corpus_dir` 批量测试

### B1: TenderService 删除 OLD 分支
- 清理 4 个函数的 OLD/SHADOW/PREFER_NEW 分支
- 验证：`rg -n "CutoverMode.OLD"` 返回 0

### B2: 删除招投标旧模块
- 扫描并删除 `services/tender/` 下旧模块
- 删除 `extract_diff.py`, `review_diff.py`

### B3: 加硬门槛防旧链路复活
- 修改 `check_platform_work_boundary.py`
- 禁止 kb_documents/kb_chunks/services.tender.

### 最终验收
- `make verify-docker` 全绿 (Gate 1-7 全 PASS)
- `rg -n "kb_documents|kb_chunks"` 返回 0

---

## 📊 进度统计

- **A0-A2**: ✅ 100% 完成
- **A3-1**: ✅ 100% 完成
- **A3-2**: 🔜 0% (即将开始)
- **A3-3**: 📋 未开始
- **B1-B3**: 📋 未开始

**总体完成度**: ~40%

---

## 🔄 下一步操作（立即执行）

1. **检查现有文件**:
   ```bash
   # 查看 project_info_v2.py 当前实现
   docker-compose exec -T backend cat /app/app/apps/tender/extraction_specs/project_info_v2.py
   
   # 查看 prompt 模板
   docker-compose exec -T backend cat /app/app/apps/tender/prompts/project_info_v2.md
   
   # 查看 service 实现
   docker-compose exec -T backend grep -A 30 "def extract_project_info" /app/app/apps/tender/extract_v2_service.py
   ```

2. **修改文件**:
   - 按上述方案逐个修改

3. **验证修改**:
   ```bash
   docker-compose build backend
   docker-compose up -d
   docker-compose exec -T backend python scripts/eval/tender_feature_parity.py
   ```

4. **检查结果**:
   ```bash
   cat reports/verify/parity/testdata/diff_summary.json
   # 应该看到 "missing": [] (空数组)
   ```

---

**当前状态**: 🚧 进行中 | **下一里程碑**: A3-2 纠偏完成

