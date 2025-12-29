# 投标响应抽取改进 - 三步方案实施总结

## ✅ 实施完成

按照用户指令，完成了三步改进，无需修改数据库schema或前端，仅修改Prompt和后处理逻辑。

---

## 📋 Step 1: 修正投标响应抽取 Prompt

### 修改内容

**文件**: 数据库 `prompt_templates` 表，`id='prompt_bid_response_v2_001'`，版本升级到 v4

### 新增的强制规则

#### 🚫 禁止规则1：price 维度的严格闸门
**只有同时满足以下两个条件时，才能归为 `dimension="price"`：**
1. 出现任一关键词：【投标总价/投标报价/报价表/报价汇总/开标一览表/投标函总价/报价一览/分项报价单】
2. 出现货币单位：【元/万元/￥/人民币】

**强制禁止归为 price 的情况：**
- 若文本出现【合同金额/业绩/类似项目/项目业绩/中标金额/合同价/历史业绩/业绩合同/已完成项目/完工项目金额】
- → **必须归为 `dimension="qualification"`**（业绩证明）

**示例**：
- ✅ "投标总价：500万元" → `dimension="price"`, `total_price_cny=5000000`
- ❌ "类似项目业绩：XX医院信息化建设，合同金额800万元" → `dimension="qualification"`（不是price！）

#### 🚫 禁止规则2：qualification 维度的明确归属
**以下内容必须归为 `dimension="qualification"`，不得归为 `doc_structure`：**
- 营业执照
- 法定代表人授权书/授权委托书
- 资质证书（如建筑资质、信息系统集成资质等）
- 安全生产许可证
- 保证金回执/保证金缴纳凭证
- 基本存款账户信息/银行开户许可证
- 财务审计报告
- 项目业绩证明/业绩合同
- 人员资格证书（如建造师、项目经理等）

#### 🚫 禁止规则3：doc_structure 维度的精确定义
**只有以下内容才归为 `dimension="doc_structure"`：**
- 密封要求（封口、封条、密封袋等）
- 装订要求（胶装、线装、骑马钉等）
- 签字盖章要求（法定代表人签字、公章位置等）
- 份数要求（正本几份、副本几份）
- 目录页码要求
- 偏离表/响应表
- 文件格式要求（A4纸、双面打印等）

#### 🚫 禁止规则4：原子事实拆分（必须执行）
**若同一句话/同一段落同时包含多个独立事实，必须拆成多条 response：**
- ✅ "质保期4年，工期90天" → 拆成2条：
  - 第1条：`dimension="business"`, `response_text="质保期4年"`, `warranty_months=48`
  - 第2条：`dimension="schedule_quality"`, `response_text="工期90天"`, `duration_days=90`

---

## 📋 Step 2: 添加抽取后矫正器

### 修改内容

**文件**: `/aidata/x-llmapp1/backend/app/works/tender/bid_response_service.py`

### 新增函数

```python
def normalize_and_fix_response(resp: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    抽取后矫正器：修正明显错误的维度分类，并拆分复合事实
    
    规则：
    1. dimension=="price" 且包含业绩关键词 → 强制改为 qualification
    2. dimension=="doc_structure" 且包含证书关键词 → 强制改为 qualification
    3. business 文本同时含质保和工期 → 拆成两条
    """
```

### 矫正规则

#### 规则1: price → qualification
- **触发条件**: `dimension="price"` 且 `response_text` 包含业绩关键词
- **关键词**: `合同金额|项目业绩|中标金额|类似项目|历史业绩|业绩合同|已完成项目|完工项目金额|近*年*完成|业绩证明`
- **操作**:
  - 强制改为 `dimension="qualification"`
  - 设置 `response_type="document_ref"`
  - 在 `extracted_value_json` 中标记 `{"type": "past_performance"}`

#### 规则2: doc_structure → qualification
- **触发条件**: `dimension="doc_structure"` 且 `response_text` 包含证书关键词
- **关键词**: `营业执照|授权书|授权委托书|资质证书|安全生产许可证|保证金回执|基本存款账户|银行开户许可证|财务审计报告|业绩证明|资格证书|建造师|项目经理`
- **操作**: 强制改为 `dimension="qualification"`

#### 规则3: business 拆分
- **触发条件**: `dimension="business"` 且同时包含质保和工期关键词
- **操作**: 拆成两条记录
  - 质保保留在 `business`
  - 工期放到 `schedule_quality`
  - 共享相同的 `evidence_segment_ids`

### 调用位置

在写入数据库前调用矫正器：
```python
for resp in responses_list:
    # ✅ Step 2: 应用矫正器（可能返回1条或2条）
    corrected_resps = normalize_and_fix_response(resp)
    
    for corrected_resp in corrected_resps:
        # 写入数据库...
```

---

## 📋 Step 3: 改进 Mapping 优先级

### 修改内容

**文件**: `/aidata/x-llmapp1/backend/app/works/tender/review_pipeline_v3.py`

### 增强的 `_mapping_score` 函数

