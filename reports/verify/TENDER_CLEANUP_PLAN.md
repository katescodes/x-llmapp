# 能力定义纠偏 + 删除旧接口/旧实现 - 实施计划

## 已完成部分 ✅

### A0: 契约定义 ✅
- ✅ 创建 `backend/app/apps/tender/contracts/tender_contract_v1.yaml`
- ✅ 定义四大能力：project_info (4板块), risks, outline, review
- ✅ 定义 MUST_HIT_001 必命中规则
- ✅ 机器可验收的字段定义

### A1: 对比脚本 ✅
- ✅ 创建 `scripts/eval/tender_feature_parity.py`
- ✅ 支持 OLD vs NEW_ONLY 对比
- ✅ 支持单项目和批量测试（corpus_dir）
- ✅ 生成 diff_summary.json 和 report.md
- ✅ 验证契约合规性

### A2: 接入 CI ✅
- ✅ 修改 `scripts/ci/verify_cutover_and_extraction.py`
- ✅ 新增 Gate 7: tender_feature_parity
- ✅ 检查必须产出文件
- ✅ 强制退出码验证

---

## 待完成部分 🚧

### A3: 纠偏（若发现字段丢失）

**验证步骤**:
```bash
# 1. 确保数据库已初始化（上次遇到的问题）
cd /aidata/x-llmapp1
for f in backend/migrations/0*.sql; do 
  docker-compose exec -T postgres psql -U localgpt -d localgpt < "$f"
done

# 2. 运行功能一致性检查
docker-compose up -d
docker-compose exec -T backend python scripts/eval/tender_feature_parity.py

# 3. 检查报告
cat reports/verify/parity/testdata/report.md
cat reports/verify/parity/testdata/diff_summary.json
```

**如果发现缺失（预期会有）**:

#### 3.1 修改 extraction_specs
`backend/app/apps/tender/extraction_specs/project_info_v2.py`:
```python
# 当前可能只有一个通用 query
# 需要拆成 4 组，每组专注一个板块：

QUERIES = {
    "base": [
        {"name": "project_name", "query": "项目名称是什么？", "top_k": 3},
        {"name": "budget", "query": "预算金额是多少？", "top_k": 3},
        {"name": "purchaser", "query": "采购人/招标人是谁？", "top_k": 3},
        # ... 其他 base 字段
    ],
    "technical_parameters": [
        {"name": "tech_specs", "query": "技术参数和规格要求有哪些？", "top_k": 10},
        {"name": "performance", "query": "性能指标要求是什么？", "top_k": 5},
    ],
    "business_terms": [
        {"name": "payment", "query": "付款条款和方式？", "top_k": 5},
        {"name": "warranty", "query": "质保期和质保要求？", "top_k": 5},
    ],
    "scoring_criteria": [
        {"name": "scoring", "query": "评分标准和评标办法？", "top_k": 10},
        {"name": "weights", "query": "各项分值和权重？", "top_k": 5},
    ]
}
```

#### 3.2 修改 prompt
`backend/app/apps/tender/prompts/project_info_v2.md`:
```markdown
# 输出 JSON 格式（必须包含四大板块）：

{
  "base": {
    "project_name": "...",
    "budget": "...",
    // ... 其他 base 字段
  },
  "technical_parameters": [
    {
      "name": "参数名",
      "value": "参数值",
      "evidence_chunk_ids": ["seg_xxx"]
    }
  ],
  "business_terms": [
    {
      "clause_type": "payment",
      "content": "...",
      "evidence_chunk_ids": ["seg_xxx"]
    }
  ],
  "scoring_criteria": [
    {
      "criterion_name": "技术评分",
      "score": 60,
      "evidence_chunk_ids": ["seg_xxx"]
    }
  ]
}

## 注意：
- 四个 key 必须存在
- 未找到可以是空数组/空对象，但不能缺失
- 每项必须包含 evidence_chunk_ids
```

#### 3.3 修改落库逻辑
`backend/app/apps/tender/extract_v2_service.py`:
```python
def extract_project_info(...):
    # ... 调用引擎 ...
    result = engine.extract(...)
    
    # 确保四大板块都存在
    data_json = result.get('data', {})
    if 'base' not in data_json:
        data_json['base'] = {}
    if 'technical_parameters' not in data_json:
        data_json['technical_parameters'] = []
    if 'business_terms' not in data_json:
        data_json['business_terms'] = []
    if 'scoring_criteria' not in data_json:
        data_json['scoring_criteria'] = []
    
    # 写入 tender_project_info
    self.dao.update_project_info(project_id, data_json)
```

#### 3.4 验证纠偏效果
```bash
# 每次修改后都重新验证
docker-compose down
docker-compose build backend
docker-compose up -d
docker-compose exec -T backend python scripts/eval/tender_feature_parity.py

# 直到报告显示 PASS
```

