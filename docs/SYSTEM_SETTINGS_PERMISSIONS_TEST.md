# 系统设置权限控制测试指南

## 测试目的
验证系统设置模块的权限控制是否正确实施，确保只有拥有相应权限的用户才能访问系统设置功能。

## 测试环境准备

### 1. 执行数据库迁移
```bash
cd /aidata/x-llmapp1/backend/migrations
chmod +x run_rbac_migration.sh
./run_rbac_migration.sh
```

### 2. 创建测试用户
使用以下脚本创建不同角色的测试用户：

```bash
cd /aidata/x-llmapp1/backend
python scripts/create_admin.py
```

或者通过API创建：
```bash
# 创建管理员用户（需要已有管理员权限）
curl -X POST http://localhost:8000/api/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -d '{
    "username": "test_admin",
    "password": "admin123",
    "role": "admin"
  }'

# 创建普通员工用户
curl -X POST http://localhost:8000/api/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -d '{
    "username": "test_employee",
    "password": "employee123",
    "role": "employee"
  }'
```

## 测试用例

### 测试用例 1: 管理员访问系统设置

#### 前端测试
1. 使用管理员账号登录
2. 点击"⚙️ 系统设置"按钮
3. **预期结果**：
   - ✅ 看到5个Tab: LLM模型、向量模型、应用设置、语音转文本、Prompt管理
   - ✅ 可以切换到任何Tab并查看内容
   - ✅ 可以执行创建、编辑、删除等操作

#### API测试
```bash
# 获取管理员Token
TOKEN=$(curl -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test_admin","password":"admin123"}' | jq -r '.token')

# 测试LLM模型配置访问
curl -X GET http://localhost:8000/api/settings/llm-models \
  -H "Authorization: Bearer $TOKEN"
# 预期：返回200，包含模型列表

# 测试Embedding配置访问
curl -X GET http://localhost:8000/api/settings/embedding-providers \
  -H "Authorization: Bearer $TOKEN"
# 预期：返回200，包含提供商列表

# 测试应用设置访问
curl -X GET http://localhost:8000/api/settings/app \
  -H "Authorization: Bearer $TOKEN"
# 预期：返回200，包含应用设置

# 测试ASR配置访问
curl -X GET http://localhost:8000/api/asr-configs \
  -H "Authorization: Bearer $TOKEN"
# 预期：返回200，包含ASR配置列表

# 测试Prompt管理访问
curl -X GET http://localhost:8000/api/apps/tender/prompts/ \
  -H "Authorization: Bearer $TOKEN"
# 预期：返回200，包含Prompt列表
```

### 测试用例 2: 普通员工访问系统设置

#### 前端测试
1. 使用普通员工账号登录
2. 查看导航栏
3. **预期结果**：
   - ❌ 不显示"⚙️ 系统设置"按钮，或显示但点击后无任何Tab
   - ✅ 可以看到业务功能按钮（对话、知识库等）

#### API测试
```bash
# 获取员工Token
TOKEN=$(curl -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test_employee","password":"employee123"}' | jq -r '.token')

# 测试LLM模型配置访问
curl -X GET http://localhost:8000/api/settings/llm-models \
  -H "Authorization: Bearer $TOKEN"
# 预期：返回403 Forbidden
# 响应示例：{"detail":"Permission 'system.model' required"}

# 测试Embedding配置访问
curl -X GET http://localhost:8000/api/settings/embedding-providers \
  -H "Authorization: Bearer $TOKEN"
# 预期：返回403 Forbidden

# 测试应用设置访问
curl -X GET http://localhost:8000/api/settings/app \
  -H "Authorization: Bearer $TOKEN"
# 预期：返回403 Forbidden

# 测试ASR配置访问
curl -X GET http://localhost:8000/api/asr-configs \
  -H "Authorization: Bearer $TOKEN"
# 预期：返回403 Forbidden

# 测试Prompt管理访问
curl -X GET http://localhost:8000/api/apps/tender/prompts/ \
  -H "Authorization: Bearer $TOKEN"
# 预期：返回403 Forbidden
```

### 测试用例 3: 部门经理访问系统设置

#### 前端测试
1. 使用部门经理账号登录
2. 查看导航栏
3. **预期结果**：
   - ❌ 不显示"⚙️ 系统设置"按钮
   - ✅ 可以看到业务功能按钮
   - ✅ 可以看到本部门的数据

#### API测试
```bash
# 获取经理Token
TOKEN=$(curl -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test_manager","password":"manager123"}' | jq -r '.token')

# 测试系统设置访问（应该全部失败）
curl -X GET http://localhost:8000/api/settings/llm-models \
  -H "Authorization: Bearer $TOKEN"
# 预期：返回403 Forbidden
```

### 测试用例 4: 客户访问系统设置

