# 自定义规则管理功能 - 文件清单

## 新创建的文件

### 后端文件 (3个)

1. **`backend/app/routers/custom_rules.py`**
   - 自定义规则管理API路由
   - 包含6个API接口
   - 权限控制集成

2. **`backend/app/schemas/custom_rules.py`**
   - 自定义规则相关的Pydantic Schema
   - CustomRulePackCreateReq（创建请求）
   - CustomRulePackOut（规则包输出）
   - CustomRuleOut（规则输出）

3. **`backend/app/services/custom_rule_service.py`**
   - 自定义规则业务逻辑服务
   - AI规则分析
   - 规则包CRUD操作
   - 有效规则集构建

### 前端文件 (1个)

4. **`frontend/src/components/CustomRulesPage.tsx`**
   - 自定义规则管理页面组件
   - 规则包创建、列表、详情、删除
   - 深色主题UI
   - 响应式布局

### 文档文件 (3个)

5. **`docs/CUSTOM_RULES_FEATURE.md`**
   - 功能说明文档
   - API接口文档
   - 使用流程说明
   - 技术实现细节

6. **`docs/CUSTOM_RULES_IMPLEMENTATION_SUMMARY.md`**
   - 实现总结文档
   - 完成任务清单
   - 技术亮点
   - 待完善功能

7. **`docs/CUSTOM_RULES_QUICK_GUIDE.md`**
   - 快速使用指南
   - 步骤说明
   - 常见问题
   - 技巧建议

### 测试文件 (1个)

8. **`scripts/test_custom_rules.py`**
   - API测试脚本
   - 5个测试用例
   - 可执行文件

### 清单文件 (1个)

9. **`docs/CUSTOM_RULES_FILE_CHECKLIST.md`** (本文件)

**新创建文件总计：9个**

---

## 修改的文件

### 后端文件 (3个)

1. **`backend/app/main.py`**
   - 添加 custom_rules 路由导入
   - 注册 custom_rules.router

2. **`backend/app/schemas/tender.py`**
   - ReviewRunReq 添加 custom_rule_pack_ids 字段
   - 更新文档说明

3. **`backend/app/routers/tender.py`**
   - run_review 接口文档更新
   - 说明规则包参数

### 前端文件 (1个)

4. **`frontend/src/components/TenderWorkspace.tsx`**
   - 导入 CustomRulesPage 组件
   - 添加 viewMode 新值 "customRules"
   - 添加左侧"自定义规则"按钮
   - 添加 selectedRulePackIds 状态管理
   - 添加 rulePacks 状态
   - 添加 loadRulePacks 函数
   - 审核Tab添加规则包选择UI
   - Tab切换时加载规则包
   - runReview 函数传递规则包ID

**修改文件总计：4个**

---

## 文件统计

| 类型 | 新建 | 修改 | 小计 |
|------|------|------|------|
| 后端代码 | 3 | 3 | 6 |
| 前端代码 | 1 | 1 | 2 |
| 文档 | 3 | 0 | 3 |
| 测试脚本 | 1 | 0 | 1 |
| **总计** | **8** | **4** | **12** |

---

## 代码统计

### 后端代码

| 文件 | 行数 | 说明 |
|------|------|------|
| custom_rules.py (router) | ~150 | API路由 |
| custom_rules.py (schema) | ~50 | Schema定义 |
| custom_rule_service.py | ~350 | 业务逻辑服务 |
| **小计** | **~550** | |

### 前端代码

| 文件 | 行数 | 说明 |
|------|------|------|
| CustomRulesPage.tsx | ~470 | 规则管理页面 |
| TenderWorkspace.tsx (修改) | ~150 | 集成代码 |
| **小计** | **~620** | |

### 文档和测试

| 文件 | 行数 | 说明 |
|------|------|------|
| CUSTOM_RULES_FEATURE.md | ~300 | 功能文档 |
| CUSTOM_RULES_IMPLEMENTATION_SUMMARY.md | ~400 | 实现总结 |
| CUSTOM_RULES_QUICK_GUIDE.md | ~200 | 使用指南 |
| test_custom_rules.py | ~200 | 测试脚本 |
| **小计** | **~1100** | |

