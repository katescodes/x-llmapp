# 评分标准提取原文信息修复报告

## 问题描述

用户反馈：评分标准没有提取原文的信息。

## 问题分析

通过排查发现问题根源：

1. **Prompt 要求正确**：`project_info_v2.md` 中 Stage 4 明确要求：
   - 提取 `rule` 字段，用于保存"得分规则（完整复制原文，不要改写或概括）"
   - 提取 `evaluationMethod` 字段，用于保存"评标办法名称"

2. **Schema 定义缺失**：`schemas/project_info_v2.py` 中：
   - `ScoringItem` 类**没有定义 `rule` 字段**
   - `ScoringCriteria` 类**没有定义 `evaluationMethod` 字段**
   - `score` 字段类型为 `float`，无法支持 "5-10分"、"最高10分" 等描述性文本

3. **结果**：LLM 输出的 `rule` 和 `evaluationMethod` 字段被 Pydantic 模型验证时忽略或丢失

## 修复内容

### 1. 更新 ScoringItem Schema

**文件**：`backend/app/works/tender/schemas/project_info_v2.py`

**修改前**：
```python
class ScoringItem(BaseModel):
    """评分项"""
    category: Optional[str] = None
    item: Optional[str] = None
    score: Optional[float] = None
    scoring_method: Optional[str] = None
    evidence_chunk_ids: List[str] = Field(default_factory=list)
```

**修改后**：
```python
class ScoringItem(BaseModel):
    """评分项"""
    category: Optional[str] = None
    item: Optional[str] = None
    score: Optional[str] = None  # 改为str以支持"5-10分"、"最高10分"等描述
    rule: Optional[str] = None  # 得分规则（完整复制原文）
    scoring_method: Optional[str] = None
    evidence_chunk_ids: List[str] = Field(default_factory=list)
```

### 2. 更新 ScoringCriteria Schema

**修改前**：
```python
class ScoringCriteria(BaseModel):
    """评分标准"""
    items: List[ScoringItem] = Field(default_factory=list)
```

**修改后**：
```python
class ScoringCriteria(BaseModel):
    """评分标准"""
    evaluationMethod: Optional[str] = None  # 评标办法名称（如"综合评分法"）
    items: List[ScoringItem] = Field(default_factory=list)
```

### 3. 更新数据库中的 Prompt 模板

已将 `project_info_v2.md` 更新到数据库，版本升级至 v9。

## 验证

```python
from app.works.tender.schemas.project_info_v2 import ScoringItem, ScoringCriteria

# 测试实例化
test_item = ScoringItem(
    category='技术评审',
    item='技术方案',
    score='30分',
    rule='评审专家根据投标人提供的技术方案进行综合评分：方案完整、可行性强、重点突出：25-30分'
)

test_criteria = ScoringCriteria(
    evaluationMethod='综合评分法，满分100分',
    items=[test_item]
)

print(f'Rule: {test_item.rule}')
print(f'EvaluationMethod: {test_criteria.evaluationMethod}')
# 输出：
# Rule: 评审专家根据投标人提供的技术方案进行综合评分：方案完整、可行性强、重点突出：25-30分
# EvaluationMethod: 综合评分法，满分100分
```

## 效果

修复后，评分标准抽取将：

1. ✅ **保留完整的评分规则原文**（在 `rule` 字段中）
2. ✅ **保存评标办法名称**（在 `evaluationMethod` 字段中）
3. ✅ **支持描述性分值**（如 "5-10分"、"最高10分"）
4. ✅ **符合 Prompt 要求**：完整复制原文，不改写或概括

## 建议

用户需要**重新运行项目信息抽取**，以使用更新后的 Schema 重新提取评分标准。

旧的抽取结果中 `rule` 字段为空，是因为使用了旧版 Schema，LLM 输出的 `rule` 字段被丢弃了。

## 修复时间

2025-12-26

## 修复文件

- `backend/app/works/tender/schemas/project_info_v2.py`
- 数据库表 `prompt_templates` (module='project_info', version=9)

