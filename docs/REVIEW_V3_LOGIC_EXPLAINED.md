# ReviewV3 审核逻辑详解

## 核心理念

**V3审核 = 招标要求（Requirements） × 投标响应（Responses） + 规则引擎（Rules）**

不同于V2的检索驱动方式，V3是**结构化数据驱动**的审核方式。

## 一、核心概念

### 1. 三个关键数据源

```
┌─────────────────────────────────────────────────────────────┐
│                     V3审核数据流                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  招标文件                投标文件                 自定义规则包  │
│     ↓                     ↓                        ↓        │
│  ┌──────────┐         ┌──────────┐            ┌──────────┐ │
│  │ 招标要求  │         │ 投标响应  │            │ 评估规则  │ │
│  │Requirements│       │ Responses │            │  Rules   │ │
│  └──────────┘         └──────────┘            └──────────┘ │
│       │                    │                        │       │
│       │                    │                        │       │
│       └────────────────────┴────────────────────────┘       │
│                            ↓                                │
│                    ┌───────────────┐                        │
│                    │  审核引擎      │                        │
│                    │Review Engine  │                        │
│                    └───────────────┘                        │
│                            ↓                                │
│                    ┌───────────────┐                        │
│                    │  审核结果      │                        │
│                    │Review Items   │                        │
│                    └───────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

#### A. 招标要求（tender_requirements）

**来源**：从招标文件中抽取（通过LLM）

**结构**：
```python
{
  "requirement_id": "business_001",
  "dimension": "business",      # 维度：business/technical/qualification/commercial
  "requirement_text": "不得转包、分包的承诺",
  "is_hard": True,              # 是否硬性要求
  "req_type": "commitment",     # 要求类型
  "allow_deviation": False,     # 是否允许偏离
  "value_schema_json": {...}    # 值模式（如果是数值型要求）
}
```

**特点**：
- 从招标文件中AI抽取
- 结构化存储
- 包含完整的要求信息
- **本身就是审核依据**

#### B. 投标响应（tender_bid_response_items）

**来源**：从投标文件中抽取（通过LLM）

**结构**：
```python
{
  "bidder_name": "123",
  "dimension": "technical",      # 对应招标要求的维度
  "response_type": "text",       # text/document_ref/structured_value/numeric
  "response_text": "端到端闭环：从数据接入到预警输出...",
  "extracted_value_json": {...}, # 结构化值（如果是数值型）
  "evidence_chunk_ids": [...]    # 证据片段ID
}
```

**特点**：
- 从投标文件中AI抽取
- 按维度组织
- 包含证据链接
- 支持多种响应类型

#### C. 自定义规则（tender_rules + tender_rule_packs）

**来源**：用户创建或系统预设

**结构**：
```python
{
  "rule_key": "qual_license_check",
  "rule_name": "营业执照检查",
  "dimension": "qualification",
  "evaluator": "deterministic",  # 或 "semantic_llm"
  "condition_json": {            # 规则条件
    "type": "must_provide",
    "target": "营业执照"
  },
  "severity": "critical",        # critical/high/medium/low
  "is_hard": True
}
```

**特点**：
- 可选的（不是必须的）
- 用于精细化审核
- 支持确定性规则和语义规则

## 二、两种审核模式

### 模式A：基础评估模式（BASIC_REQUIREMENTS_ONLY）

**触发条件**：没有自定义规则包

**评估逻辑**：
```python
for requirement in requirements:
    # 1. 按维度查找响应
    responses_in_dimension = filter_by_dimension(responses, requirement.dimension)
    
    # 2. 判断是否有响应
    if len(responses_in_dimension) == 0:
        if requirement.is_hard:
            result = "FAIL"  # 硬性要求未响应 → 不合格
            reason = "硬性要求未响应"
        else:
            result = "WARN"  # 非硬性要求未响应 → 警告
            reason = "建议性要求未响应"
    else:
        # 3. 检查响应完整性
        total_length = sum(len(r.response_text) for r in responses_in_dimension)
        if total_length < 10:
            result = "WARN"
            reason = "响应过于简短，可能不完整"
        else:
            result = "PASS"
            reason = f"已提供{len(responses_in_dimension)}条响应"
    
    # 4. 生成审核结果
    review_item = {
        "requirement_id": requirement.requirement_id,
        "result": result,
        "reason": reason,
        "evaluator": "basic_requirement_evaluator"
    }
```

**特点**：
- ✅ 快速、简单
- ✅ 覆盖所有招标要求
- ✅ 不需要配置规则
- ⚠️ 只做基础匹配，不做深度审核

**适用场景**：
- 快速初审
- 简单项目
- 没有特殊规则要求

### 模式B：自定义规则模式（CUSTOM_RULES）

**触发条件**：有自定义规则包

**评估逻辑**：
```python
# 1. 加载有效规则集
effective_rules = load_rules(custom_rule_pack_ids)

