# 系统设置模块权限控制文档

## 概述

本文档记录系统设置模块的权限控制实现，包括5个主要子模块的权限配置。

## 系统设置模块结构

系统设置模块包含以下5个一级子模块和1个权限管理模块：

### 1. LLM模型配置 (system.model)
- **路由文件**: `backend/app/routers/llm_config.py`
- **功能**: 管理AI大语言模型配置
- **权限要求**: `system.model`

#### API端点

| 端点 | 方法 | 功能 | 权限 |
|------|------|------|------|
| `/api/settings/llm-models` | GET | 获取LLM模型列表 | `system.model` |
| `/api/settings/llm-models` | POST | 创建LLM模型配置 | `system.model` |
| `/api/settings/llm-models/{model_id}` | PUT | 更新LLM模型配置 | `system.model` |
| `/api/settings/llm-models/{model_id}` | DELETE | 删除LLM模型配置 | `system.model` |
| `/api/settings/llm-models/{model_id}/set-default` | POST | 设置默认LLM模型 | `system.model` |
| `/api/settings/llm-models/{model_id}/test` | POST | 测试LLM模型连接 | `system.model` |

### 2. Embedding配置 (system.embedding)
- **路由文件**: `backend/app/routers/embedding_providers.py`
- **功能**: 管理向量嵌入模型配置
- **权限要求**: `system.embedding`

#### API端点

| 端点 | 方法 | 功能 | 权限 |
|------|------|------|------|
| `/api/settings/embedding-providers` | GET | 获取Embedding提供商列表 | `system.embedding` |
| `/api/settings/embedding-providers` | POST | 创建Embedding提供商配置 | `system.embedding` |
| `/api/settings/embedding-providers/{provider_id}` | PUT | 更新Embedding提供商配置 | `system.embedding` |
| `/api/settings/embedding-providers/{provider_id}` | DELETE | 删除Embedding提供商配置 | `system.embedding` |
| `/api/settings/embedding-providers/{provider_id}/set-default` | POST | 设置默认Embedding提供商 | `system.embedding` |
| `/api/settings/embedding-providers/{provider_id}/test` | POST | 测试Embedding提供商连接 | `system.embedding` |

### 3. 应用设置 (system.settings)
- **路由文件**: `backend/app/routers/app_settings.py`
- **功能**: 管理应用系统参数（如Google搜索、检索配置等）
- **权限要求**: `system.settings`

#### API端点

| 端点 | 方法 | 功能 | 权限 |
|------|------|------|------|
| `/api/settings/app` | GET | 获取应用设置 | `system.settings` |
| `/api/settings/app` | PUT | 更新应用设置 | `system.settings` |
| `/api/settings/search/google-key` | PUT | 更新Google搜索凭证 | `system.settings` |
| `/api/settings/search/test` | POST | 测试Google搜索配置 | `system.settings` |

### 4. ASR配置 (system.asr)
- **路由文件**: `backend/app/routers/asr_configs.py`
- **功能**: 管理语音识别服务配置
- **权限要求**: `system.asr`

#### API端点

| 端点 | 方法 | 功能 | 权限 |
|------|------|------|------|
| `/api/asr-configs` | GET | 获取所有ASR配置列表 | `system.asr` |
| `/api/asr-configs/{config_id}` | GET | 获取指定ASR配置详情 | `system.asr` |
| `/api/asr-configs` | POST | 创建新的ASR配置 | `system.asr` |
| `/api/asr-configs/{config_id}` | PATCH | 更新ASR配置 | `system.asr` |
| `/api/asr-configs/{config_id}` | DELETE | 删除ASR配置 | `system.asr` |
| `/api/asr-configs/{config_id}/test` | POST | 测试ASR配置是否可用 | `system.asr` |
| `/api/asr-configs/import/curl` | POST | 从curl命令导入ASR配置 | `system.asr` |

### 5. Prompt管理 (system.prompt)
- **路由文件**: `backend/app/routers/prompts.py`
- **功能**: 管理系统提示词模板（包括版本控制）
- **权限要求**: `system.prompt`

#### API端点

| 端点 | 方法 | 功能 | 权限 |
|------|------|------|------|
| `/api/apps/tender/prompts/modules` | GET | 获取所有模块列表 | `system.prompt` |
| `/api/apps/tender/prompts/` | GET | 获取Prompt列表 | `system.prompt` |
| `/api/apps/tender/prompts/{prompt_id}` | GET | 获取单个Prompt详情 | `system.prompt` |
| `/api/apps/tender/prompts/` | POST | 创建新Prompt模板 | `system.prompt` |
| `/api/apps/tender/prompts/{prompt_id}` | PUT | 更新Prompt模板 | `system.prompt` |
| `/api/apps/tender/prompts/{prompt_id}/history` | GET | 获取Prompt变更历史 | `system.prompt` |
| `/api/apps/tender/prompts/{prompt_id}/history/{version}` | GET | 获取指定版本的Prompt内容 | `system.prompt` |
| `/api/apps/tender/prompts/{prompt_id}` | DELETE | 删除Prompt模板（软删除） | `system.prompt` |

