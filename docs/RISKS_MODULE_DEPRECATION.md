# Risks模块废弃说明

## 废弃时间
2025-12-29

## 废弃原因
risks模块是历史设计错误的产物。最初设计时混淆了"风险识别"和"招标要求提取"两个概念：

1. **risks模块（已废弃）**:
   - 原命名：risks（风险）
   - 实际功能：招标要求提取
   - 数据表：`tender_risks`
   - 字段：`risk_type`, `title`, `severity`, `description`
   - 问题：字段太简单，无法支持审核流程所需的`eval_method`, `is_hard`等字段

2. **requirements_v1模块（正确的）**:
   - 命名：requirements（要求）
   - 功能：招标要求提取
   - 数据表：`tender_requirements`
   - 字段：完整的审核所需字段（`requirement_id`, `dimension`, `req_type`, `is_hard`, `eval_method`等）
   - 用途：审核流程的基础数据源

## 已完成的清理工作

### 1. 后端代码
- ✅ 删除 `backend/app/works/tender/extraction_specs/risks_v2.py`
- ✅ 删除 `ExtractV2Service.extract_risks_v2()` 方法
- ✅ 删除 `TenderService.extract_risks()` 方法
- ✅ 删除 `async_extract_risks_v2()` 异步任务
- ✅ 删除 `TenderDAO.replace_risks()` 方法

### 2. 数据库
- ✅ 删除 `prompt_history` 中risks相关记录（2条）
- ✅ 删除 `prompt_templates` 中risks模块记录（1条）
- ✅ 删除 `tender_risks` 表中所有数据（29条）
- ⚠️ 保留 `tender_risks` 表结构（以防需要回滚）

### 3. 前端代码（待完成）
- ⏳ `TenderWorkspace.tsx` 中的risks相关代码需要清理
- ⏳ 前端UI中"招标要求提取"按钮需要保留（实际调用requirements）

### 4. 文档
- ✅ 更新 `tender_contract_v1.yaml`，移除risks能力定义
- ✅ 创建本废弃说明文档

## API变更

### 删除的API（不再可用）
无。`POST /api/apps/tender/projects/{project_id}/extract/risks` 保留，但内部已改为调用`extract_requirements_v1`。

### 推荐使用的API
```bash
# 招标要求提取（Step 2）
POST /api/apps/tender/projects/{project_id}/extract/risks
# 注：虽然路径还是/risks，但内部已改为调用requirements_v1模块
# 实际写入：tender_requirements表

# 风险分析聚合（基于requirements）
GET /api/apps/tender/projects/{project_id}/risk-analysis
# 从tender_requirements聚合生成风险表和检查清单
```

## 数据迁移指南

如果之前的系统有使用risks模块的数据：

1. **tender_risks表的数据**：已被清空，不需要迁移
2. **前端展示**：改用新的`/risk-analysis` API，基于`tender_requirements`聚合
3. **审核流程**：完全基于`tender_requirements`，无需变更

## 回滚方案

如果需要回滚（不推荐）：

```sql
-- 恢复prompt_templates（需要手动创建prompt内容）
INSERT INTO prompt_templates (id, module, name, version, is_active, prompt_text, created_at)
VALUES ('prompt_risks_v2', 'risks', '招标要求提取', 1, true, '...', now());

-- 恢复后端代码（从git历史恢复）
git checkout <commit_before_deletion> -- backend/app/works/tender/extraction_specs/risks_v2.py
```

## 相关文件
- 本文档：`docs/RISKS_MODULE_DEPRECATION.md`
- Contract：`backend/app/works/tender/contracts/tender_contract_v1.yaml`
- 清理脚本：`cleanup_risks_fixed.sql`

## 联系人
- 负责人：AI Assistant (Claude Sonnet 4.5)
- 日期：2025-12-29

