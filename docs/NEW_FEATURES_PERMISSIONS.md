# 新增功能权限控制配置文档

## 更新日期
2025-12-28

## 概述
本文档记录所有新增功能模块的权限控制配置，确保系统安全性和数据隔离。

## 新增功能模块权限映射

### 1. 用户文档管理 (User Documents)

**模块路径**: `/user-documents`  
**功能描述**: 招投标项目中的用户文档管理，支持文档分类、上传、分析

#### 权限项

| 权限代码 | 权限名称 | 使用场景 | 所属角色 |
|---------|---------|---------|---------|
| `tender.view` | 查看项目 | 查看文档分类、文档列表、文档详情 | employee, manager, admin |
| `tender.userdoc` | 用户文档管理 | 创建/更新/删除分类，上传/更新/删除文档，分析文档 | employee, manager, admin |

#### API端点权限

| 端点 | 方法 | 功能 | 权限要求 |
|------|------|------|---------|
| `/user-documents/categories` | GET | 列出文档分类 | `tender.view` |
| `/user-documents/categories` | POST | 创建文档分类 | `tender.userdoc` |
| `/user-documents/categories/{id}` | GET | 获取分类详情 | `tender.view` |
| `/user-documents/categories/{id}` | PATCH | 更新文档分类 | `tender.userdoc` |
| `/user-documents/categories/{id}` | DELETE | 删除文档分类 | `tender.userdoc` |
| `/user-documents/documents` | GET | 列出文档 | `tender.view` |
| `/user-documents/documents` | POST | 上传文档 | `tender.userdoc` |
| `/user-documents/documents/{id}` | GET | 获取文档详情 | `tender.view` |
| `/user-documents/documents/{id}` | PATCH | 更新文档信息 | `tender.userdoc` |
| `/user-documents/documents/{id}` | DELETE | 删除文档 | `tender.userdoc` |
| `/user-documents/documents/{id}/analyze` | POST | AI分析文档 | `tender.userdoc` |

---

### 2. 格式范本管理 (Format Snippets)

**模块路径**: `/api/apps/tender/format-snippets`  
**功能描述**: 招标文件格式范本的提取、管理和应用

#### 权限项

| 权限代码 | 权限名称 | 使用场景 | 所属角色 |
|---------|---------|---------|---------|
| `tender.edit` | 编辑项目 | 所有格式范本相关操作 | employee, manager, admin |

#### API端点权限

| 端点 | 方法 | 功能 | 权限要求 |
|------|------|------|---------|
| `/api/apps/tender/projects/{id}/extract-format-snippets` | POST | 从文件提取范本 | `tender.edit` |
| `/api/apps/tender/projects/{id}/format-snippets` | GET | 列出项目范本 | `tender.edit` |
| `/api/apps/tender/format-snippets/{id}` | GET | 获取范本详情 | `tender.edit` |
| `/api/apps/tender/outline-nodes/{id}/apply-snippet` | POST | 应用范本到目录节点 | `tender.edit` |
| `/api/apps/tender/format-snippets/{id}` | DELETE | 删除范本 | `tender.edit` |

---

### 3. 模板分析 (Template Analysis)

**模块路径**: `/api/apps/tender/templates`  
**功能描述**: Word模板分析和基于模板的目录渲染

#### 权限项

| 权限代码 | 权限名称 | 使用场景 | 所属角色 |
|---------|---------|---------|---------|
| `tender.edit` | 编辑项目 | 模板上传、分析、渲染 | employee, manager, admin |

#### API端点权限

| 端点 | 方法 | 功能 | 权限要求 |
|------|------|------|---------|
| `/api/apps/tender/templates/upload-and-analyze` | POST | 上传并分析模板 | `tender.edit` |
| `/api/apps/tender/templates/{id}/render-outline` | POST | 基于模板渲染目录 | `tender.edit` |

---

### 4. 格式模板管理 (Format Templates)

**模块路径**: `/api/apps/tender/format-templates`  
**功能描述**: 管理投标文档的格式模板，应用格式样式

#### 权限项

| 权限代码 | 权限名称 | 使用场景 | 所属角色 |
|---------|---------|---------|---------|
| `tender.edit` | 编辑项目 | 格式模板的CRUD和应用 | employee, manager, admin |

