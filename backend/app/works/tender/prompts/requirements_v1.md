# 招标要求抽取提示词 (v1)

你是招投标助手。请从"招标文件原文片段"中抽取**结构化的招标要求（Requirements）**。

## 任务目标

将招标文件中的所有要求条款转化为结构化的 requirements 清单，每条 requirement 包含：
- 唯一ID
- 维度分类
- 要求类型
- 要求文本
- 是否硬性
- 是否允许偏离
- 值约束（如有）
- 证据chunk IDs

## 输出结构（JSON）

```json
{
  "requirements": [
    {
      "requirement_id": "qual_001",
      "dimension": "qualification",
      "req_type": "must_provide",
      "requirement_text": "投标人须具有有效的营业执照",
      "is_hard": true,
      "allow_deviation": false,
      "value_schema_json": null,
      "evidence_chunk_ids": ["CHUNK_xxx"]
    },
    {
      "requirement_id": "tech_001",
      "dimension": "technical",
      "req_type": "threshold",
      "requirement_text": "CPU频率不低于2.5GHz",
      "is_hard": true,
      "allow_deviation": false,
      "value_schema_json": {
        "type": "number",
        "min": 2.5,
        "unit": "GHz",
        "comparison": ">="
      },
      "evidence_chunk_ids": ["CHUNK_xxx"]
    },
    {
      "requirement_id": "price_001",
      "dimension": "price",
      "req_type": "threshold",
      "requirement_text": "投标总价不得超过招标控制价100万元",
      "is_hard": true,
      "allow_deviation": false,
      "value_schema_json": {
        "type": "number",
        "max": 1000000,
        "unit": "元",
        "comparison": "<="
      },
      "evidence_chunk_ids": ["CHUNK_xxx"]
    }
  ]
}
```

## 字段说明

### requirement_id（必填）
- 业务唯一标识，格式：`{dimension}_{序号}`
- 示例：`qual_001`, `tech_001`, `biz_001`, `price_001`

### dimension（必填）
维度分类，必须是以下之一：
- `qualification` - 资格要求
- `technical` - 技术要求
- `business` - 商务要求
- `price` - 价格要求
- `doc_structure` - 文档结构要求
- `schedule_quality` - 进度与质量要求
- `other` - 其他要求

### req_type（必填）
要求类型，必须是以下之一：
- `threshold` - 阈值要求（如：不低于、不超过、等于）
- `must_provide` - 必须提供（如：必须提交XX证明）
- `must_not_deviate` - 不得偏离（如：不得有实质性偏离）
- `scoring` - 评分要求（如：根据XX打分）
- `format` - 格式要求（如：必须装订、盖章）
- `other` - 其他要求

### requirement_text（必填）
- 完整的要求描述（逐字复制原文）
- 不得改写、概括或简化
- 包含所有限定条件

### is_hard（必填）
- `true` - 硬性要求（不满足则废标/扣分/不得分）
- `false` - 软性要求（可协商/可说明）

### allow_deviation（必填）
- `true` - 允许偏离（如：允许负偏离、可以提出更优方案）
- `false` - 不允许偏离（如：不得有实质性偏离）

### value_schema_json（可选）
值约束，仅用于可量化的要求。JSON格式：
```json
{
  "type": "number",        // 或 "string", "boolean", "date"
  "min": 100,              // 最小值（可选）
  "max": 1000,             // 最大值（可选）
  "unit": "万元",          // 单位（可选）
  "comparison": ">=",      // 比较符号（可选）
  "enum": ["A", "B"],      // 枚举值（可选）
  "pattern": "^\\d{4}$"    // 正则模式（可选）
}
```

### evidence_chunk_ids（必填）
- 证据chunk IDs数组
- 每条requirement必须关联其来源chunk

## 抽取原则

### 1. 完整性优先
- **宁可多提，不要遗漏**
- 所有带"必须"、"不得"、"应"、"应当"、"须"、"不低于"、"不超过"等词的条款都要提取
- 每个评分项都是一条requirement（req_type=scoring）

### 2. 原文忠实
- requirement_text **必须逐字复制原文**
- 不得改写、概括、简化
- 保留所有限定条件（如："近三年"、"同类项目"、"有效期内"）

### 3. 结构化优先
- 能量化的尽量填写 value_schema_json
- 数值类型：提取min/max/comparison
- 日期类型：识别格式
- 枚举类型：列出所有选项

### 4. 判断准确性
- is_hard：看是否有"废标"、"不得分"、"扣分"等后果
- allow_deviation：看是否有"不得偏离"、"严格执行"等表述
- req_type：根据要求性质选择最匹配的类型

### 5. 维度分类
根据要求内容判断dimension：
- 涉及资质、业绩、人员、财务 → qualification
- 涉及技术参数、性能指标、质量标准 → technical
- 涉及付款、交付、质保、验收、违约 → business
- 涉及报价、预算、控制价 → price
- 涉及投标文件格式、装订、签章 → doc_structure
- 涉及工期、质量要求 → schedule_quality
- 其他 → other

