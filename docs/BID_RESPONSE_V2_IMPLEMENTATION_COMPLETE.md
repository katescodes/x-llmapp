# 投标响应抽取 V2 升级 - 实施完成报告

**日期**: 2025-12-29  
**状态**: ✅ 代码实施完成，待用户测试

---

## ✅ 已完成所有实施步骤 (Steps 1-5)

### Step 1: 创建 v2 Prompt 并写入数据库 ✅

**成果**:
- 文件: `backend/prompts/bid_response_extraction_v2.md` (9688字符)
- 数据库: `prompt_templates.id='prompt_bid_response_v2_001'`
- Version: 2, Active: true

**v2 新特性**:
```json
{
  "schema_version": "bid_response_v2",
  "normalized_fields_json": {
    "company_name": "XX公司",
    "credit_code": "91110000...",
    "total_price_cny": 1280000,
    "warranty_months": 36,
    "duration_days": 120
  },
  "evidence_segment_ids": ["seg_bid_001", "seg_bid_002"],
  "evidence_chunk_ids": ["seg_bid_001", "seg_bid_002"]
}
```

### Step 2: 创建 bid_response_v2.py Spec 文件 ✅

**成果**:
- 文件: `backend/app/works/tender/extraction_specs/bid_response_v2.py`
- 函数: `build_bid_response_spec_v2_async(pool)`
- 优先加载: `prompt_bid_response_v2_001`

### Step 3: 修改 BidResponseService 支持 v2 字段 ✅

**成果**:
- 新增方法: `extract_bid_response_v2()`
- 解析 v2 输出: normalized_fields_json + evidence_segment_ids
- 兼容性处理: chunk_ids ↔ segment_ids

**辅助函数**:
```python
_prefetch_doc_segments(segment_ids)    # 批量SQL查询
_make_quote(text, limit=220)           # 截取quote
_build_evidence_json_from_segments()   # 组装统一结构
```

### Step 4: 更新落库逻辑 - 组装 evidence_json ✅

**成果**:
- 批量预取 doc_segments (避免N+1查询)
- 组装 evidence_json:
  ```json
  [
    {
      "segment_id": "seg_bid_001",
      "asset_id": "...",
      "page_start": 12,
      "page_end": 12,
      "heading_path": "第二部分/技术方案",
      "quote": "本次投标产品完全符合国家标准...",
      "segment_type": "paragraph",
      "source": "doc_segments"
    }
  ]
  ```

**落库字段**:
- `normalized_fields_json`: JSONB (标准化字段)
- `evidence_json`: JSONB array (页码+引用)
- `evidence_chunk_ids`: TEXT[] (向后兼容)

### Step 5: ReviewPipelineV3 读取 normalized_fields_json ✅

**成果**:
- Consistency 检查优先使用 v2 标准字段
- 价格: `total_price_cny` (降级: total_price/price)
- 工期: `duration_days` (降级: duration/construction_period)
- 公司名称: `company_name` (已实现)

**代码修改**:
```python
# 优先级设计
price_field = (
    normalized_fields.get("total_price_cny") or 
    normalized_fields.get("total_price") or 
    normalized_fields.get("price")
)
```

---

## 📋 Git 提交记录

```bash
9b9d313 - 🔧 实现: BidResponseService v2 + ReviewPipelineV3 适配
8d977b7 - ✨ 新增: 投标响应抽取 v2 (normalized_fields + evidence_segments)
```

---

## 🧪 测试准备

### 测试脚本已创建

**文件**: `test_bid_response_v2.sh`

**测试流程**:
1. 清理旧数据
2. 触发 v2 抽取（需要用户在前端操作）
3. 验收 normalized_fields_json
4. 验收 evidence_json 结构
5. 运行审核
6. 验收 consistency 检查

### 用户操作步骤

#### 1. 刷新前端页面
```bash
访问: http://192.168.2.17:6173
按 Ctrl+F5 强制刷新
```

#### 2. 进入项目并抽取投标响应
```
1. 进入项目: tp_3f49f66ead6d46e1bac3f0bd16a3efe9
2. 选择投标人: "123"
3. 点击"开始抽取"按钮（投标响应抽取 tab）
4. 等待抽取完成
```

