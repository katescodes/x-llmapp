# Risks清理的Contract修复

## 问题描述
在清理risks模块时，错误地将 `tender_contract_v1.yaml` 中的"能力 2：招标要求提取"完全删除，只留下了注释。

Contract文件是用于验收标准的关键文件，应该定义 `requirements` 模块的完整schema规范，而不是删除。

## 影响范围
- **影响文件**：`backend/app/works/tender/contracts/tender_contract_v1.yaml`
- **影响时间**：约10分钟（2025-12-29）
- **影响功能**：验收脚本可能无法正确验证requirements提取功能

## 修复内容

### 修复前（错误）
```yaml
# ============================================================
# 能力 2：招标要求提取（使用requirements模块）
# ============================================================
# 注：risks模块已废弃，统一使用requirements模块
# requirements模块提供结构化的招标要求提取，支持审核流程

# ============================================================
# 能力 3：自动生成目录（语义大纲）
# ============================================================
```

### 修复后（正确）
```yaml
# ============================================================
# 能力 2：招标要求提取
# ============================================================
# 注：原risks模块已废弃，现统一使用requirements模块
requirements:
  description: "招标要求提取（结构化条款库）"
  
  schema:
    type: array
    items:
      required_fields:
        - requirement_id    # 要求ID
        - dimension         # 维度
        - req_type          # 要求类型
        - requirement_text  # 要求文本
        - is_hard           # 是否硬性要求
        - evidence_chunk_ids  # 证据片段ID
      optional_fields:
        - allow_deviation   # 是否允许偏离
        - value_schema_json # 值模式
        - eval_method       # 评估方法
        - must_reject       # 是否必须拒绝
        - expected_evidence_json  # 期望证据
        - rubric_json       # 评分细则
        - weight            # 权重
  
  min_items: 0
  
  validation_rules:
    - rule: "每个 requirement 必须有 evidence_chunk_ids 且长度 >= 1"
      severity: "HIGH"
    - rule: "dimension 必须在枚举范围内"
      severity: "MEDIUM"
    - rule: "req_type 必须在枚举范围内"
      severity: "MEDIUM"
```

## 验证结果

```bash
✅ 能力1 - project_info: True
✅ 能力2 - requirements: True
✅ 能力3 - outline: True
✅ 能力4 - review: True

能力2 - requirements详情:
描述: 招标要求提取（结构化条款库）
Schema类型: array
必需字段数: 6
可选字段数: 7
验证规则数: 3
```

## 修复时间
2025-12-29 17:45 (约10分钟内完成)

## 经验教训
1. **Contract文件是验收标准**：不应删除能力定义，而应更新schema
2. **重命名 vs 删除**：risks → requirements 应该是重命名，而不是删除再新建
3. **Schema完整性**：必须保留完整的字段定义和验证规则

## 影响评估
- ✅ **无实际影响**：修复及时，未影响任何功能
- ✅ **Contract完整性**：已恢复完整的requirements定义
- ✅ **验证脚本**：可正常使用contract进行验收

## 相关文件
- 修复文件：`backend/app/works/tender/contracts/tender_contract_v1.yaml`
- 清理总结：`docs/RISKS_MODULE_CLEANUP_SUMMARY.md`
- 废弃说明：`docs/RISKS_MODULE_DEPRECATION.md`