**总代码量：~2270行**

---

## 依赖关系

### 后端依赖

```
custom_rules.py (router)
  ├── custom_rules.py (schema)
  └── custom_rule_service.py
      ├── llm_client.py (llm_json)
      ├── db/postgres.py (get_pool)
      └── auth/auth.py (权限)
```

### 前端依赖

```
TenderWorkspace.tsx
  └── CustomRulesPage.tsx
      ├── axios (API调用)
      └── config/api.ts (API配置)
```

---

## 数据库表

使用现有表结构，无需新增migration：

1. **`tender_rule_packs`** - 规则包表
2. **`tender_rules`** - 规则详情表

---

## Git提交建议

### Commit 1: 后端实现
```bash
git add backend/app/routers/custom_rules.py
git add backend/app/schemas/custom_rules.py
git add backend/app/services/custom_rule_service.py
git add backend/app/main.py
git commit -m "feat(tender): 添加自定义规则管理API

- 新增自定义规则路由和Schema
- 实现AI规则分析服务
- 支持规则包CRUD操作
- 集成权限控制"
```

### Commit 2: 前端实现
```bash
git add frontend/src/components/CustomRulesPage.tsx
git add frontend/src/components/TenderWorkspace.tsx
git commit -m "feat(tender): 添加自定义规则管理UI

- 新增规则管理页面组件
- 集成到招投标工作台
- 审核页面添加规则包选择
- 支持规则包创建、查看、删除"
```

### Commit 3: 审核集成
```bash
git add backend/app/schemas/tender.py
git add backend/app/routers/tender.py
git commit -m "feat(tender): 审核支持自定义规则包

- 审核Schema添加规则包ID字段
- 前端审核流程传递规则包ID
- 为规则引擎集成预留接口"
```

### Commit 4: 文档和测试
```bash
git add docs/CUSTOM_RULES_*.md
git add scripts/test_custom_rules.py
git commit -m "docs(tender): 添加自定义规则管理文档和测试

- 功能说明文档
- 实现总结文档
- 快速使用指南
- API测试脚本"
```

---

## 部署清单

### 后端部署
- ✅ 无需数据库迁移（使用现有表）
- ✅ 需要重启后端服务
- ✅ 需要配置LLM模型（用于规则分析）

### 前端部署
- ✅ 需要重新构建前端
- ✅ 需要清除浏览器缓存

### 权限配置
- ✅ 确保用户有 `tender:read` 和 `tender:write` 权限

---

## 验证清单

### 后端验证
- [ ] API接口测试（使用 test_custom_rules.py）
- [ ] 权限验证测试
- [ ] AI规则分析测试
- [ ] 规则包CRUD测试

### 前端验证
- [ ] 规则管理页面显示正常
- [ ] 规则包创建功能正常
- [ ] 规则列表和详情显示正常
- [ ] 删除功能正常
- [ ] 审核页面规则包选择正常
- [ ] 项目切换状态保持正常

### 集成验证
- [ ] 创建规则包后可在审核中看到
- [ ] 选择规则包后参数正确传递
- [ ] 多项目规则包隔离正常

---

## 文件路径速查

### 后端
```
backend/app/
├── routers/custom_rules.py
├── schemas/custom_rules.py
├── services/custom_rule_service.py
├── main.py (修改)
├── schemas/tender.py (修改)
└── routers/tender.py (修改)
```

### 前端
```
frontend/src/components/
├── CustomRulesPage.tsx
└── TenderWorkspace.tsx (修改)
```

### 文档
```
docs/
├── CUSTOM_RULES_FEATURE.md
├── CUSTOM_RULES_IMPLEMENTATION_SUMMARY.md
├── CUSTOM_RULES_QUICK_GUIDE.md
└── CUSTOM_RULES_FILE_CHECKLIST.md
```

### 测试
```
scripts/
└── test_custom_rules.py
```

