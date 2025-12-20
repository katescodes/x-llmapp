# 项目删除功能修复说明

## 问题描述

删除项目时出现 500 错误：`删除失败: Error: 500: Internal Server Error`

## 根本原因

后端日志显示错误：
```
psycopg.errors.UndefinedTable: relation "tender_project_delete_audit" does not exist
```

项目删除功能依赖的审计表 `tender_project_delete_audit` 没有在数据库中创建。这是因为迁移脚本 `010_project_cascade_delete_prepare.sql` 没有被执行。

## 解决方案

已执行以下SQL创建缺失的表和索引：

```sql
-- 1. 创建项目删除审计表（记录删除操作）
CREATE TABLE IF NOT EXISTS tender_project_delete_audit (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  project_name TEXT NOT NULL,
  requested_by TEXT,
  plan_json JSONB,
  status TEXT NOT NULL, -- PENDING | RUNNING | SUCCESS | FAILED
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_project_delete_audit_project_id ON tender_project_delete_audit(project_id);
CREATE INDEX IF NOT EXISTS idx_project_delete_audit_status ON tender_project_delete_audit(status);

-- 2. 确保 kb_documents 和 kb_chunks 有必要的索引用于清理
CREATE INDEX IF NOT EXISTS idx_kb_documents_kb_id ON kb_documents(kb_id);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_kb_id ON kb_chunks(kb_id);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_doc_id ON kb_chunks(doc_id);

-- 3. 创建项目更新时间触发器
CREATE OR REPLACE FUNCTION update_tender_projects_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tender_projects_updated_at_trigger
  BEFORE UPDATE ON tender_projects
  FOR EACH ROW
  EXECUTE FUNCTION update_tender_projects_updated_at();
```

## 验证

执行以下命令验证表已创建：
```bash
docker-compose exec postgres psql -U localgpt -d localgpt -c "\d tender_project_delete_audit"
```

## 项目删除功能说明

项目删除采用两阶段确认机制：

### 1. 获取删除计划
- 接口：`GET /api/apps/tender/projects/{project_id}/delete-plan`
- 返回：删除计划，包括将被删除的资源清单和确认令牌

### 2. 执行删除
- 接口：`DELETE /api/apps/tender/projects/{project_id}`
- 需要提供：
  - `confirm_text`: 项目名称（必须完全匹配）
  - `confirm_token`: 从删除计划获取的令牌

### 删除流程

删除操作会按以下顺序清理资源：

1. **资产清理** (AssetResourceCleaner)
   - 删除 `tender_project_assets` 表记录
   - 删除物理文件（storage_path）

2. **文档绑定清理** (DocumentResourceCleaner)
   - 删除 `tender_project_documents` 表记录

3. **知识库清理** (KnowledgeBaseResourceCleaner)
   - 删除向量数据（Milvus）
   - 删除 `kb_chunks` 表记录
   - 删除 `kb_documents` 表记录
   - 删除知识库本身

4. **元数据清理** (MetadataResourceCleaner)
   - 删除 `tender_risks` 表记录
   - 删除 `tender_directory_nodes` 表记录
   - 删除 `tender_review_items` 表记录
   - 删除 `tender_runs` 表记录
   - 删除 `tender_project_info` 表记录

5. **项目记录删除**
   - 删除 `tender_projects` 表记录

### 审计日志

所有删除操作都会记录在 `tender_project_delete_audit` 表中，包括：
- 删除时间
- 项目信息
- 删除计划详情
- 执行状态（RUNNING/SUCCESS/FAILED）
- 错误信息（如果失败）

## 状态

✅ 已修复 - 数据库表已创建，删除功能现在应该可以正常工作。

## 测试建议

1. 创建一个测试项目
2. 上传一些文档
3. 获取删除计划
4. 执行删除操作
5. 验证所有资源已被清理

## 相关文件

- 后端路由：`backend/app/routers/tender.py`
- 服务层：`backend/app/services/tender_service.py`
- 删除编排器：`backend/app/services/project_delete/orchestrator.py`
- 资源清理器：`backend/app/services/project_delete/cleaners.py`
- 迁移脚本：`backend/migrations/010_project_cascade_delete_prepare.sql`
- 前端组件：`frontend/src/components/TenderWorkspace.tsx`