#### API测试
```bash
# 获取客户Token
TOKEN=$(curl -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test_customer","password":"customer123"}' | jq -r '.token')

# 测试系统设置访问（应该全部失败）
curl -X GET http://localhost:8000/api/settings/llm-models \
  -H "Authorization: Bearer $TOKEN"
# 预期：返回403 Forbidden
```

## 测试检查清单

### 后端权限控制
- [ ] 管理员可以访问所有系统设置API
- [ ] 普通员工访问系统设置API返回403
- [ ] 部门经理访问系统设置API返回403
- [ ] 客户访问系统设置API返回403
- [ ] 无Token访问系统设置API返回401

### 前端权限显示
- [ ] 管理员可以看到所有5个系统设置Tab
- [ ] 普通员工看不到系统设置Tab（或Tab列表为空）
- [ ] 部门经理看不到系统设置Tab
- [ ] 客户看不到系统设置Tab

### 功能完整性
- [ ] 管理员可以创建LLM模型配置
- [ ] 管理员可以编辑LLM模型配置
- [ ] 管理员可以删除LLM模型配置
- [ ] 管理员可以测试LLM模型连接
- [ ] 管理员可以设置默认LLM模型
- [ ] Embedding、ASR、Prompt等模块功能类似

## 常见问题排查

### 问题1: 管理员看不到某些Tab
**可能原因**：
- 数据库迁移未执行
- 用户的角色权限未正确分配

**解决方案**：
```bash
# 检查用户权限
curl -X GET http://localhost:8000/api/permissions/users/my/permissions \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"

# 重新执行迁移
cd /aidata/x-llmapp1/backend/migrations
./run_rbac_migration.sh
```

### 问题2: API返回403但应该有权限
**可能原因**：
- JWT Token过期
- 权限未正确分配给角色

**解决方案**：
```bash
# 检查用户角色
curl -X GET http://localhost:8000/api/permissions/users/my/roles \
  -H "Authorization: Bearer YOUR_TOKEN"

# 检查角色权限
curl -X GET http://localhost:8000/api/permissions/roles/{role_id}/permissions \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

### 问题3: 前端显示Tab但API返回403
**可能原因**：
- 前端和后端权限检查不一致
- 前端缓存问题

**解决方案**：
```bash
# 清除浏览器缓存
# 重新登录获取最新权限
# 检查前端hasPermission结果和后端权限是否一致
```

## 自动化测试脚本

创建一个bash脚本来自动执行所有测试：

```bash
#!/bin/bash

echo "开始系统设置权限测试..."

# 测试管理员权限
echo "1. 测试管理员权限..."
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | jq -r '.token')

echo "  - 测试LLM配置访问..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/settings/llm-models)
if [ "$STATUS" -eq 200 ]; then
  echo "    ✅ 管理员可以访问LLM配置"
else
  echo "    ❌ 管理员无法访问LLM配置 (HTTP $STATUS)"
fi

# 测试员工权限
echo "2. 测试普通员工权限..."
EMPLOYEE_TOKEN=$(curl -s -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"employee","password":"employee123"}' | jq -r '.token')

echo "  - 测试LLM配置访问..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $EMPLOYEE_TOKEN" \
  http://localhost:8000/api/settings/llm-models)
if [ "$STATUS" -eq 403 ]; then
  echo "    ✅ 员工无法访问LLM配置（预期）"
else
  echo "    ❌ 员工可以访问LLM配置（不应该） (HTTP $STATUS)"
fi

echo "测试完成！"
```

保存为 `test_system_settings_permissions.sh` 并执行：
```bash
chmod +x test_system_settings_permissions.sh
./test_system_settings_permissions.sh
```

## 测试报告模板

```
# 系统设置权限测试报告

测试日期：YYYY-MM-DD
测试人员：XXX
测试环境：开发/测试/生产

## 测试结果总览
- 通过测试用例：X / Y
- 失败测试用例：X / Y
- 跳过测试用例：X / Y

## 详细测试结果

### 后端权限控制
| 角色 | 模块 | 预期 | 实际 | 状态 |
|------|------|------|------|------|
| 管理员 | LLM配置 | 200 | 200 | ✅ |
| 管理员 | Embedding配置 | 200 | 200 | ✅ |
| 员工 | LLM配置 | 403 | 403 | ✅ |
| 员工 | Embedding配置 | 403 | 403 | ✅ |

### 前端Tab显示
| 角色 | 显示Tab数量 | 预期Tab数量 | 状态 |
|------|------------|------------|------|
| 管理员 | 5 | 5 | ✅ |
| 员工 | 0 | 0 | ✅ |

## 发现的问题
1. 问题描述
2. 问题描述

## 建议和改进
1. 建议内容
2. 建议内容
```

## 总结

通过以上测试，可以全面验证系统设置模块的权限控制是否正确实施。建议在每次权限相关代码修改后都执行完整的测试流程。

