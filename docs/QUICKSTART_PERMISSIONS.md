# 权限管理系统 - 快速启动

## 🚀 快速开始

### 步骤 1: 运行数据库迁移

```bash
cd /aidata/x-llmapp1/backend/migrations

# 方式1: 使用psql（推荐）
psql -h localhost -U postgres -d x_llmapp -f 030_create_rbac_tables.sql

# 方式2: 使用提供的脚本
chmod +x run_rbac_migration.sh
./run_rbac_migration.sh
```

### 步骤 2: 重启后端服务

```bash
cd /aidata/x-llmapp1/backend
# 如果使用systemd
sudo systemctl restart x-llmapp-backend

# 或手动启动
python -m uvicorn app.main:app --reload
```

### 步骤 3: 访问权限管理

1. 打开浏览器访问前端应用
2. 使用管理员账号登录
3. 点击顶部导航栏的 "🔐 权限管理"

## ✅ 验证安装

### 检查数据库表

```sql
-- 检查是否创建成功
SELECT count(*) FROM permissions;  -- 应该有50+条记录
SELECT count(*) FROM roles;        -- 应该有4条记录
SELECT count(*) FROM user_roles;   -- 应该有现有用户数量的记录

-- 查看系统角色
SELECT * FROM roles WHERE is_system = true;

-- 查看权限项（按模块）
SELECT module, count(*) FROM permissions GROUP BY module;
```

### 测试API

```bash
# 获取当前用户权限
curl -X GET "http://localhost:8000/api/permissions/me/permissions" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 获取角色列表
curl -X GET "http://localhost:8000/api/permissions/roles" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 📋 默认账号

如果需要创建初始管理员账号：

```bash
# 通过API注册后，手动更新数据库
psql -d x_llmapp -c "UPDATE users SET role='admin' WHERE username='your_admin_username';"

# 然后为该用户分配admin角色
psql -d x_llmapp -c "
INSERT INTO user_roles (id, user_id, role_id)
SELECT gen_random_uuid()::text, u.id, r.id
FROM users u, roles r
WHERE u.username='your_admin_username' AND r.code='admin'
ON CONFLICT (user_id, role_id) DO NOTHING;
"
```

## 🎯 主要功能

### 用户管理
- ✅ 查看所有用户
- ✅ 为用户分配角色
- ✅ 启用/禁用用户

### 角色管理
- ✅ 创建自定义角色
- ✅ 为角色分配权限
- ✅ 删除角色（非系统角色）

### 权限管理
- ✅ 查看所有权限项
- ✅ 按模块筛选权限
- ✅ 查看权限详情

### 数据权限
- ✅ 自动过滤用户数据
- ✅ 管理员查看所有数据
- ✅ 普通用户仅查看自己的数据

## 🔧 常见问题

### Q: 迁移脚本执行失败？
A: 检查数据库连接配置，确保PostgreSQL服务运行正常。

### Q: 用户看不到权限管理入口？
A: 权限管理入口仅对管理员可见，确认用户角色为 admin。

### Q: 分配角色后权限未生效？
A: 用户需要重新登录，前端会重新获取权限信息。

### Q: 如何重置权限？
A: 重新运行 030_create_rbac_tables.sql 脚本（会删除现有数据）。

## 📚 详细文档

- 完整使用指南：`docs/PERMISSION_MANAGEMENT.md`
- 实施总结：`docs/PERMISSION_IMPLEMENTATION_SUMMARY.md`
- API文档：访问 `http://localhost:8000/docs`

## 🆘 技术支持

如遇问题：
1. 查看日志：`backend/logs/` 或控制台输出
2. 检查数据库：使用上面的SQL验证命令
3. 查阅文档：详细使用说明在 `docs/` 目录

---

**准备就绪！** 🎉 现在您可以开始使用完整的权限管理系统了。

