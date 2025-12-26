# 📋 Tender Requirements 样例数据（20条）

基于真实招标场景的 requirements 示例，展示各种维度、类型和 is_hard 值的组合。

---

## 样例 1: 资格要求 - 营业执照（硬性）

```json
{
  "requirement_id": "qual_001",
  "dimension": "qualification",
  "req_type": "must_provide",
  "requirement_text": "投标人须具有有效的营业执照，营业执照须在有效期内，经营范围须包含本项目采购内容。",
  "is_hard": true,
  "allow_deviation": false,
  "value_schema_json": null,
  "evidence_chunk_ids": ["CHUNK_001"]
}
```

**说明**: 
- 硬性要求（无营业执照则废标）
- 不允许偏离
- 无值约束

---

## 样例 2: 资格要求 - 企业资质（硬性）

```json
{
  "requirement_id": "qual_002",
  "dimension": "qualification",
  "req_type": "must_provide",
  "requirement_text": "投标人须具有建筑工程施工总承包壹级及以上资质，并提供资质证书复印件加盖公章。",
  "is_hard": true,
  "allow_deviation": false,
  "value_schema_json": {
    "type": "enum",
    "enum": ["特级", "壹级"],
    "description": "资质等级要求"
  },
  "evidence_chunk_ids": ["CHUNK_002"]
}
```

**说明**: 
- 硬性要求（资质不符则废标）
- 有枚举值约束
- 不允许偏离

---

## 样例 3: 资格要求 - 项目业绩（软性评分）

```json
{
  "requirement_id": "qual_003",
  "dimension": "qualification",
  "req_type": "scoring",
  "requirement_text": "企业业绩评分（满分20分）：近三年内完成过类似项目3个及以上得20分，2个得12分，1个得6分，0个不得分。",
  "is_hard": false,
  "allow_deviation": false,
  "value_schema_json": {
    "type": "enum",
    "enum": ["3个及以上:20分", "2个:12分", "1个:6分", "0个:0分"],
    "max_score": 20
  },
  "evidence_chunk_ids": ["CHUNK_003"]
}
```

**说明**: 
- 软性要求（评分项，不满足不废标）
- 有评分规则
- 不允许偏离

---

## 样例 4: 资格要求 - 项目经理（硬性）

```json
{
  "requirement_id": "qual_004",
  "dimension": "qualification",
  "req_type": "must_provide",
  "requirement_text": "项目经理须具有建造师一级及以上资格证书，且注册专业为建筑工程，并提供近三个月社保缴纳证明。",
  "is_hard": true,
  "allow_deviation": false,
  "value_schema_json": null,
  "evidence_chunk_ids": ["CHUNK_004"]
}
```

**说明**: 
- 硬性要求（项目经理不符合则废标）
- 不允许偏离

---

## 样例 5: 技术要求 - CPU参数（硬性阈值）

```json
{
  "requirement_id": "tech_001",
  "dimension": "technical",
  "req_type": "threshold",
  "requirement_text": "服务器CPU频率不低于2.5GHz，核心数不少于8核。",
  "is_hard": true,
  "allow_deviation": false,
  "value_schema_json": {
    "type": "object",
    "properties": {
      "cpu_frequency": {
        "type": "number",
        "min": 2.5,
        "unit": "GHz",
        "comparison": ">="
      },
      "cpu_cores": {
        "type": "number",
        "min": 8,
        "unit": "核",
        "comparison": ">="
      }
    }
  },
  "evidence_chunk_ids": ["CHUNK_005"]
}
```

**说明**: 
- 硬性要求（技术参数不达标则废标）
- 有数值约束（最小值）
- 不允许偏离

---

## 样例 6: 技术要求 - 内存容量（硬性阈值）

```json
{
  "requirement_id": "tech_002",
  "dimension": "technical",
  "req_type": "threshold",
  "requirement_text": "内存容量不低于32GB，须采用DDR4或更高规格。",
  "is_hard": true,
  "allow_deviation": false,
  "value_schema_json": {
    "type": "number",
    "min": 32,
    "unit": "GB",
    "comparison": ">="
  },
  "evidence_chunk_ids": ["CHUNK_006"]
}
```

**说明**: 
- 硬性要求
- 有数值约束
- 不允许偏离

---

## 样例 7: 技术要求 - 质量标准（硬性）

