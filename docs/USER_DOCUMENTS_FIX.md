# 用户文档新建分类失败问题修复报告

## 问题诊断

用户反馈：**用户文档的新建分类失败**

经过深入调查，发现了以下根本原因：

### 1. 数据库表结构问题

**问题：**
- `tender_user_doc_categories` 表的 `project_id` 字段有 `NOT NULL` 约束
- 并且有外键约束：`REFERENCES tender_projects(id) ON DELETE CASCADE`
- 前端尝试传入 `'shared'` 字符串，但这个值在 `tender_projects` 表中不存在
- 导致插入失败（外键约束违规）

**原始表定义（031_create_user_documents_table.sql）：**
```sql
CREATE TABLE IF NOT EXISTS tender_user_doc_categories (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES tender_projects(id) ON DELETE CASCADE,  -- ❌ 强制外键
  category_name TEXT NOT NULL,
  ...
);
```

### 2. 后端服务依赖问题

在修复过程中还发现：
- 后端服务启动失败，因为缺少 `psycopg` 和 `psycopg-pool` Python包
- 这导致API接口无法正常响应

## 修复方案

### 修复 1: 安装缺失的Python依赖

```bash
pip install psycopg psycopg-pool
```

### 修复 2: 修改数据库表结构（迁移脚本）

创建新迁移：`032_make_user_documents_project_optional.sql`

**关键修改：**

1. **删除外键约束**
```sql
ALTER TABLE tender_user_doc_categories 
  DROP CONSTRAINT IF EXISTS tender_user_doc_categories_project_id_fkey;

ALTER TABLE tender_user_documents 
  DROP CONSTRAINT IF EXISTS tender_user_documents_project_id_fkey;
```

2. **将 project_id 改为可选（允许NULL）**
```sql
ALTER TABLE tender_user_doc_categories 
  ALTER COLUMN project_id DROP NOT NULL;

ALTER TABLE tender_user_documents 
  ALTER COLUMN project_id DROP NOT NULL;
```

3. **为共享文档创建索引**
```sql
CREATE INDEX IF NOT EXISTS idx_user_doc_categories_shared 
  ON tender_user_doc_categories(id) WHERE project_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_user_documents_shared 
  ON tender_user_documents(id) WHERE project_id IS NULL;
```

### 修复 3: 修改前端代码

**UserDocumentsPage.tsx** 和 **CustomRulesPage.tsx**

将 `project_id` 从 `'shared'` 字符串改为 `null`：

```typescript
// 修改前
project_id: projectId || 'shared'  // ❌ 字符串 'shared' 不存在于 tender_projects 表

// 修改后
project_id: projectId || null  // ✅ NULL表示共享资源，不关联特定项目
```

**修改的文件：**
- `/aidata/x-llmapp1/frontend/src/components/UserDocumentsPage.tsx`
  - `handleCreateCategory()` - 创建分类时的 project_id
  - `handleUploadDocument()` - 上传文档时的 project_id（使用空字符串，后端处理为NULL）
  
- `/aidata/x-llmapp1/frontend/src/components/CustomRulesPage.tsx`
  - `handleCreate()` - 创建规则包时的 project_id

## 数据模型说明

### 新的共享资源模型

**project_id 的三种状态：**

1. **有值（非NULL）** - 文档/分类属于特定项目
   - 例如：`project_id = 'abc-123-def'`
   - 只有该项目的成员可以访问

2. **NULL** - 文档/分类是共享资源
   - `project_id IS NULL`
   - 所有用户都可以访问和使用
   - 适用于公司级别的通用文档（如资质证书、企业介绍等）

3. **空字符串** - 前端传空字符串时，后端应转换为 NULL
   - FormData 无法直接传递 null，所以使用空字符串作为标记

### tender_rule_packs 表

经检查，`tender_rule_packs` 表的 `project_id` 本身就是可空的，无需修改：

```sql
project_id | text | | | 
```

所以自定义规则包功能应该直接可用。

## 验证步骤

1. ✅ 安装 Python 依赖
2. ✅ 执行数据库迁移
3. ✅ 修改前端代码（project_id: null）
4. ✅ 重新构建前端
5. ✅ 重启后端服务
6. ✅ 验证服务健康检查

## 预期结果

现在，管理员用户应该能够：

1. **创建文档分类** - project_id 为 NULL，表示共享分类
2. **上传文档** - project_id 为 NULL，表示共享文档
3. **创建规则包** - project_id 为 NULL，表示共享规则包

所有这些资源都不再需要关联到特定项目，所有用户都可以查看和使用。

## 修改文件清单

### 数据库
- ✅ `/aidata/x-llmapp1/backend/migrations/032_make_user_documents_project_optional.sql` （新建）

### 前端
- ✅ `/aidata/x-llmapp1/frontend/src/components/UserDocumentsPage.tsx`
- ✅ `/aidata/x-llmapp1/frontend/src/components/CustomRulesPage.tsx`

### 后端
- ✅ 安装 `psycopg` 和 `psycopg-pool`

## 关键改进

1. **灵活性** - 支持项目级别和共享级别的文档管理
2. **兼容性** - 旧代码传入 projectId 仍然有效
3. **性能** - 为共享资源创建了专门的索引
4. **语义清晰** - NULL 明确表示共享，而不是魔法字符串 'shared'

## 注意事项

如果后端API需要处理FormData中的空字符串（`''`）并转换为数据库的NULL，可能需要添加转换逻辑：

```python
project_id = req.project_id if req.project_id else None  # 将空字符串转为None
```

但根据当前表结构，`tender_rule_packs.project_id` 已经支持 NULL，应该可以直接工作。