### 6. 权限管理 (permission)
- **路由文件**: `backend/app/routers/permissions.py`
- **功能**: 管理用户、角色和权限
- **子模块**:
  - **用户管理** (`permission.user`): 包含用户CRUD和角色分配
  - **角色管理** (`permission.role`): 包含角色CRUD和权限分配
  - **权限项管理** (`permission.item`): 权限项查看和编辑

详见 [PERMISSION_MANAGEMENT.md](./PERMISSION_MANAGEMENT.md)

## 权限层级结构

```
system (系统设置)
├── system.model (LLM模型配置)
├── system.embedding (Embedding配置)
├── system.settings (应用设置)
├── system.asr (ASR配置)
├── system.prompt (Prompt管理)
├── system.category (分类管理)
└── permission (权限管理)
    ├── permission.user (用户管理)
    │   ├── permission.user.create (创建用户)
    │   ├── permission.user.view (查看用户)
    │   ├── permission.user.edit (编辑用户)
    │   ├── permission.user.delete (删除用户)
    │   └── permission.user.assign_role (分配角色)
    ├── permission.role (角色管理)
    │   ├── permission.role.create (创建角色)
    │   ├── permission.role.view (查看角色)
    │   ├── permission.role.edit (编辑角色)
    │   ├── permission.role.delete (删除角色)
    │   └── permission.role.assign_perm (分配权限)
    └── permission.item (权限项管理)
        ├── permission.item.view (查看权限项)
        └── permission.item.edit (编辑权限项)
```

## 角色权限分配

### 管理员 (admin)
- ✅ 拥有所有系统设置和权限管理功能
- ✅ 可以配置所有模块
- ✅ 可以管理用户、角色和权限

### 部门经理 (manager)
- ❌ 不能访问系统设置模块
- ❌ 不能访问权限管理模块
- ✅ 可以使用业务功能模块

### 普通员工 (employee)
- ❌ 不能访问系统设置模块
- ❌ 不能访问权限管理模块
- ✅ 仅可以使用基本业务功能

### 客户 (customer)
- ❌ 不能访问系统设置模块
- ❌ 不能访问权限管理模块
- ✅ 仅可以使用受限的业务功能

## 前端集成

### 系统设置入口
- **位置**: `frontend/src/components/SystemSettings.tsx`
- **Tab控制**: 使用 `currentTab` 状态管理，包含5个tab：
  - `'llm'`: LLM模型配置
  - `'embedding'`: Embedding配置
  - `'app'`: 应用设置
  - `'asr'`: ASR配置
  - `'prompts'`: Prompt管理

### 权限检查
前端使用 `usePermission` Hook 检查用户权限：

```typescript
const { hasPermission, isAdmin } = usePermission();

// 检查是否有系统设置权限
if (hasPermission('system.model')) {
  // 显示LLM配置tab
}

if (hasPermission('system.prompt')) {
  // 显示Prompt管理tab
}
```

### 权限管理入口
- **位置**: `frontend/src/components/PermissionManagementPage.tsx`
- **访问条件**: 仅管理员可见（`isAdmin`）
- **功能**: 包含用户管理、角色管理、权限项管理三个子页面

## 实施步骤

### 1. 后端权限控制
所有系统设置相关的API端点都已添加 `require_permission` 依赖注入：

```python
from app.utils.permission import require_permission

@router.get("/endpoint")
def endpoint_handler(
    current_user: TokenData = Depends(require_permission("system.model"))
):
    # 只有拥有 system.model 权限的用户才能访问
    pass
```

### 2. 数据库迁移
执行迁移脚本以添加系统设置相关权限项：

```bash
cd /aidata/x-llmapp1/backend/migrations
./run_rbac_migration.sh
```

### 3. 前端权限适配
前端组件需要根据用户权限动态显示/隐藏Tab和功能按钮。

## 测试建议

### 1. 功能权限测试
- 使用管理员账号，验证所有系统设置功能可访问
- 使用普通员工账号，验证系统设置功能不可访问（返回403）

### 2. 角色切换测试
- 创建测试用户，分配不同角色
- 验证不同角色用户看到的菜单和功能不同

### 3. API权限测试
使用不同用户Token调用API：

```bash
# 管理员Token（应成功）
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/settings/llm-models

# 普通员工Token（应返回403）
curl -H "Authorization: Bearer $EMPLOYEE_TOKEN" \
  http://localhost:8000/api/settings/llm-models
```

## 注意事项

1. **权限粒度**: 系统设置模块的权限控制到一级子模块级别，不细分到具体操作（CRUD）
2. **向后兼容**: 对于已存在的系统，需要通过迁移脚本为现有用户分配适当的角色
3. **前端显示**: 前端需要根据权限动态显示Tab，避免用户看到无权访问的功能入口
4. **错误处理**: 后端返回403时，前端应友好提示"无权限访问"

## 相关文档

- [权限管理完整文档](./PERMISSION_MANAGEMENT.md)
- [数据权限状态文档](./DATA_PERMISSION_STATUS.md)
- [快速入门指南](./QUICKSTART_PERMISSIONS.md)

## 更新历史

| 日期 | 更新内容 | 修改人 |
|------|----------|--------|
| 2025-12-28 | 初始版本，添加系统设置模块权限控制 | AI Assistant |