```json
{
  "requirement_id": "tech_003",
  "dimension": "technical",
  "req_type": "must_not_deviate",
  "requirement_text": "产品质量须符合GB/T 19001-2016标准，投标人不得对此条款提出实质性偏离。",
  "is_hard": true,
  "allow_deviation": false,
  "value_schema_json": null,
  "evidence_chunk_ids": ["CHUNK_007"]
}
```

**说明**: 
- 硬性要求（质量标准不符则废标）
- 明确不得偏离
- 无值约束

---

## 样例 8: 技术要求 - 技术方案评分（软性）

```json
{
  "requirement_id": "tech_004",
  "dimension": "technical",
  "req_type": "scoring",
  "requirement_text": "技术方案评分（满分30分）：方案完整性（10分）、创新性（10分）、可行性（10分），由评审专家打分。",
  "is_hard": false,
  "allow_deviation": false,
  "value_schema_json": {
    "type": "object",
    "max_score": 30,
    "sub_items": [
      {"name": "完整性", "max_score": 10},
      {"name": "创新性", "max_score": 10},
      {"name": "可行性", "max_score": 10}
    ]
  },
  "evidence_chunk_ids": ["CHUNK_008"]
}
```

**说明**: 
- 软性要求（评分项）
- 有评分细则
- 专家主观打分

---

## 样例 9: 商务要求 - 付款方式（硬性不得偏离）

```json
{
  "requirement_id": "biz_001",
  "dimension": "business",
  "req_type": "must_not_deviate",
  "requirement_text": "付款方式：合同签订后预付30%，设备到货验收合格后支付60%，质保期满后支付尾款10%。投标人不得对此条款提出实质性偏离。",
  "is_hard": true,
  "allow_deviation": false,
  "value_schema_json": {
    "type": "object",
    "payment_schedule": [
      {"stage": "合同签订", "percentage": 30},
      {"stage": "验收合格", "percentage": 60},
      {"stage": "质保期满", "percentage": 10}
    ]
  },
  "evidence_chunk_ids": ["CHUNK_009"]
}
```

**说明**: 
- 硬性要求（付款方式不得偏离）
- 明确不允许变更
- 有结构化值约束

---

## 样例 10: 商务要求 - 交付期（硬性阈值）

```json
{
  "requirement_id": "biz_002",
  "dimension": "business",
  "req_type": "threshold",
  "requirement_text": "交付期：中标通知书发出之日起60个日历日内完成全部设备交付和安装调试，延期交付每日扣除合同价款的0.5‰作为违约金。",
  "is_hard": true,
  "allow_deviation": false,
  "value_schema_json": {
    "type": "number",
    "max": 60,
    "unit": "日历日",
    "comparison": "<=",
    "penalty_rate": 0.0005
  },
  "evidence_chunk_ids": ["CHUNK_010"]
}
```

**说明**: 
- 硬性要求（超期有违约金）
- 有时间上限
- 有违约金条款

---

## 样例 11: 商务要求 - 质保期（硬性）

```json
{
  "requirement_id": "biz_003",
  "dimension": "business",
  "req_type": "threshold",
  "requirement_text": "质保期不少于3年，自验收合格之日起计算，质保期内免费维修和更换。",
  "is_hard": true,
  "allow_deviation": false,
  "value_schema_json": {
    "type": "number",
    "min": 3,
    "unit": "年",
    "comparison": ">="
  },
  "evidence_chunk_ids": ["CHUNK_011"]
}
```

**说明**: 
- 硬性要求
- 有最小值约束
- 不允许偏离

---

## 样例 12: 商务要求 - 售后服务评分（软性）

```json
{
  "requirement_id": "biz_004",
  "dimension": "business",
  "req_type": "scoring",
  "requirement_text": "售后服务方案评分（满分10分）：响应时间2小时内到达现场得10分，4小时内得6分，8小时内得3分，超过8小时不得分。",
  "is_hard": false,
  "allow_deviation": false,
  "value_schema_json": {
    "type": "enum",
    "enum": ["2小时内:10分", "4小时内:6分", "8小时内:3分", "超过8小时:0分"],
    "max_score": 10
  },
  "evidence_chunk_ids": ["CHUNK_012"]
}
```

**说明**: 
- 软性要求（评分项）
- 有时间梯度评分
- 不满足不废标

---

## 样例 13: 价格要求 - 控制价（硬性阈值）

