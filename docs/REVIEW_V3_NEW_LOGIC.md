# 审核V3新逻辑说明

## 修改概要

重新设计了ReviewV3的审核逻辑，支持三种审核模式：

1. **基础要求评估模式**（BASIC_REQUIREMENTS_ONLY）
   - 不需要自定义规则
   - 直接评估 `tender_requirements` vs `tender_bid_responses`
   - 检查每个招标要求是否有对应的投标响应

2. **自定义规则模式**（CUSTOM_RULES）
   - 使用自定义规则包进行审核
   - 同时包含基础要求评估
   - 规则引擎 + 基础评估的组合

3. **混合模式**
   - 自动选择：如果没有传 `custom_rule_pack_ids` 且数据库中有共享规则包，自动加载
   - 如果没有规则包，则回退到基础评估模式

## 核心变更

### 1. 新增 `BasicRequirementEvaluator` 类

文件：`backend/app/works/tender/rules/basic_requirement_evaluator.py`

功能：
- 按维度索引投标响应
- 遍历每个招标要求，检查是否有响应
- 硬性要求无响应 → FAIL
- 非硬性要求无响应 → WARN
- 有响应但过于简短 → WARN
- 正常响应 → PASS

### 2. 修改 `ReviewV3Service.run_review_v3()` 逻辑

#### 原逻辑（有问题）：
```python
# 构建规则集
effective_rules = self.ruleset_builder.build_effective_ruleset(...)
# 如果规则为空 → 0条结果 ❌
```

#### 新逻辑：
```python
# 1. 尝试加载自定义规则包
if not custom_rule_pack_ids:
    # 自动查找共享规则包
    ...

# 2. 根据规则包情况选择模式
if use_custom_rules and custom_rule_pack_ids:
    # 模式A：CUSTOM_RULES
    # - 执行确定性规则引擎
    # - 执行语义LLM规则引擎
    # - 执行基础要求评估
    # - 合并所有结果
    all_results = deterministic_results + semantic_results + basic_results
else:
    # 模式B：BASIC_REQUIREMENTS_ONLY
    # - 只执行基础要求评估
    all_results = basic_results
```

### 3. 修复 `_save_review_items()` 字段映射

#### 原代码（错误）：
```python
INSERT INTO tender_review_items (
    id, project_id, bidder_name, dimension,
    item_type, result, description,  # ❌ 这些字段不存在
    ...
)
```

#### 修复后：
```python
INSERT INTO tender_review_items (
    id, project_id, bidder_name, dimension,
    tender_requirement, bid_response, result, remark,  # ✓ 使用实际字段
    is_hard, rule_id, requirement_id, severity, evaluator
)
```

## 测试结果

### 测试2项目（tp_259c05d1979e402db656a58a930467e2）

**数据：**
- 招标要求：69条
- 投标响应：12条
- 共享规则包：6个，包含7条规则

**审核结果：**
```
模式: CUSTOM_RULES
要求: 69 | 响应: 12
规则: 7 | 结果: 69
PASS: 17 | WARN: 2 | FAIL: 50
```

**分析：**
- 使用了自定义规则 + 基础评估
- 69个招标要求都被评估了
- 17个通过（有响应且符合规则）
- 2个警告（响应不完整或非硬性要求未响应）
- 50个不合格（硬性要求未响应）

**结论：** ✅ 审核成功！即使没有明确选择规则包，系统也自动加载了共享规则包并完成了评估。

## 三种审核模式对比

| 模式 | 触发条件 | 使用场景 | 评估内容 |
|------|----------|----------|----------|
| BASIC_REQUIREMENTS_ONLY | 无自定义规则包 | 简单项目，快速审核 | requirements vs responses 基础匹配 |
| CUSTOM_RULES | 有自定义规则包 | 复杂项目，精细审核 | 规则引擎 + 基础评估 |
| AUTO | 未指定规则包 | 自动选择 | 优先使用共享规则包，否则回退基础评估 |