```python
def _mapping_score(self, req: Dict, resp: Dict) -> int:
    """
    Step 3: normalized_fields 命中优先级（超高权重）
    
    如果 requirement.expected_evidence_json 里有 normalized_keys
    （如 ["total_price_cny", "duration_days", "warranty_months"]）
    且 response.normalized_fields_json 含这些 key 
    → 得分直接 +100（远超关键词权重）
    """
```

### 优先级规则

1. **normalized_fields 匹配** (+100分/每个key)
   - 检查 `requirement.expected_evidence_json.normalized_keys`
   - 如果 `response.normalized_fields_json` 含这些 key
   - 每匹配一个 key，加 100 分

2. **关键词匹配** (+1分/每个关键词)
   - 统计共同关键词数量

3. **综合分数**
   - `combined_score = keyword_score * 10 + jaccard_score`
   - normalized_fields 权重最高（100分 vs 10分）

### 效果

- ✅ "控制价/最高限价"条款 → 优先匹配到含 `total_price_cny` 的 price 响应
- ✅ "工期 90 天"条款 → 优先匹配到含 `duration_days` 的 schedule_quality 响应
- ✅ "质保期要求"条款 → 优先匹配到含 `warranty_months` 的 business 响应

---

## 🧪 验收方法

### 1. 重新抽取投标响应

```bash
# 在UI中或通过API重新抽取投标响应
# 确保使用最新的prompt和代码
```

### 2. 执行验收SQL

```bash
# 编辑 validation_sqls.sql，替换 YOUR_PROJECT_ID 为实际项目ID
vim /aidata/x-llmapp1/validation_sqls.sql

# 执行验收SQL
docker-compose exec postgres psql -U localgpt -d localgpt -f /validation_sqls.sql
```

### 3. 验收标准

#### ✅ 验收1: price 维度不应包含业绩金额
- **SQL**: 统计 `dimension='price'` 且包含业绩关键词的条目
- **期望**: `bad_price_rows = 0`

#### ✅ 验收2: qualification 维度应包含业绩金额
- **SQL**: 统计 `dimension='qualification'` 且包含业绩关键词的条目
- **期望**: `perf_in_qual > 0`

#### ✅ 验收3: doc_structure 不应包含证书
- **SQL**: 统计 `dimension='doc_structure'` 且包含证书关键词的条目
- **期望**: `bad_doc_structure = 0` 或极少

#### ✅ 验收4: 关键维度的核心字段至少各有一条
- **SQL**: 统计 price/duration/warranty 维度的核心条目
- **期望**: `price_core > 0`, `duration_core > 0`, `warranty_core > 0`

#### ✅ 验收5: normalized_fields_json 是否有数据
- **SQL**: 统计含 `total_price_cny`/`duration_days`/`warranty_months` 的条目
- **期望**: 三个字段都有数据（> 0）

#### ✅ 验收6: 维度分布统计
- **SQL**: 查看各维度的条目数量和百分比
- **期望**: 各维度都有合理数量的数据

#### ✅ 验收7: 矫正器生效验证
- **SQL**: 查看标记为 `past_performance` 的条目
- **期望**: `corrected_performance > 0`（说明矫正器捕获了业绩金额）

#### ✅ 验收8: evidence_json 是否正确组装
- **SQL**: 统计有 `evidence_json` 的条目比例
- **期望**: `evidence_percentage` 接近 100%

---

## 📊 预期效果

### 维度分类更准确
- ✅ 业绩金额不再被误判为投标价格
- ✅ 证书文件正确归类到 qualification
- ✅ 文档格式要求精确归类到 doc_structure

### 原子化更彻底
- ✅ 复合事实（如"质保+工期"）被拆分成两条独立记录
- ✅ 每条 response 只表达一个核心事实
- ✅ 便于后续审核流水线精确匹配

### 审核匹配更精准
- ✅ 数值型条款优先匹配到含结构化字段的 response
- ✅ "控制价"条款匹配到真实投标价格（而非业绩金额）
- ✅ "工期/质保"条款匹配到正确的维度和字段

### 后处理兜底
- ✅ 即使 LLM 犯错，矫正器也能捕获并修正
- ✅ 三重保障（Prompt规则 + LLM理解 + 后处理矫正）
- ✅ 系统鲁棒性显著提升

---

## 🎯 总结

### ✅ 完成的工作
1. **Step 1**: 修正投标响应抽取 Prompt（4条强制禁止规则）
2. **Step 2**: 添加抽取后矫正器（3条矫正规则）
3. **Step 3**: 改进 Mapping 优先级（normalized_fields 命中 +100分）

### ✅ 不需要的工作
- ❌ 不需要修改数据库 schema
- ❌ 不需要修改前端代码
- ❌ 不需要修改 API 接口

### ✅ 改进原理
- **Prompt**: 引导LLM在源头就正确分类
- **后处理**: 捕获并修正LLM的明显错误
- **Mapping**: 优先匹配能提供结构化字段的 response

### 🚀 下一步
1. 使用实际项目数据重新抽取投标响应
2. 执行验收SQL验证改进效果
3. 如果验收通过，三步改进全部生效！

---

**实施时间**: 2025-12-29  
**版本**: v1.0  
**状态**: ✅ 已完成，待验收
