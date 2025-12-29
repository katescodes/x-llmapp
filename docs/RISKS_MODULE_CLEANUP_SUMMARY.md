# Risks模块清理完成总结

## 清理时间
2025-12-29

## 背景
risks模块是历史设计错误，将"风险识别"和"招标要求提取"混淆。系统实际需要的是结构化的招标要求（requirements），而不是简单的风险列表（risks）。

## 清理范围

### ✅ 1. 后端代码清理

#### 删除的文件
- `backend/app/works/tender/extraction_specs/risks_v2.py`

#### 修改的文件
- `backend/app/works/tender/extract_v2_service.py`
  - 删除 `import build_risks_spec_async`
  - 删除 `extract_risks_v2()` 方法（约70行）
  
- `backend/app/services/tender_service.py`
  - 删除 `extract_risks()` 方法（约118行）
  
- `backend/app/queue/tasks.py`
  - 删除 `async_extract_risks_v2()` 函数（约60行）
  
- `backend/app/services/dao/tender_dao.py`
  - 删除 `replace_risks()` 方法（约25行）

- `backend/app/routers/tender.py`
  - **保留** `POST /projects/{project_id}/extract/risks` 路由
  - 内部已改为调用 `extract_requirements_v1()`

### ✅ 2. 数据库清理

#### 删除的数据
```sql
-- prompt_history: 2条记录
DELETE FROM prompt_history WHERE prompt_id IN (SELECT id FROM prompt_templates WHERE module = 'risks');

-- prompt_templates: 1条记录  
DELETE FROM prompt_templates WHERE module = 'risks';

-- tender_risks表数据: 29条记录
DELETE FROM tender_risks;
```

#### 保留的表结构
- `tender_risks` 表结构保留（以防需要回滚）
- 相关索引保留

### ✅ 3. 前端代码清理

#### 修改的文件
- `frontend/src/components/TenderWorkspace.tsx`
  - `loadRisks()` 重命名为 `loadRiskAnalysis()`
  - `extractRisks()` 重命名为 `extractRequirements()`
  - 更新所有调用点（4处）
  - UI按钮保留，文案不变："招标要求提取"

#### 保留的功能
- 前端UI布局不变
- "Step 2: 招标要求提取"按钮保留
- 轮询逻辑保留（kind='extract_risks'保持不变）

### ✅ 4. 文档更新

#### 新增文档
- `docs/RISKS_MODULE_DEPRECATION.md` - 废弃说明
- `docs/RISKS_MODULE_CLEANUP_SUMMARY.md` - 本文件

#### 修改文档
- `backend/app/works/tender/contracts/tender_contract_v1.yaml`
  - ~~删除 `risks:` 能力定义~~ ❌ **已修正**
  - ✅ 将 `risks:` 重命名为 `requirements:`
  - ✅ 更新schema为完整的requirements定义（6个必需字段 + 7个可选字段）
  - ✅ 添加注释说明risks模块已废弃

### ✅ 5. 清理脚本
- `cleanup_risks.sql` - 初版（有外键错误）
- `cleanup_risks_fixed.sql` - 修复版（已执行）

## API变更

### 保留的API（行为已改变）
```bash
POST /api/apps/tender/projects/{project_id}/extract/risks
```
- **旧行为**：调用risks模块，写入tender_risks表
- **新行为**：调用requirements_v1模块，写入tender_requirements表
- **前端无感知**：UI和调用方式不变

### 推荐使用的API
```bash
# 招标要求提取
POST /api/apps/tender/projects/{project_id}/extract/risks
# 实际调用：extract_requirements_v1()
# 写入表：tender_requirements

# 风险分析（基于requirements聚合）
GET /api/apps/tender/projects/{project_id}/risk-analysis
# 数据来源：tender_requirements
# 返回：must_reject_table + checklist_table
```

## 数据流变化

### 旧流程（已废弃）
```
招标文档 → risks模块 → tender_risks表 → 前端展示
```

### 新流程
```
招标文档 → requirements模块 → tender_requirements表 → risk_analysis聚合 → 前端展示
                              ↓
                          审核流程（ReviewPipelineV3）
```

## 影响范围

### ✅ 不受影响
- **审核流程**：一直使用 `tender_requirements`，不受影响
- **前端UI**：布局和交互保持不变
- **API路径**：`/extract/risks` 保留，行为改变但前端无感知

### ⚠️ 轻微影响
- **后端日志**：日志中会看到 `extract_requirements_v1` 而非 `extract_risks`
- **数据库**：`tender_risks` 表空闲（但保留）

### ❌ 需要注意
- **如果有外部系统直接读取 `tender_risks` 表**：需要改为读取 `tender_requirements`
- **如果有监控/报表依赖risks数据**：需要更新查询

## 测试验证

### 功能测试
1. ✅ 后端服务重启成功
2. 🔄 前端构建重启中
3. ⏳ 待测试：
   - [ ] 创建招投标项目
   - [ ] 上传招标文档
   - [ ] 点击"Step 2: 招标要求提取"
   - [ ] 验证数据写入 `tender_requirements` 表
   - [ ] 验证风险分析页面正常显示
   - [ ] 执行审核流程
   - [ ] 验证审核结果正确

### 回归测试
- [ ] 项目信息抽取（Step 1）
- [ ] 招标要求提取（Step 2）- **重点测试**
- [ ] 目录生成（Step 3）
- [ ] 投标响应抽取（Step 4）
- [ ] 审核执行（Step 5）- **重点测试**

## 回滚方案

如果需要回滚（不推荐）：

### 1. 恢复代码
```bash
git revert <commit_hash>
```

### 2. 恢复数据库
```sql
-- 恢复prompt（需要手动创建内容）
INSERT INTO prompt_templates (id, module, name, version, is_active, prompt_text, created_at)
VALUES ('prompt_risks_v2', 'risks', '招标要求提取', 1, true, '...', now());
```

### 3. 重启服务
```bash
docker-compose restart backend frontend
```

## 统计数据

### 代码删除
- Python代码：约 **273行**
- TypeScript代码：约 **30行** (主要是重命名)
- SQL代码：约 **10行** (清理脚本)

### 数据库清理
- prompt_history：2条
- prompt_templates：1条
- tender_risks：29条
- 总计：32条记录

### 文件变更
- 删除：1个文件
- 修改：6个文件（后端4个 + 前端1个 + contract 1个）
- 新增：3个文档

## 维护者
- 执行人：AI Assistant (Claude Sonnet 4.5)
- 审核人：待定
- 日期：2025-12-29

## 相关链接
- 废弃说明：`docs/RISKS_MODULE_DEPRECATION.md`
- Contract：`backend/app/works/tender/contracts/tender_contract_v1.yaml`
- 审核流程：`backend/app/works/tender/review_pipeline_v3.py`
- Requirements提取：`backend/app/works/tender/extraction_specs/requirements_v1.py`