#### 3. 验收抽取结果
```bash
# 在服务器上运行
cd /aidata/x-llmapp1
./test_bid_response_v2.sh
```

**预期结果**:
- `has_nf` >= 70% (至少70%响应有normalized_fields)
- `has_ev` >= 70% (至少70%响应有evidence_json)
- 商务维度有 `total_price_cny`, `warranty_months`, `duration_days`
- evidence_json 包含 `page_start`, `source`, `quote`

#### 4. 运行审核
```
1. 在前端点击"开始审核"按钮
2. 等待审核完成
```

#### 5. 验收审核结果
```bash
# 再次运行测试脚本查看审核结果
./test_bid_response_v2.sh
```

**预期结果**:
- consistency 维度存在审核项
- consistency 不再全是 PENDING
- 能看到 company_name/price/duration 的一致性判断

---

## 📊 验收指标清单

### 抽取阶段

- [ ] **API返回成功**: 显示 "成功抽取X条响应数据 (v2)"
- [ ] **normalized_fields 覆盖率**: >= 70%
- [ ] **evidence_json 覆盖率**: >= 70%
- [ ] **商务维度标准字段**:
  - [ ] `total_price_cny` (数值类型)
  - [ ] `warranty_months` (数值类型)
  - [ ] `duration_days` (数值类型)
- [ ] **资格维度标准字段**:
  - [ ] `company_name` (字符串)
  - [ ] `credit_code` (18位)
- [ ] **evidence_json 结构**:
  - [ ] `page_start` 不为空
  - [ ] `quote` 不为空 (长度 < 220)
  - [ ] `source` = "doc_segments"

### 审核阶段

- [ ] **consistency 维度存在**: 至少1条
- [ ] **consistency 不全是 PENDING**: 有PASS/WARN/FAIL
- [ ] **价格一致性**: 能读取 total_price_cny
- [ ] **工期一致性**: 能读取 duration_days
- [ ] **公司名称一致性**: 能读取 company_name

---

## 🔍 验收SQL查询

### 查询1: 总体统计
```sql
SELECT 
  COUNT(*) as total,
  SUM(CASE WHEN normalized_fields_json IS NOT NULL AND normalized_fields_json != '{}' THEN 1 ELSE 0 END) as has_nf,
  SUM(CASE WHEN evidence_json IS NOT NULL THEN 1 ELSE 0 END) as has_ev
FROM tender_bid_response_items
WHERE project_id='tp_3f49f66ead6d46e1bac3f0bd16a3efe9' AND bidder_name='123';
```

### 查询2: 商务维度字段
```sql
SELECT 
  normalized_fields_json->'total_price_cny' as price,
  normalized_fields_json->'warranty_months' as warranty,
  normalized_fields_json->'duration_days' as duration,
  response_text
FROM tender_bid_response_items
WHERE project_id='tp_3f49f66ead6d46e1bac3f0bd16a3efe9' 
AND bidder_name='123'
AND dimension IN ('business', 'price');
```

### 查询3: evidence_json 结构
```sql
SELECT 
  dimension,
  jsonb_array_length(evidence_json) as ev_count,
  evidence_json->0->'page_start' as first_page,
  evidence_json->0->'quote' as first_quote
FROM tender_bid_response_items
WHERE project_id='tp_3f49f66ead6d46e1bac3f0bd16a3efe9' 
AND bidder_name='123'
LIMIT 5;
```

### 查询4: consistency 审核结果
```sql
SELECT 
  requirement_id,
  status,
  remark
FROM tender_review_items
WHERE project_id='tp_3f49f66ead6d46e1bac3f0bd16a3efe9' 
AND bidder_name='123'
AND dimension='consistency';
```

---

## 🚨 常见问题排查

### 问题1: 抽取后 normalized_fields_json 为空 {}

**可能原因**:
1. LLM 输出不符合 v2 schema
2. Prompt 没有正确加载

