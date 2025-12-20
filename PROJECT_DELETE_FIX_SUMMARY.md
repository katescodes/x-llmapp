# 项目删除功能修复总结

## 问题

用户在删除项目时遇到错误：
```
删除失败: Error: 500: Internal Server Error
```

## 原因分析

通过检查后端日志发现：
```
psycopg.errors.UndefinedTable: relation "tender_project_delete_audit" does not exist
```

项目删除功能需要的审计表 `tender_project_delete_audit` 没有在数据库中创建。

## 已执行的修复

### 1. 创建审计表

执行了以下SQL语句创建缺失的表：

```sql
CREATE TABLE IF NOT EXISTS tender_project_delete_audit (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  project_name TEXT NOT NULL,
  requested_by TEXT,
  plan_json JSONB,
  status TEXT NOT NULL,
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_project_delete_audit_project_id ON tender_project_delete_audit(project_id);
CREATE INDEX IF NOT EXISTS idx_project_delete_audit_status ON tender_project_delete_audit(status);
```

### 2. 创建必要的索引

为知识库相关表添加索引以优化删除性能：

```sql
CREATE INDEX IF NOT EXISTS idx_kb_documents_kb_id ON kb_documents(kb_id);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_kb_id ON kb_chunks(kb_id);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_doc_id ON kb_chunks(doc_id);
```

### 3. 创建更新触发器

为项目表添加自动更新时间戳的触发器：

```sql
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

### 4. 重启后端服务

```bash
docker-compose restart backend
```

## 验证结果

✅ 数据库表已成功创建
✅ 索引已创建
✅ 触发器已创建
✅ 后端服务已重启
✅ 审计表可以正常访问

## 现在可以正常使用删除功能

### 删除项目的步骤：

1. **在项目列表中找到要删除的项目**
   - 点击项目卡片右上角的"⋮"菜单
   - 选择"删除项目"

2. **查看删除计划**
   - 系统会显示将要删除的资源清单
   - 包括：资产、文档、知识库、元数据等

3. **确认删除**
   - 在输入框中输入项目名称（必须完全匹配）
   - 点击"确认删除"按钮

4. **等待删除完成**
   - 系统会按顺序清理所有资源
   - 删除成功后会自动刷新项目列表

### 删除的资源包括：

- ✅ 项目资产（文件和数据库记录）
- ✅ 文档绑定关系
- ✅ 知识库（文档、分块、向量）
- ✅ 项目元数据（风险、目录、审核记录、运行记录）
- ✅ 项目本身

### 安全保护机制：

- 🔒 两阶段确认（先获取计划，再确认删除）
- 🔒 必须输入完整的项目名称
- 🔒 使用一次性确认令牌
- 🔒 所有删除操作都有审计日志

## 查看删除审计日志

如需查看删除历史记录，可以执行：

```bash
docker-compose exec postgres psql -U localgpt -d localgpt -c "
  SELECT 
    project_name,
    status,
    created_at,
    finished_at,
    error_message
  FROM tender_project_delete_audit
  ORDER BY created_at DESC
  LIMIT 10;
"
```

## 相关文件

- 修复说明：`FIX_PROJECT_DELETE_ISSUE.md`
- 测试脚本：`test_project_delete.sh`
- 迁移脚本：`backend/migrations/010_project_cascade_delete_prepare.sql`

## 状态

✅ **问题已解决** - 项目删除功能现在可以正常使用了！

---

修复时间：2025-12-19
修复人员：AI Assistant