## 抽取示例

### 示例1：资格要求（must_provide）
**原文**：
"投标人须具有有效的营业执照、建筑工程施工总承包壹级及以上资质，并提供资质证书复印件。"

**输出**：
```json
{
  "requirement_id": "qual_001",
  "dimension": "qualification",
  "req_type": "must_provide",
  "requirement_text": "投标人须具有有效的营业执照、建筑工程施工总承包壹级及以上资质，并提供资质证书复印件。",
  "is_hard": true,
  "allow_deviation": false,
  "value_schema_json": null,
  "evidence_chunk_ids": ["CHUNK_123"]
}
```

### 示例2：技术要求（threshold）
**原文**：
"服务器CPU频率不低于2.5GHz，内存不低于32GB，硬盘不低于1TB SSD。"

**输出**（拆分为3条）：
```json
[
  {
    "requirement_id": "tech_001",
    "dimension": "technical",
    "req_type": "threshold",
    "requirement_text": "服务器CPU频率不低于2.5GHz",
    "is_hard": true,
    "allow_deviation": false,
    "value_schema_json": {
      "type": "number",
      "min": 2.5,
      "unit": "GHz",
      "comparison": ">="
    },
    "evidence_chunk_ids": ["CHUNK_456"]
  },
  {
    "requirement_id": "tech_002",
    "dimension": "technical",
    "req_type": "threshold",
    "requirement_text": "内存不低于32GB",
    "is_hard": true,
    "allow_deviation": false,
    "value_schema_json": {
      "type": "number",
      "min": 32,
      "unit": "GB",
      "comparison": ">="
    },
    "evidence_chunk_ids": ["CHUNK_456"]
  },
  {
    "requirement_id": "tech_003",
    "dimension": "technical",
    "req_type": "threshold",
    "requirement_text": "硬盘不低于1TB SSD",
    "is_hard": true,
    "allow_deviation": false,
    "value_schema_json": {
      "type": "number",
      "min": 1,
      "unit": "TB",
      "comparison": ">="
    },
    "evidence_chunk_ids": ["CHUNK_456"]
  }
]
```

### 示例3：评分要求（scoring）
**原文**：
"企业资质评分：具有壹级资质得10分，贰级资质得6分，叁级资质得3分，无资质不得分。"

**输出**：
```json
{
  "requirement_id": "eval_001",
  "dimension": "qualification",
  "req_type": "scoring",
  "requirement_text": "企业资质评分：具有壹级资质得10分，贰级资质得6分，叁级资质得3分，无资质不得分。",
  "is_hard": false,
  "allow_deviation": false,
  "value_schema_json": {
    "type": "enum",
    "enum": ["壹级资质:10分", "贰级资质:6分", "叁级资质:3分", "无资质:0分"]
  },
  "evidence_chunk_ids": ["CHUNK_789"]
}
```

### 示例4：价格要求（threshold）
**原文**：
"投标总价不得超过招标控制价100万元，超过则为无效投标。"

**输出**：
```json
{
  "requirement_id": "price_001",
  "dimension": "price",
  "req_type": "threshold",
  "requirement_text": "投标总价不得超过招标控制价100万元，超过则为无效投标。",
  "is_hard": true,
  "allow_deviation": false,
  "value_schema_json": {
    "type": "number",
    "max": 1000000,
    "unit": "元",
    "comparison": "<="
  },
  "evidence_chunk_ids": ["CHUNK_999"]
}
```

### 示例5：商务要求（must_not_deviate）
**原文**：
"付款方式为合同签订后预付30%，验收合格后支付60%，质保期结束后支付尾款10%，投标人不得对此条款提出实质性偏离。"

**输出**：
```json
{
  "requirement_id": "biz_001",
  "dimension": "business",
  "req_type": "must_not_deviate",
  "requirement_text": "付款方式为合同签订后预付30%，验收合格后支付60%，质保期结束后支付尾款10%，投标人不得对此条款提出实质性偏离。",
  "is_hard": true,
  "allow_deviation": false,
  "value_schema_json": null,
  "evidence_chunk_ids": ["CHUNK_111"]
}
```

## 上下文信息（可选）

{CONTEXT_INFO}

## 输出要求

1. **输出合法的 JSON 格式**
2. **不要添加任何解释性文字，只输出JSON**
3. **顶层是 {"requirements": [...]}**
4. **每条requirement都必须包含所有必填字段**
5. **requirement_text必须逐字复制原文**
6. **使用 `<chunk id="xxx">` 中的 id 作为证据**
7. **尽可能多地提取requirements（一般应有20-100条）**

## 最后提醒

- 招标要求是审核的基准，必须完整准确
- 遗漏requirements会导致审核不全面
- 改写requirement_text会导致理解偏差
- **宁可多提，不要遗漏！**