#### API端点权限

| 端点 | 方法 | 功能 | 权限要求 |
|------|------|------|---------|
| `/api/apps/tender/format-templates` | GET | 列出格式模板 | `tender.edit` |
| `/api/apps/tender/format-templates` | POST | 创建格式模板 | `tender.edit` |
| `/api/apps/tender/format-templates/{id}` | GET | 获取模板详情 | `tender.edit` |
| `/api/apps/tender/format-templates/{id}` | PUT | 更新格式模板 | `tender.edit` |
| `/api/apps/tender/format-templates/{id}` | DELETE | 删除格式模板 | `tender.edit` |
| `/api/apps/tender/format-templates/{id}/apply` | POST | 应用格式模板 | `tender.edit` |

---

### 5. 文档导出 (Export)

**模块路径**: `/api/apps/tender/projects/{id}/export`  
**功能描述**: 导出招投标项目为Word文档

#### 权限项

| 权限代码 | 权限名称 | 使用场景 | 所属角色 |
|---------|---------|---------|---------|
| `tender.edit` | 编辑项目 | 文档导出操作 | employee, manager, admin |
| `tender.export` | 导出文档 | 专门的导出权限 | employee, manager, admin |

#### API端点权限

| 端点 | 方法 | 功能 | 权限要求 |
|------|------|------|---------|
| `/api/apps/tender/projects/{id}/export/docx` | POST | 导出为Word文档 | `tender.edit` |
| `/api/apps/tender/projects/{id}/export/backfill-summary` | POST | 回填目录摘要 | `tender.edit` |
| `/api/apps/tender/projects/{id}/export/backfill-stats` | GET | 获取回填统计 | `tender.edit` |

---

### 6. 知识库分类管理 (KB Category)

**模块路径**: `/api/kb-categories`  
**功能描述**: 管理知识库的分类体系

#### 权限项

| 权限代码 | 权限名称 | 使用场景 | 所属角色 |
|---------|---------|---------|---------|
| `kb.view` | 查看知识库 | 查看分类列表 | employee, manager, admin |
| `system.category` | 分类管理 | 创建/更新/删除分类（系统管理功能） | admin |

#### API端点权限

| 端点 | 方法 | 功能 | 权限要求 |
|------|------|------|---------|
| `/api/kb-categories` | GET | 列出所有分类 | `kb.view` |
| `/api/kb-categories` | POST | 创建新分类 | `system.category` |
| `/api/kb-categories/{id}` | PUT | 更新分类 | `system.category` |
| `/api/kb-categories/{id}` | DELETE | 删除分类 | `system.category` |

**说明**: 知识库分类属于系统基础数据，只有管理员可以修改，但所有用户都可以查看。

---

## 权限层级结构

```
tender (招投标管理)
├── tender.create (创建项目)
├── tender.view (查看项目)
├── tender.edit (编辑项目) ← 包含格式范本、模板分析、格式模板、文档导出
├── tender.delete (删除项目)
├── tender.export (导出文档)
├── tender.template (模板管理)
└── tender.userdoc (用户文档管理) ← 新增

kb (知识库管理)
├── kb.create (创建知识库)
├── kb.view (查看知识库)
├── kb.edit (编辑知识库)
├── kb.delete (删除知识库)
├── kb.upload (上传文档)
└── kb.share (共享知识库)

system (系统设置)
└── system.category (分类管理) ← 用于知识库分类CRUD
```

## 角色权限分配

### 管理员 (admin)
- ✅ 所有权限
- ✅ 包括所有新增功能权限

### 部门经理 (manager)
- ✅ 所有业务功能（招投标、申报书、知识库、录音）
- ❌ 系统设置和权限管理
- ✅ **新增功能**：
  - ✅ 用户文档管理 (`tender.userdoc`)
  - ✅ 格式范本管理 (`tender.edit`)
  - ✅ 模板分析 (`tender.edit`)
  - ✅ 格式模板 (`tender.edit`)
  - ✅ 文档导出 (`tender.edit`, `tender.export`)
  - ❌ 知识库分类管理（需要`system.category`）