## API 使用示例

### 1. 基础评估模式（无规则）
```bash
POST /api/apps/tender/projects/{project_id}/review/run
{
  "bidder_name": "123",
  "custom_rule_pack_ids": null  # 或不传
}
```

### 2. 自定义规则模式
```bash
POST /api/apps/tender/projects/{project_id}/review/run
{
  "bidder_name": "123",
  "custom_rule_pack_ids": ["4ff8f82c-d188-4ac1-aaff-a7cf9090da28"]
}
```

### 3. 自动模式（推荐）
```bash
POST /api/apps/tender/projects/{project_id}/review/run
{
  "bidder_name": "123"
  # 不传 custom_rule_pack_ids，系统自动决定
}
```

## 前端UI建议

### 当前UI问题
审核Tab的规则包选择是可选的，但用户可能不理解什么时候需要选择。

### 建议改进

1. **修改规则包选择提示**
   ```
   从"可选：选择自定义规则包（可多选）"
   改为"自定义规则包（可选，不选则使用基础评估）"
   ```

2. **添加模式说明**
   ```tsx
   <div className="kb-doc-meta" style={{backgroundColor: '#eff6ff'}}>
     💡 审核模式说明：
     <ul>
       <li>不选规则包：使用基础要求评估（快速）</li>
       <li>选择规则包：使用自定义规则 + 基础评估（详细）</li>
     </ul>
   </div>
   ```

3. **显示审核模式**
   ```tsx
   {reviewRun?.result && (
     <div>
       审核完成！模式：{reviewRun.result.review_mode === 'CUSTOM_RULES' ? '自定义规则' : '基础评估'}
     </div>
   )}
   ```

## 技术细节

### BasicRequirementEvaluator 算法

```python
for requirement in requirements:
    dimension = requirement.dimension
    responses_in_dimension = filter_by_dimension(responses, dimension)
    
    if len(responses_in_dimension) == 0:
        if requirement.is_hard:
            result = FAIL  # 硬性要求未响应 → 不合格
        else:
            result = WARN  # 非硬性要求未响应 → 警告
    else:
        total_length = sum(len(r.response_text) for r in responses_in_dimension)
        if total_length < 10:
            result = WARN  # 响应过于简短 → 警告
        else:
            result = PASS  # 正常响应 → 通过
```

### 规则引擎与基础评估的关系

```
审核结果 = 规则引擎结果 ∪ 基础评估结果

其中：
- 规则引擎：评估特定的业务规则（如资质要求、技术指标）
- 基础评估：覆盖所有招标要求，确保没有遗漏
```

## 遗留问题

1. **规则包中的 `must_provide` 规则类型**
   - 日志显示：`DeterministicEngine: Unknown rule type 'must_provide'`
   - 需要在 `deterministic_engine.py` 中添加对该规则类型的支持

2. **响应文本填充**
   - 当前 `_save_review_items` 中 `bid_response` 字段为空
   - 可以考虑从 `responses` 中查找对应维度的响应文本

3. **前端UI更新**
   - 需要更新规则包选择的提示文案
   - 添加审核模式的显示
   - 显示评估器类型（basic_requirement_evaluator vs deterministic_engine）

## 文件变更清单

### 新增文件
- `backend/app/works/tender/rules/basic_requirement_evaluator.py`
- `docs/REVIEW_V3_COMPLETE_DIAGNOSIS.md`
- `docs/REVIEW_V3_NEW_LOGIC.md`（本文件）

### 修改文件
- `backend/app/works/tender/review_v3_service.py`
  - 添加 `BasicRequirementEvaluator` 导入和初始化
  - 重写 `run_review_v3()` 逻辑
  - 修复 `_save_review_items()` 字段映射

### 待修改文件
- `frontend/src/components/TenderWorkspace.tsx` - 更新UI提示
- `backend/app/works/tender/rules/deterministic_engine.py` - 添加 `must_provide` 规则支持