# 2. 分离规则类型
deterministic_rules = [r for r in effective_rules if r.evaluator == "deterministic"]
semantic_rules = [r for r in effective_rules if r.evaluator == "semantic_llm"]

# 3. 执行确定性规则引擎
deterministic_results = []
for rule in deterministic_rules:
    # 按规则类型执行不同的检查
    if rule.condition.type == "check_requirement_response":
        # 检查特定要求是否有响应
    elif rule.condition.type == "check_value_threshold":
        # 检查数值是否满足阈值
    elif rule.condition.type == "must_provide":
        # 检查必须提供的文档或信息
    # ... 更多规则类型

# 4. 执行语义LLM规则引擎（可选）
semantic_results = []
for rule in semantic_rules:
    # 使用LLM进行语义判断
    # 例如：判断技术方案的可行性、完整性等

# 5. 执行基础评估（补充）
basic_results = basic_evaluator.evaluate_requirements(requirements, responses)

# 6. 合并所有结果
all_results = deterministic_results + semantic_results + basic_results
```

**特点**：
- ✅ 精细化审核
- ✅ 规则 + 基础评估双重保障
- ✅ 支持复杂业务逻辑
- ✅ 可扩展、可配置
- ⚠️ 需要配置规则包

**适用场景**：
- 正式审核
- 复杂项目
- 有特定规则要求

## 三、完整审核流程

```
┌─────────────────────────────────────────────────────────────┐
│ ReviewV3Service.run_review_v3()                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Step 1: 读取招标要求                                          │
│   requirements = get_requirements(project_id)               │
│   └─ SELECT * FROM tender_requirements WHERE project_id = ?│
│                                                              │
│ Step 2: 读取投标响应                                          │
│   responses = get_responses(project_id, bidder_name)       │
│   └─ SELECT * FROM tender_bid_response_items WHERE ...     │
│                                                              │
│ Step 3: 判断审核模式                                          │
│   if not custom_rule_pack_ids:                             │
│       # 尝试自动加载共享规则包                                │
│       custom_rule_pack_ids = auto_load_shared_packs()      │
│                                                              │
│ Step 4a: 模式A - 基础评估（无规则包）                         │
│   basic_results = BasicRequirementEvaluator.evaluate(...)  │
│   └─ 遍历每个requirement，检查是否有response                 │
│                                                              │
│ Step 4b: 模式B - 规则引擎（有规则包）                         │
│   ┌─ effective_rules = build_effective_ruleset(...)        │
│   │                                                          │
│   ├─ deterministic_results =                                │
│   │    DeterministicEngine.evaluate_rules(...)             │
│   │    └─ 执行确定性规则（条件匹配）                          │
│   │                                                          │
│   ├─ semantic_results =                                     │
│   │    SemanticLLMEngine.evaluate_rules(...)               │
│   │    └─ 执行语义规则（LLM判断）                            │
│   │                                                          │
│   └─ basic_results =                                        │
│        BasicRequirementEvaluator.evaluate(...)             │
│        └─ 基础评估（补充）                                    │
│                                                              │
│ Step 5: 合并结果                                             │
│   all_results = rule_results + basic_results               │
│                                                              │
│ Step 6: 保存到数据库                                         │
│   INSERT INTO tender_review_items (...)                    │
│                                                              │
│ Step 7: 统计并返回                                           │
│   return {                                                  │
│       "review_mode": "CUSTOM_RULES" | "BASIC_...",         │
│       "requirement_count": 69,                             │
│       "response_count": 12,                                │
│       "rule_count": 7,                                     │
│       "finding_count": 69,                                 │
│       "pass_count": 17,                                    │
│       "fail_count": 50,                                    │
│       "warn_count": 2,                                     │
│       "items": [...]                                       │
│   }                                                         │
└─────────────────────────────────────────────────────────────┘
```

## 四、审核结果结构

每条审核结果（tender_review_items）包含：

```python
{
    "id": "uuid",
    "project_id": "tp_xxx",
    "bidder_name": "123",
    "dimension": "business",           # 维度
    "requirement_id": "business_001",  # 招标要求ID
    "requirement_text": "不得转包...", # 招标要求文本
    "bid_response": "我司承诺...",     # 投标响应文本
    "result": "PASS",                 # PASS/WARN/FAIL
    "remark": "已提供响应",            # 评估说明
    "is_hard": True,                  # 是否硬性要求
    "rule_id": "rule_xxx",            # 应用的规则ID（可选）
    "severity": "medium",             # 严重程度
    "evaluator": "basic_requirement_evaluator" # 评估器类型
}
```

## 五、V2 vs V3 对比

| 特性 | V2 (检索驱动) | V3 (结构化驱动) |
|------|--------------|----------------|
| **数据基础** | 文档片段（chunks） | 结构化要求和响应 |
| **审核方式** | 检索匹配 | 逐项对比 + 规则引擎 |
| **准确性** | 依赖检索质量 | 依赖抽取质量 + 规则 |
| **覆盖度** | 可能遗漏 | 确保全覆盖 |
| **规则支持** | ❌ | ✅ |
| **可解释性** | 低 | 高 |
| **速度** | 快 | 中等 |
| **适用场景** | 快速审核 | 正式审核 |

## 六、关键优势

1. **结构化**：基于明确的要求和响应，不是模糊的文本检索
2. **全覆盖**：确保每个招标要求都被评估
3. **可追溯**：每条审核结果都有明确的依据
4. **可扩展**：支持自定义规则，适应不同业务需求
5. **灵活性**：可以不用规则包（基础评估）或使用规则包（精细审核）
6. **双保险**：规则引擎 + 基础评估，确保不遗漏

## 七、使用建议

### 何时使用基础评估模式？
- ✅ 快速初审
- ✅ 简单项目
- ✅ 还没有配置规则包

### 何时使用自定义规则模式？
- ✅ 正式审核
- ✅ 复杂项目
- ✅ 有特定业务规则
- ✅ 需要详细的合规性检查

### 规则包设计建议
1. **按维度组织**：business、technical、qualification、commercial
2. **区分严重程度**：critical、high、medium、low
3. **明确硬性要求**：is_hard = True
4. **选择合适的评估器**：deterministic（快速、精确）vs semantic_llm（灵活、智能）

## 八、示例

### 示例：基础评估

**输入：**
- 招标要求：69条（包含business、technical、qualification等维度）
- 投标响应：12条（主要是technical维度）
- 规则包：无

**输出：**
```
review_mode: BASIC_REQUIREMENTS_ONLY
finding_count: 69
├─ PASS: 12 (有响应的维度)
├─ WARN: 7  (响应不完整或非硬性要求未响应)
└─ FAIL: 50 (硬性要求未响应)
```

### 示例：自定义规则审核

**输入：**
- 招标要求：69条
- 投标响应：12条
- 规则包：6个，包含7条规则

**输出：**
```
review_mode: CUSTOM_RULES
finding_count: 69
├─ 规则引擎结果：0条（规则匹配到的问题）
├─ 基础评估结果：69条
│  ├─ PASS: 17
│  ├─ WARN: 2
│  └─ FAIL: 50
└─ 总计：69条审核结果
```

## 九、技术实现

### 核心类

```python
# 1. 审核服务主类
class ReviewV3Service:
    def __init__(self, pool, llm_orchestrator):
        self.basic_evaluator = BasicRequirementEvaluator()
        self.deterministic_engine = DeterministicRuleEngine()
        self.semantic_engine = SemanticLLMRuleEngine(llm_orchestrator)
        self.ruleset_builder = EffectiveRulesetBuilder(pool)
    
    async def run_review_v3(self, project_id, bidder_name, ...):
        # 主审核逻辑
        ...

# 2. 基础要求评估器
class BasicRequirementEvaluator:
    def evaluate_requirements(self, requirements, responses):
        # 逐项检查requirement是否有response
        ...

# 3. 确定性规则引擎
class DeterministicRuleEngine:
    def evaluate_rules(self, rules, requirements, responses):
        # 执行确定性规则
        ...

# 4. 语义LLM规则引擎
class SemanticLLMRuleEngine:
    async def evaluate_rules(self, rules, requirements, responses, model_id):
        # 使用LLM执行语义规则
        ...

# 5. 有效规则集构建器
class EffectiveRulesetBuilder:
    def build_effective_ruleset(self, project_id, custom_rule_pack_ids):
        # 加载并合并规则
        ...
```

## 十、总结

**V3审核的本质**：
- 将审核任务分解为：**结构化数据抽取** → **逐项对比** → **规则评估** → **结果汇总**
- 核心优势：**准确、全面、可追溯、可扩展**
- 适用场景：**需要精确、可靠审核结果的正式投标审核**

**V3的创新之处**：
1. 首次实现了基于结构化数据的审核（而不是文本检索）
2. 支持可选的自定义规则，灵活性高
3. 双层保障（规则 + 基础评估），确保不遗漏
4. 完整的审核链路和证据追溯