**排查步骤**:
```bash
# 1. 查看后端日志
docker-compose logs --tail=100 backend | grep -i "bid_response\|schema_version"

# 2. 验证 prompt 版本
docker-compose exec -T postgres psql -U localgpt -d localgpt -c \
  "SELECT id, version, is_active FROM prompt_templates WHERE module='bid_response';"

# 3. 查看 LLM 原始输出（需要在代码中添加日志）
```

### 问题2: evidence_json 为 null

**可能原因**:
1. doc_segments 表中没有对应的 segment_id
2. evidence_segment_ids 为空

**排查步骤**:
```bash
# 1. 查看 evidence_chunk_ids
docker-compose exec -T postgres psql -U localgpt -d localgpt -c \
  "SELECT evidence_chunk_ids FROM tender_bid_response_items 
   WHERE project_id='tp_3f49f66ead6d46e1bac3f0bd16a3efe9' LIMIT 5;"

# 2. 验证 doc_segments 数据
docker-compose exec -T postgres psql -U localgpt -d localgpt -c \
  "SELECT segment_id, page_start FROM doc_segments 
   WHERE segment_id = ANY(ARRAY['seg_bid_001', 'seg_bid_002']);"
```

### 问题3: consistency 全是 PENDING

**可能原因**:
1. normalized_fields_json 为空，没有数据可对比
2. 字段名不匹配（使用了旧字段名）

**排查步骤**:
```bash
# 查看商务维度的 normalized_fields
docker-compose exec -T postgres psql -U localgpt -d localgpt -c \
  "SELECT dimension, normalized_fields_json 
   FROM tender_bid_response_items 
   WHERE project_id='tp_3f49f66ead6d46e1bac3f0bd16a3efe9' 
   AND dimension='business';"
```

---

## 📝 关键代码位置

### 后端

| 文件 | 说明 |
|------|------|
| `backend/prompts/bid_response_extraction_v2.md` | v2 Prompt 模板 |
| `backend/app/works/tender/extraction_specs/bid_response_v2.py` | v2 Spec 定义 |
| `backend/app/works/tender/bid_response_service.py` | v2 抽取服务 |
| `backend/app/routers/tender.py` | 路由 (调用 v2) |
| `backend/app/works/tender/review_pipeline_v3.py` | 审核流程 (使用 normalized_fields) |

### 数据库

| 表 | 字段 |
|-----|------|
| `prompt_templates` | `id='prompt_bid_response_v2_001'` |
| `tender_bid_response_items` | `normalized_fields_json`, `evidence_json` |
| `doc_segments` | `segment_id`, `page_start`, `content` |
| `tender_review_items` | `dimension='consistency'` |

---

## 🎯 下一步行动

### 立即操作

1. **用户在前端执行抽取**:
   - 访问 `http://192.168.2.17:6173`
   - 进入项目，选择投标人 "123"
   - 点击"开始抽取"

2. **运行验收脚本**:
   ```bash
   cd /aidata/x-llmapp1
   ./test_bid_response_v2.sh
   ```

3. **执行审核**:
   - 在前端点击"开始审核"

4. **再次运行验收脚本**:
   ```bash
   ./test_bid_response_v2.sh
   ```

### 后续优化（可选）

1. **LLM 输出质量监控**:
   - 添加日志记录 LLM 原始输出
   - 统计 normalized_fields 填充率

2. **Evidence 定位精度**:
   - 验证 page_start 准确性
   - 确认 quote 内容相关性

3. **前端展示**:
   - 在投标响应表格中显示 normalized_fields
   - 在证据面板中显示 page_start 和 quote

---

## ✅ 总结

**实施状态**: 
- ✅ Steps 1-5 代码实施完成
- ✅ 服务已重启并运行最新代码
- ⏳ Step 6 等待用户执行抽取和审核操作
- ⏳ 验收脚本已准备就绪

**重要提示**:
- 所有代码已提交到 Git: `9b9d313`
- 数据库 schema 已支持 v2 字段
- Prompt 已写入数据库并激活
- 路由已切换到 v2 方法

**用户只需**:
1. 刷新前端
2. 执行抽取操作
3. 运行测试脚本验收
4. 执行审核操作
5. 再次验收

一切准备就绪！🚀