---

### B1: TenderService 删除 OLD 分支

**目标**: `backend/app/services/tender_service.py` 内部只保留 NEW 实现

**步骤**:

#### B1.1 清理 extract_project_info (行 904)
```python
def extract_project_info(self, project_id: str, ...):
    # 删除所有 if mode == OLD/SHADOW/PREFER_NEW 分支
    # 统一走 NEW 路径：
    
    from app.apps.tender.extract_v2_service import ExtractV2Service
    
    v2_svc = ExtractV2Service(self.pool)
    v2_svc.extract_project_info(
        project_id=project_id,
        model_id=model_id,
        run_id=run_id,
        owner_id=owner_id
    )
    
    # 保留：run_id 记录、写兼容表（tender_project_info）
```

#### B1.2 清理 extract_risks (行 1131)
```python
def extract_risks(self, project_id: str, ...):
    # 统一走 NEW：
    from app.apps.tender.extract_v2_service import ExtractV2Service
    
    v2_svc = ExtractV2Service(self.pool)
    v2_svc.extract_risks(
        project_id=project_id,
        model_id=model_id,
        run_id=run_id,
        owner_id=owner_id
    )
```

#### B1.3 清理 generate_directory (行 1381)
```python
def generate_directory(self, project_id: str, ...):
    # 统一走 NEW
    from app.apps.tender.extract_v2_service import ExtractV2Service
    
    v2_svc = ExtractV2Service(self.pool)
    v2_svc.generate_directory(
        project_id=project_id,
        model_id=model_id,
        run_id=run_id,
        owner_id=owner_id
    )
```

#### B1.4 清理 run_review (行 2122)
```python
def run_review(self, project_id: str, ...):
    # 统一走 NEW
    from app.apps.tender.review_v2_service import ReviewV2Service
    
    v2_svc = ReviewV2Service(self.pool)
    v2_svc.run_review(
        project_id=project_id,
        model_id=model_id,
        custom_rule_asset_ids=custom_rule_asset_ids,
        bidder_name=bidder_name,
        bid_asset_ids=bid_asset_ids,
        run_id=run_id,
        owner_id=owner_id
    )
```

#### B1.5 删除旧 ingest 方法
删除或注释掉：
- `_ingest_tender_asset_old()` - 旧入库逻辑
- 所有引用 `kb_documents`, `kb_chunks` 的代码（除非是 KB 功能本身需要）

**验证**:
```bash
# 1. 检查是否还有 OLD 分支
rg -n "if.*mode.*==.*(OLD|SHADOW|PREFER_NEW)" backend/app/services/tender_service.py
# 应该返回 0 结果

# 2. 检查是否还有旧表引用
rg -n "kb_documents|kb_chunks" backend/app/services/tender_service.py
# 应该返回 0 结果（或只在注释中）

# 3. 编译检查
docker-compose exec -T backend python -m compileall backend/app

# 4. 功能检查
docker-compose exec -T backend python scripts/eval/tender_feature_parity.py
```

---

### B2: 删除招投标旧模块

**步骤**:

#### B2.1 扫描旧模块
```bash
cd /aidata/x-llmapp1
rg -n "services\.tender\.|from app\.services\.tender" backend/app | grep -v "tender_service.py"
```

#### B2.2 清理候选（谨慎！先确认用途）
可能需要删除/改shim的：
- `backend/app/services/tender/` 下只服务旧抽取的模块
- `backend/app/apps/tender/extract_diff.py` (如果只用于 shadow)
- `backend/app/apps/tender/review_diff.py` (如果只用于 shadow)

**不要删除**:
- `backend/app/services/tender_service.py` - 主服务（但内部已清理）
- `backend/app/apps/tender/extract_v2_service.py` - 新实现
- `backend/app/apps/tender/review_v2_service.py` - 新实现
- `backend/app/services/retrieval/` 如果 KB 功能还在用

#### B2.3 验证
```bash
# 确保 tender_service.py 不再引用旧模块
rg -n "from app\.services\.tender\." backend/app/services/tender_service.py
# 应该返回 0

# 编译检查
docker-compose exec -T backend python -m compileall backend/app
```

---

### B3: 禁止旧链路复活（硬门槛）

**修改**: `scripts/ci/check_platform_work_boundary.py`

