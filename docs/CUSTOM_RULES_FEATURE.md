# 招投标自定义规则管理功能

## 功能概述

为招投标系统添加了自定义规则管理功能，允许用户输入规则要求，系统自动分析并生成结构化规则，用于投标文件审核。

## 功能特性

### 1. 自定义规则创建
- **用户输入**：用户输入规则要求文本（自然语言）
- **AI分析**：系统使用LLM自动分析规则要求，生成结构化规则
- **规则字段**：
  - `rule_key`: 规则唯一标识
  - `rule_name`: 规则名称
  - `dimension`: 适用维度（资格审查/技术规格/商务条款/价格/文档结构/进度质量/其他）
  - `evaluator`: 执行器类型（确定性/LLM语义）
  - `condition_json`: 条件配置
  - `severity`: 严重程度（低/中/高）
  - `is_hard`: 是否硬性要求（废标项）

### 2. 规则包管理
- **创建规则包**：将多条规则组织成规则包
- **查看规则包列表**：显示所有规则包及其规则数量
- **查看规则详情**：查看规则包中的所有规则及其配置
- **删除规则包**：删除不需要的规则包（级联删除所有规则）

### 3. 审核应用
- **选择规则包**：在审核页面可以选择一个或多个自定义规则包
- **叠加应用**：选中的规则包将与系统默认规则一起应用于审核
- **灵活组合**：支持同时选择规则包和规则文件资产

## 文件结构

### 后端文件

```
backend/
├── app/
│   ├── routers/
│   │   └── custom_rules.py          # 自定义规则API路由
│   ├── schemas/
│   │   └── custom_rules.py          # 自定义规则Schema定义
│   └── services/
│       └── custom_rule_service.py   # 自定义规则服务
```

### 前端文件

```
frontend/
└── src/
    └── components/
        ├── CustomRulesPage.tsx      # 自定义规则管理页面
        └── TenderWorkspace.tsx      # 招投标工作台（已更新）
```

### 数据库表

使用现有的表结构（来自 migration 028）：
- `tender_rule_packs`: 规则包表
- `tender_rules`: 规则详情表

## API接口

### 1. 创建规则包
```
POST /custom-rules/rule-packs
```

**请求体：**
```json
{
  "project_id": "项目ID",
  "pack_name": "规则包名称",
  "rule_requirements": "规则要求文本（自然语言）",
  "model_id": "模型ID（可选）"
}
```

**响应：**
```json
{
  "id": "规则包ID",
  "pack_name": "规则包名称",
  "pack_type": "custom",
  "project_id": "项目ID",
  "priority": 10,
  "is_active": true,
  "rule_count": 3,
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 2. 列出规则包
```
GET /custom-rules/rule-packs?project_id={project_id}
```

**响应：** 规则包数组

### 3. 获取规则包详情
```
GET /custom-rules/rule-packs/{pack_id}
```

### 4. 删除规则包
```
DELETE /custom-rules/rule-packs/{pack_id}
```

### 5. 列出规则
```
GET /custom-rules/rule-packs/{pack_id}/rules
```

## 使用流程

### 1. 创建自定义规则

1. 在招投标工作台左侧点击"自定义规则"按钮
2. 点击"+ 创建规则包"
3. 输入规则包名称，例如："特殊资格要求"
4. 输入规则要求，例如：
   ```
   1. 投标人必须具有有效的营业执照，且注册资本不低于500万元
   2. 投标人必须提供近三年的财务审计报告
   3. 投标报价不得高于预算的110%
   ```
5. 点击"创建规则包"
6. 系统自动分析并生成结构化规则

### 2. 查看和管理规则

1. 在规则包列表中选择一个规则包
2. 右侧显示该规则包的所有规则详情
3. 可以查看每条规则的：
   - 规则名称和ID
   - 维度和严重程度
   - 执行器类型
   - 条件配置
4. 可以删除不需要的规则包

### 3. 在审核中应用规则

1. 切换到"⑤ 审核" Tab
2. 在"可选：选择自定义规则包"部分勾选要应用的规则包
3. （可选）同时选择自定义规则文件资产
4. 选择投标人
5. 点击"开始审核"
6. 系统将应用选中的规则包进行审核

## AI规则分析示例

### 输入示例
```
投标人必须具有有效的营业执照，且注册资本不低于500万元
```

### 输出示例
```json
{
  "rules": [
    {
      "rule_key": "qual_business_license",
      "rule_name": "营业执照检查",
      "dimension": "qualification",
      "evaluator": "semantic_llm",
      "condition_json": {
        "type": "must_provide",
        "description": "投标人必须提供有效的营业执照",
        "parameters": {
          "document_type": "营业执照",
          "validity_check": true
        }
      },
      "severity": "high",
      "is_hard": true
    },
    {
      "rule_key": "qual_registered_capital",
      "rule_name": "注册资本检查",
      "dimension": "qualification",
      "evaluator": "deterministic",
      "condition_json": {
        "type": "threshold_check",
        "description": "注册资本不低于500万元",
        "parameters": {
          "field": "registered_capital",
          "operator": ">=",
          "value": 5000000,
          "unit": "元"
        }
      },
      "severity": "high",
      "is_hard": true
    }
  ]
}
```

## 权限要求

- **创建规则包**：需要 `tender:write` 权限
- **查看规则包**：需要 `tender:read` 权限
- **删除规则包**：需要 `tender:write` 权限

## 技术实现

### AI规则分析

使用 `llm_json` 函数调用LLM进行结构化分析：
- 温度设置为 0.2，确保输出稳定
- 使用详细的Prompt指导LLM生成符合Schema的规则
- 自动处理JSON解析和错误容错

### 规则应用（待完善）

当前版本：
- 前端可以选择规则包并传递给后端
- 后端接收规则包ID参数
- 实际规则执行逻辑待后续版本实现

未来版本：
- 使用 `EffectiveRulesetBuilder` 合并系统规则和自定义规则
- 使用 `DeterministicRuleEngine` 和 `SemanticLLMRuleEngine` 执行规则
- 生成详细的审核报告

## 注意事项

1. **规则分析依赖LLM**：
   - 需要配置可用的LLM模型
   - AI分析失败不会阻塞创建流程，只是不生成规则

2. **规则包权限**：
   - 规则包是项目级的
   - 用户只能看到自己有权访问的项目的规则包

3. **规则应用**：
   - 当前版本规则包ID会传递给后端，但实际执行逻辑待实现
   - 建议在V3审核模式中集成规则引擎

## 后续优化建议

1. **规则编辑**：支持手动编辑生成的规则
2. **规则测试**：提供规则测试功能，验证规则是否正确
3. **规则模板**：提供常用规则模板库
4. **规则导入导出**：支持YAML/JSON格式导入导出
5. **规则执行**：完整实现规则引擎集成
6. **规则优先级**：支持自定义规则优先级和覆盖
7. **规则统计**：显示规则命中率等统计信息

