# 招投标自定义规则管理功能

> 用自然语言描述规则，AI自动生成结构化审核规则

## 功能概述

自定义规则管理功能允许用户输入自然语言的规则要求，系统使用AI自动分析并生成结构化的审核规则。生成的规则可以在投标文件审核时选择应用，实现灵活、智能的审核流程。

## 核心特性

### 🤖 AI驱动的规则生成
- 自然语言输入，无需学习复杂语法
- 自动识别规则维度（资格/技术/商务/价格等）
- 智能区分确定性规则和语义规则
- 自动标记硬性要求（废标项）

### 📦 规则包管理
- 按场景组织规则（如"资格要求"、"技术规格"）
- 支持创建、查看、删除操作
- 项目级隔离，互不干扰
- 完整的规则详情展示

### ⚙️ 灵活的审核应用
- 支持选择一个或多个规则包
- 与规则文件资产并行使用
- 实时预览规则数量
- 无缝集成审核流程

## 快速开始

### 1. 创建规则包

```
入口：招投标工作台 → 左侧"自定义规则"按钮
```

输入规则要求（示例）：
```
1. 投标人必须具有有效的营业执照，且注册资本不低于500万元
2. 投标人必须提供近三年的财务审计报告
3. 投标报价不得高于预算的110%
```

点击"创建规则包"，系统自动生成规则。

### 2. 应用规则

```
入口：招投标工作台 → ⑤ 审核 Tab
```

1. 勾选要应用的规则包
2. 选择投标人
3. 点击"开始审核"

## 文档导航

| 文档 | 说明 | 适合人群 |
|------|------|----------|
| [快速使用指南](CUSTOM_RULES_QUICK_GUIDE.md) | 步骤说明、常见问题 | 最终用户 |
| [功能说明文档](CUSTOM_RULES_FEATURE.md) | 详细功能介绍、API文档 | 开发者 |
| [实现总结](CUSTOM_RULES_IMPLEMENTATION_SUMMARY.md) | 技术实现、代码统计 | 开发者 |
| [演示指南](CUSTOM_RULES_DEMO_GUIDE.md) | 演示流程、演示脚本 | 产品经理 |
| [文件清单](CUSTOM_RULES_FILE_CHECKLIST.md) | 文件列表、Git提交建议 | 开发者 |

## API接口

### 创建规则包
```http
POST /custom-rules/rule-packs
Content-Type: application/json

{
  "project_id": "项目ID",
  "pack_name": "规则包名称",
  "rule_requirements": "规则要求文本"
}
```

### 列出规则包
```http
GET /custom-rules/rule-packs?project_id={project_id}
```

### 查看规则详情
```http
GET /custom-rules/rule-packs/{pack_id}/rules
```

更多API详见 [功能说明文档](CUSTOM_RULES_FEATURE.md)。

## 技术架构

### 后端
- **路由**: `backend/app/routers/custom_rules.py`
- **服务**: `backend/app/services/custom_rule_service.py`
- **Schema**: `backend/app/schemas/custom_rules.py`

### 前端
- **页面**: `frontend/src/components/CustomRulesPage.tsx`
- **集成**: `frontend/src/components/TenderWorkspace.tsx`

### 数据库
- **规则包**: `tender_rule_packs`
- **规则**: `tender_rules`

## 规则示例

### 输入
```
投标人必须具有有效的营业执照，且注册资本不低于500万元
```

### AI生成的规则
```json
[
  {
    "rule_key": "qual_business_license",
    "rule_name": "营业执照检查",
    "dimension": "qualification",
    "evaluator": "semantic_llm",
    "severity": "high",
    "is_hard": true
  },
  {
    "rule_key": "qual_registered_capital",
    "rule_name": "注册资本检查",
    "dimension": "qualification",
    "evaluator": "deterministic",
    "severity": "high",
    "is_hard": true
  }
]
```

## 测试

### 手动测试
1. 启动后端和前端服务
2. 创建测试项目
3. 按照[快速使用指南](CUSTOM_RULES_QUICK_GUIDE.md)操作

### API测试
```bash
python scripts/test_custom_rules.py
```

## 权限要求

- **创建规则**: `tender:write`
- **查看规则**: `tender:read`
- **删除规则**: `tender:write`

## 依赖

### 后端依赖
- FastAPI
- Pydantic
- PostgreSQL（psycopg）
- LLM（用于规则分析）

### 前端依赖
- React
- TypeScript
- Axios

## 版本历史

### v1.0.0 (当前版本)
- ✅ 规则包CRUD
- ✅ AI规则分析
- ✅ 审核集成（界面）
- ⏳ 规则引擎集成（待实现）

### 未来版本计划
- 规则编辑功能
- 规则测试功能
- 规则模板库
- 规则导入导出
- 规则统计和报告

## 常见问题

**Q: AI分析失败怎么办？**
A: 检查LLM配置，确保模型可用。如果偶尔失败，可以重试。

**Q: 规则包可以共享吗？**
A: 当前版本不支持跨项目共享，未来会添加规则模板库。

**Q: 如何编辑已生成的规则？**
A: 当前版本不支持编辑，需要删除后重新创建。

更多问题见 [快速使用指南](CUSTOM_RULES_QUICK_GUIDE.md) 的常见问题部分。

## 贡献指南

### 代码规范
- 后端遵循PEP 8
- 前端遵循ESLint规则
- 提交前运行linter检查

### Git提交
详见 [文件清单](CUSTOM_RULES_FILE_CHECKLIST.md) 的Git提交建议。

## 许可证

[项目许可证]

## 联系方式

技术支持：[技术支持邮箱]
产品反馈：[产品反馈渠道]

---

**快速链接**
- [使用指南](CUSTOM_RULES_QUICK_GUIDE.md)
- [功能文档](CUSTOM_RULES_FEATURE.md)
- [实现总结](CUSTOM_RULES_IMPLEMENTATION_SUMMARY.md)
- [演示指南](CUSTOM_RULES_DEMO_GUIDE.md)