```python
def check_tender_no_old_paths():
    """检查 tender_service 不使用旧链路（B3 硬门槛）"""
    tender_service = Path(__file__).parent.parent.parent / "backend" / "app" / "services" / "tender_service.py"
    
    violations = []
    
    if not tender_service.exists():
        return violations
    
    content = tender_service.read_text(encoding='utf-8')
    
    # 禁止模式
    forbidden_patterns = [
        (r'\bkb_documents\b', "禁止使用旧表 kb_documents"),
        (r'\bkb_chunks\b', "禁止使用旧表 kb_chunks"),
        (r'from\s+app\.services\.tender\.', "禁止导入 app.services.tender 旧模块"),
        (r'if.*mode.*==.*(OLD|SHADOW)', "禁止 OLD/SHADOW 分支（只允许 NEW_ONLY）"),
    ]
    
    for pattern, msg in forbidden_patterns:
        import re
        matches = list(re.finditer(pattern, content))
        for match in matches:
            # 排除注释
            line_start = content.rfind('\n', 0, match.start()) + 1
            line_end = content.find('\n', match.end())
            if line_end == -1:
                line_end = len(content)
            line = content[line_start:line_end]
            
            if not line.strip().startswith('#'):
                violations.append(
                    f"backend/app/services/tender_service.py: {msg}\n"
                    f"    违规行: {line.strip()}"
                )
    
    return violations


# 在 main() 中调用
def main():
    # ... 现有检查 ...
    
    # B3: Tender 旧链路检查
    print()
    print("检查4: Tender 不使用旧链路（B3 硬门槛）...")
    tender_violations = check_tender_no_old_paths()
    if tender_violations:
        print("  ✗ FAIL: 发现旧链路使用")
        for v in tender_violations:
            print(f"    - {v}")
        all_passed = False
    else:
        print("  ✓ PASS: Tender 已完全迁移到 NEW")
```

**验证**:
```bash
docker-compose exec -T backend python scripts/ci/check_platform_work_boundary.py
# 应该包含 "✓ PASS: Tender 已完全迁移到 NEW"
```

---

## 最终验收清单

### 必须全部 PASS:

```bash
cd /aidata/x-llmapp1
docker-compose exec -T backend make clean-reports
docker-compose exec -T backend make verify-docker
```

**验收判据**:

1. ✅ Gate 1-6 全绿（现有 gates）
2. ✅ Gate 7: tender_feature_parity PASS
3. ✅ reports/verify/parity/testdata/ 下所有文件存在且 size>0:
   - new_project_info.json
   - old_project_info.json
   - new_risks.json
   - old_risks.json
   - new_review.json
   - old_review.json
   - diff_summary.json
   - report.md
4. ✅ 边界检查新增 Tender 旧链路检查 PASS
5. ✅ `rg -n "kb_documents|kb_chunks|services\.tender\." backend/app/services/tender_service.py` 返回 0

---

## 实施顺序（严格遵守）

1. **A3: 纠偏**（如果 Gate 7 首次运行失败）
   - 修改 extraction_specs
   - 修改 prompts
   - 修改落库逻辑
   - 验证直到 PASS

2. **B1: 删除 OLD 分支**
   - 一个函数一个函数清理
   - 每清理一个函数就编译+测试
   - 确保不破坏功能

3. **B2: 删除旧模块**
   - 先扫描依赖关系
   - 谨慎删除（避免误删 KB 共用代码）
   - 可以先改 shim + 报错，而不是直接删除

4. **B3: 加硬门槛**
   - 修改 boundary check
   - 接入 CI
   - 防止回退

5. **最终验收**
   - `make verify-docker` 全绿
   - 所有检查项 PASS

---

## 注意事项

### 数据库初始化问题
上次 Step 3 遇到 `users` 表缺失，需要：
```bash
cd /aidata/x-llmapp1
for f in backend/migrations/0*.sql; do 
  docker-compose exec -T postgres psql -U localgpt -d localgpt < "$f" 2>&1 | tail -2
done
```

### Milvus 文件锁定
如果遇到 "Open /app/data/milvus.db failed"：
```bash
docker-compose down
rm -f data/milvus.db-wal data/milvus.db-shm
docker-compose up -d
```

### 契约不可降级
- **禁止**: 为了让 Gate 7 PASS 而降低契约要求
- **正确**: 修改实现和映射，让 NEW_ONLY 满足契约

### 保持 API 兼容
- 对外 API 路由不要改（前端依赖）
- 只删除内部实现和旧表
- 兼容表（tender_project_info 等）必须保留

---

## 时间估算

- A3 纠偏: 2-4 小时（如果有字段缺失）
- B1 删除 OLD 分支: 2-3 小时
- B2 删除旧模块: 1-2 小时
- B3 加硬门槛: 0.5 小时
- 验收调试: 1-2 小时

**总计**: 约 6-11 小时（取决于纠偏工作量）

---

## 当前状态

- ✅ A0: 契约定义完成
- ✅ A1: 对比脚本完成
- ✅ A2: 接入 CI 完成
- 🚧 A3: 待运行验证，根据结果纠偏
- 🚧 B1-B3: 待 A3 完成后执行

**下一步**: 运行 Gate 7，检查是否需要纠偏