### 普通员工 (employee)
- ✅ 基本业务功能
- ✅ **新增功能**：
  - ✅ 用户文档管理 (`tender.userdoc`)
  - ✅ 格式范本管理 (`tender.edit`)
  - ✅ 模板分析 (`tender.edit`)
  - ✅ 格式模板 (`tender.edit`)
  - ✅ 文档导出 (`tender.edit`, `tender.export`)
  - ❌ 知识库分类管理（需要`system.category`）

### 客户 (customer)
- ✅ 仅查看功能
- ❌ 所有新增功能（不可用）

## 数据库迁移

新增权限已添加到迁移脚本 `030_create_rbac_tables.sql`：

```sql
-- 新增权限项
('perm_tender_userdoc', 'tender.userdoc', '用户文档管理', 
 '管理招投标项目的用户文档', 'tender', 'tender', 'api', 7, TRUE)
```

### 执行迁移

```bash
cd /aidata/x-llmapp1/backend/migrations
cat 030_create_rbac_tables.sql | docker-compose exec -T postgres psql -U localgpt -d localgpt
```

### 验证迁移

```bash
# 检查权限数量
docker-compose exec -T postgres psql -U localgpt -d localgpt -c \
  "SELECT COUNT(*) FROM permissions WHERE code LIKE 'tender%';"

# 检查员工角色是否有新权限
docker-compose exec -T postgres psql -U localgpt -d localgpt -c \
  "SELECT p.code, p.name FROM permissions p 
   JOIN role_permissions rp ON p.id = rp.permission_id 
   JOIN roles r ON rp.role_id = r.id 
   WHERE r.code = 'employee' AND p.code LIKE 'tender%';"
```

## 前端适配

### 权限检查示例

```typescript
import { usePermission } from '@/hooks/usePermission';

function UserDocumentManagement() {
  const { hasPermission } = usePermission();
  
  const canView = hasPermission('tender.view');
  const canEdit = hasPermission('tender.userdoc');
  
  return (
    <div>
      {canView && <DocumentList />}
      {canEdit && <UploadButton />}
    </div>
  );
}
```

### API调用示例

```typescript
// 上传用户文档
const response = await authFetch('/user-documents/documents', {
  method: 'POST',
  body: formData
});

// 如果用户没有 tender.userdoc 权限，会返回 403 Forbidden
if (response.status === 403) {
  showError('您没有权限上传文档');
}
```

## 测试建议

### 1. 权限测试
- [ ] 管理员可以访问所有新增功能
- [ ] 员工可以访问用户文档管理和招投标相关功能
- [ ] 员工不能管理知识库分类
- [ ] 客户无法访问任何新增功能

### 2. 功能测试
- [ ] 用户文档上传、分类、分析功能正常
- [ ] 格式范本提取和应用功能正常
- [ ] 模板分析和渲染功能正常
- [ ] 文档导出功能正常
- [ ] 知识库分类管理功能正常（仅管理员）

### 3. 数据隔离测试
- [ ] 用户只能看到自己项目的文档
- [ ] 管理员可以看到所有项目的文档

## 故障排查

### 问题1: 403 Forbidden错误
**原因**: 用户没有相应权限  
**解决**:
1. 检查用户的角色: `SELECT role FROM users WHERE username='xxx';`
2. 检查角色的权限: `SELECT p.code FROM permissions p JOIN role_permissions rp ON p.id=rp.permission_id WHERE rp.role_id='role_employee';`
3. 如需添加权限，使用权限管理界面或SQL

### 问题2: 新功能看不到
**原因**: 前端权限检查或路由未更新  
**解决**: 检查前端组件是否正确使用`hasPermission`检查

### 问题3: 迁移执行失败
**原因**: 权限ID冲突或约束违反  
**解决**: 检查`ON CONFLICT (id) DO NOTHING`是否正确，手动清理冲突数据

## 相关文档

- [权限管理完整文档](./PERMISSION_MANAGEMENT.md)
- [系统设置权限配置](./SYSTEM_SETTINGS_PERMISSIONS.md)
- [数据权限状态](./DATA_PERMISSION_STATUS.md)
- [权限审计报告](./PERMISSION_AUDIT_REPORT.md)

## 更新历史

| 日期 | 版本 | 更新内容 | 更新人 |
|------|------|----------|--------|
| 2025-12-28 | v1.0 | 初始版本，新增6个功能模块的权限配置 | AI Assistant |