```json
{
  "requirement_id": "price_001",
  "dimension": "price",
  "req_type": "threshold",
  "requirement_text": "投标总价不得超过招标控制价197.4万元，超过招标控制价的投标为无效投标。",
  "is_hard": true,
  "allow_deviation": false,
  "value_schema_json": {
    "type": "number",
    "max": 1974000,
    "unit": "元",
    "comparison": "<="
  },
  "evidence_chunk_ids": ["CHUNK_013"]
}
```

**说明**: 
- 硬性要求（超价则废标）
- 有最大值约束
- 不允许偏离

---

## 样例 14: 价格要求 - 价格评分（软性）

```json
{
  "requirement_id": "price_002",
  "dimension": "price",
  "req_type": "scoring",
  "requirement_text": "价格分计算（满分30分）：价格分=（评标基准价/投标报价）×30%×100。评标基准价为所有有效投标报价的算术平均值。",
  "is_hard": false,
  "allow_deviation": false,
  "value_schema_json": {
    "type": "formula",
    "formula": "(评标基准价 / 投标报价) × 0.3 × 100",
    "max_score": 30,
    "base_price_method": "算术平均值"
  },
  "evidence_chunk_ids": ["CHUNK_014"]
}
```

**说明**: 
- 软性要求（评分项）
- 有计算公式
- 价格越低分越高

---

## 样例 15: 文档结构 - 装订要求（硬性格式）

```json
{
  "requirement_id": "doc_001",
  "dimension": "doc_structure",
  "req_type": "format",
  "requirement_text": "投标文件须制作正本1份、副本5份，正本和副本须分别装订成册，封面须标明"正本"或"副本"字样。",
  "is_hard": true,
  "allow_deviation": false,
  "value_schema_json": {
    "type": "object",
    "copies": {
      "original": 1,
      "duplicate": 5
    }
  },
  "evidence_chunk_ids": ["CHUNK_015"]
}
```

**说明**: 
- 硬性要求（格式不符可能废标）
- 有份数要求
- 不允许偏离

---

## 样例 16: 文档结构 - 签章要求（硬性格式）

```json
{
  "requirement_id": "doc_002",
  "dimension": "doc_structure",
  "req_type": "format",
  "requirement_text": "投标文件须由法定代表人或其授权代理人签字并加盖单位公章，否则视为无效投标。",
  "is_hard": true,
  "allow_deviation": false,
  "value_schema_json": null,
  "evidence_chunk_ids": ["CHUNK_016"]
}
```

**说明**: 
- 硬性要求（未签章则废标）
- 格式要求
- 不允许偏离

---

## 样例 17: 进度与质量 - 工期要求（硬性阈值）

```json
{
  "requirement_id": "sched_001",
  "dimension": "schedule_quality",
  "req_type": "threshold",
  "requirement_text": "施工总工期不超过180天，自开工令发出之日起计算。投标人承诺的工期短于招标要求的，应提供相应保障措施。",
  "is_hard": true,
  "allow_deviation": true,
  "value_schema_json": {
    "type": "number",
    "max": 180,
    "unit": "天",
    "comparison": "<=",
    "allow_better": true
  },
  "evidence_chunk_ids": ["CHUNK_017"]
}
```

**说明**: 
- 硬性要求（超期不得分）
- 允许正偏离（工期更短）
- 有时间上限

---

## 样例 18: 进度与质量 - 质量标准（硬性）

```json
{
  "requirement_id": "sched_002",
  "dimension": "schedule_quality",
  "req_type": "must_not_deviate",
  "requirement_text": "工程质量须达到国家验收规范合格标准，关键工序质量须达到优良等级，投标人不得对此条款提出偏离。",
  "is_hard": true,
  "allow_deviation": false,
  "value_schema_json": {
    "type": "enum",
    "enum": ["合格", "优良"],
    "description": "质量等级要求"
  },
  "evidence_chunk_ids": ["CHUNK_018"]
}
```

**说明**: 
- 硬性要求（质量不达标则废标）
- 不允许偏离
- 有等级要求

---

## 样例 19: 评分标准 - 企业信誉（软性）

```json
{
  "requirement_id": "eval_001",
  "dimension": "other",
  "req_type": "scoring",
  "requirement_text": "企业信誉评分（满分5分）：近三年未发生重大质量安全事故得5分，发生一般事故得3分，发生较大及以上事故不得分。",
  "is_hard": false,
  "allow_deviation": false,
  "value_schema_json": {
    "type": "enum",
    "enum": ["无事故:5分", "一般事故:3分", "较大及以上事故:0分"],
    "max_score": 5
  },
  "evidence_chunk_ids": ["CHUNK_019"]
}
```

