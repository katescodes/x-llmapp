# Customer 角色权限过高问题 - 修复总结

## 🔍 问题描述
用户反馈："我用 ztuser1 的用户登录，进去后有全部权限，实际上是客户角色，并没有全部的权限"

## 🐛 根本原因分析

经过检查发现，数据库中 **customer 角色的权限配置错误**：

### 错误配置（修复前）
```
customer 角色拥有 25 个权限：
- chat, chat.create, chat.view, chat.delete, chat.export
- kb, kb.create, kb.view, kb.edit, kb.delete, kb.upload, kb.share
- tender, tender.create, tender.view, tender.edit, tender.delete, tender.export, tender.template, tender.userdoc
- recording, recording.create, recording.view, recording.delete, recording.import
```

**问题**：客户角色拥有了创建、编辑、删除知识库和招投标项目的权限，这明显不符合"客户"角色的定位。

### 正确配置（修复后）
根据 RBAC 迁移脚本 `030_create_rbac_tables.sql`，customer 角色应该只有 **8 个权限**：

```
customer 角色权限（仅查看和基本操作）：
- chat, chat.create, chat.view
- kb, kb.view
- recording, recording.create, recording.view
- recording（模块入口）
```

## 🛠️ 修复操作

### 执行的 SQL 命令：

```sql
-- 1. 删除 customer 角色的所有错误权限
DELETE FROM role_permissions WHERE role_id = 'role_customer';

-- 2. 重新分配正确的权限
INSERT INTO role_permissions (id, role_id, permission_id)
SELECT 
    md5('rp_customer_' || p.id)::uuid,
    'role_customer',
    p.id
FROM permissions p
WHERE p.is_active = TRUE 
    AND p.code IN (
        'chat', 'chat.create', 'chat.view',
        'kb', 'kb.view',
        'recording', 'recording.create', 'recording.view'
    )
ON CONFLICT (role_id, permission_id) DO NOTHING;
```

### 修复结果：
- ✅ 删除了 25 个错误的权限
- ✅ 重新分配了 8 个正确的权限

## ✅ 验证测试

### 测试用户：ztuser1 (customer 角色)

#### 修复后的权限列表：
```
✓ chat                      - 对话管理
✓ chat.create               - 创建对话
✓ chat.view                 - 查看对话
✓ kb                        - 知识库管理
✓ kb.view                   - 查看知识库
✓ recording                 - 录音管理
✓ recording.create          - 创建录音
✓ recording.view            - 查看录音
```

#### 功能测试结果：

| 功能 | 预期 | 实际结果 | 状态 |
|------|------|----------|------|
| Chat 创建 | ✅ 允许 | ✅ 可以访问 | ✅ 正确 |
| Chat 查看 | ✅ 允许 | ✅ 可以访问 | ✅ 正确 |
| KB 查看 | ✅ 允许 | ✅ 可以访问 | ✅ 正确 |
| KB 创建 | ❌ 禁止 | ❌ 403 禁止 | ✅ 正确 |
| KB 编辑 | ❌ 禁止 | ❌ 403 禁止 | ✅ 正确 |
| KB 删除 | ❌ 禁止 | ❌ 403 禁止 | ✅ 正确 |
| Tender 创建 | ❌ 禁止 | ❌ 403 禁止 | ✅ 正确 |
| 用户管理 | ❌ 禁止 | ❌ 403 禁止 | ✅ 正确 |
| Recording 创建 | ✅ 允许 | ✅ 可以访问 | ✅ 正确 |
| Recording 查看 | ✅ 允许 | ✅ 可以访问 | ✅ 正确 |

## 📊 所有角色的权限配置

### 修复后的权限分布：

| 角色 | 权限数量 | 权限范围 | 状态 |
|------|---------|---------|------|
| **customer** | 8 个 | 对话创建/查看、知识库查看、录音创建/查看 | ✅ 正确 |
| **employee** | 31 个 | 基本工作功能（chat、kb、tender、declare、recording） | ✅ 正确 |
| **manager** | 33 个 | 除系统设置和权限管理外的所有功能 | ✅ 正确 |
| **admin** | 54 个 | 所有权限（包括系统管理和用户管理） | ✅ 正确 |

### 各角色的具体权限定位：

#### 1. Customer（客户）
**定位**：仅能进行基本查看和咨询，不能创建或管理资源
- ✅ 可以创建和查看对话（咨询功能）
- ✅ 可以查看知识库内容
- ✅ 可以创建和查看录音
- ❌ 不能创建/编辑/删除知识库
- ❌ 不能创建/编辑招投标项目
- ❌ 不能访问系统管理功能

#### 2. Employee（员工）
**定位**：可以使用基本工作功能，访问自己的数据
- ✅ 对话管理（创建、查看、删除、导出）
- ✅ 知识库查看和上传文档
- ✅ 招投标项目（创建、查看、编辑、删除、导出）
- ✅ 申报书管理
- ✅ 录音管理
- ❌ 不能进行系统设置
- ❌ 不能进行用户管理

#### 3. Manager（经理）
**定位**：部门管理权限，可以管理本部门数据
- ✅ 所有基本功能（employee 的所有权限）
- ✅ 知识库高级功能（创建、编辑、共享）
- ❌ 不能进行权限管理
- ❌ 不能修改系统设置

#### 4. Admin（管理员）
**定位**：系统管理员，拥有所有权限
- ✅ 所有功能权限
- ✅ 用户管理
- ✅ 角色和权限管理
- ✅ 系统设置

## 🔧 可能的原因分析

customer 角色权限配置错误可能是由于：

1. **迁移脚本执行顺序问题**：可能多次执行了某些迁移脚本
2. **手动修改错误**：之前可能有人手动在数据库中分配了错误的权限
3. **测试数据污染**：开发/测试期间的临时权限配置没有清理

## 🚀 后续建议

1. **定期审计角色权限**：
   ```sql
   -- 检查各角色权限数量
   SELECT r.code, r.name, COUNT(rp.permission_id) as permission_count
   FROM roles r
   LEFT JOIN role_permissions rp ON r.id = rp.role_id
   GROUP BY r.code, r.name
   ORDER BY permission_count DESC;
   ```

2. **添加权限配置文档**：在代码仓库中维护一份角色权限清单，便于对照检查

3. **迁移脚本幂等性**：确保所有迁移脚本可以安全地重复执行（使用 `ON CONFLICT DO NOTHING`）

4. **权限变更日志**：考虑在数据库中记录权限变更历史，便于追溯问题

---

**修复完成时间**：2026-01-08  
**影响用户**：所有 customer 角色用户  
**测试状态**：✅ 通过  
**部署状态**：✅ 已部署（直接修改数据库）

**重要提醒**：如果有其他 customer 角色用户登录，需要他们**重新登录**以刷新权限信息。