**说明**: 
- 软性要求（评分项）
- 有事故等级判断
- 不满足不废标

---

## 样例 20: 其他要求 - 投标保证金（硬性）

```json
{
  "requirement_id": "other_001",
  "dimension": "other",
  "req_type": "must_provide",
  "requirement_text": "投标人须在投标截止时间前递交投标保证金0元（本项目不收取投标保证金）。",
  "is_hard": false,
  "allow_deviation": false,
  "value_schema_json": {
    "type": "number",
    "value": 0,
    "unit": "元"
  },
  "evidence_chunk_ids": ["CHUNK_020"]
}
```

**说明**: 
- 本项目免保证金（软性说明）
- 有明确金额（0元）
- 无实质约束

---

## 📊 **样例统计**

| 维度 | 数量 | 占比 |
|------|------|------|
| qualification（资格） | 4 | 20% |
| technical（技术） | 4 | 20% |
| business（商务） | 4 | 20% |
| price（价格） | 2 | 10% |
| doc_structure（文档） | 2 | 10% |
| schedule_quality（进度质量） | 2 | 10% |
| other（其他） | 2 | 10% |

| 要求类型 | 数量 | 占比 |
|---------|------|------|
| threshold（阈值） | 7 | 35% |
| must_provide（必须提供） | 4 | 20% |
| must_not_deviate（不得偏离） | 3 | 15% |
| scoring（评分） | 5 | 25% |
| format（格式） | 2 | 10% |

| is_hard | 数量 | 占比 |
|---------|------|------|
| true（硬性） | 14 | 70% |
| false（软性） | 6 | 30% |

| value_schema_json | 数量 | 占比 |
|-------------------|------|------|
| 有值约束 | 15 | 75% |
| 无值约束 | 5 | 25% |

---

## 🎯 **典型场景覆盖**

### ✅ 硬性要求（is_hard=true）
1. **资格类**: 营业执照、资质证书、项目经理
2. **技术类**: CPU频率、内存容量、质量标准
3. **商务类**: 付款方式、交付期、质保期
4. **价格类**: 招标控制价
5. **文档类**: 装订要求、签章要求
6. **进度质量类**: 工期、质量标准

### ✅ 软性要求（is_hard=false）
1. **评分类**: 企业业绩、技术方案、售后服务
2. **价格评分**: 价格分计算公式
3. **其他评分**: 企业信誉

### ✅ 值约束类型
1. **数值约束**: min/max/comparison
2. **枚举约束**: 资质等级、评分档位
3. **对象约束**: 复合参数、付款计划
4. **公式约束**: 价格分计算

### ✅ 偏离控制
1. **不允许偏离**: 付款方式、质量标准、签章要求
2. **允许正偏离**: 工期（可以更短）

---

## 💡 **使用建议**

### **1. 数据导入测试**
```python
# 批量导入测试数据
import json
import uuid

requirements = [样例1, 样例2, ..., 样例20]

for req in requirements:
    cur.execute("""
        INSERT INTO tender_requirements (
            id, project_id, requirement_id, dimension, req_type,
            requirement_text, is_hard, allow_deviation, 
            value_schema_json, evidence_chunk_ids
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        str(uuid.uuid4()),
        "test_project_001",
        req["requirement_id"],
        req["dimension"],
        req["req_type"],
        req["requirement_text"],
        req["is_hard"],
        req["allow_deviation"],
        json.dumps(req["value_schema_json"]) if req["value_schema_json"] else None,
        req["evidence_chunk_ids"],
    ))
```

### **2. 审核规则测试**
基于这些样例，可以测试：
- 硬性要求不满足 → `fail` 或 `risk`
- 软性要求不满足 → `warning`
- 值约束验证（数值比较、枚举匹配）
- 评分计算（按规则打分）

### **3. 前端展示测试**
- 硬性要求用红色/高亮显示
- 软性要求用黄色/次要样式
- 值约束以结构化方式展示
- 评分规则以表格方式展示

---

**文档生成时间**: 2025-12-26  
**样例来源**: 真实招标场景提炼  
**数据格式**: 符合 tender_requirements 表结构

