# 系统设置模块权限控制实施总结

## 实施日期
2025-12-28

## 概述
本次更新将系统设置模块的一级和二级子模块全面纳入权限管理体系，确保只有拥有相应权限的用户才能访问和配置系统设置。

## 修改的文件清单

### 后端文件

#### 1. 路由文件 - 添加权限检查
| 文件 | 模块 | 权限要求 | 修改内容 |
|------|------|----------|----------|
| `backend/app/routers/llm_config.py` | LLM模型配置 | `system.model` | 为所有端点添加 `require_permission("system.model")` |
| `backend/app/routers/embedding_providers.py` | Embedding配置 | `system.embedding` | 为所有端点添加 `require_permission("system.embedding")` |
| `backend/app/routers/app_settings.py` | 应用设置 | `system.settings` | 为所有端点添加 `require_permission("system.settings")` |
| `backend/app/routers/asr_configs.py` | ASR配置 | `system.asr` | 为所有端点添加 `require_permission("system.asr")` |
| `backend/app/routers/prompts.py` | Prompt管理 | `system.prompt` | 为所有端点添加 `require_permission("system.prompt")` |

#### 2. 数据库迁移文件
| 文件 | 修改内容 |
|------|----------|
| `backend/migrations/030_create_rbac_tables.sql` | 1. 更新系统设置权限项，从3个扩展到6个<br>2. 添加 `system.embedding`, `system.settings`, `system.asr` 权限项<br>3. 调整部门经理默认权限：排除所有 `system.*` 权限 |

### 前端文件

#### 1. 组件文件 - 添加权限检查
| 文件 | 修改内容 |
|------|----------|
| `frontend/src/components/SystemSettings.tsx` | 1. 引入 `usePermission` hook<br>2. 根据用户权限动态显示Tab按钮<br>3. 初始化时选择第一个可访问的Tab |

### 文档文件

| 文件 | 描述 |
|------|------|
| `docs/SYSTEM_SETTINGS_PERMISSIONS.md` | 系统设置模块权限控制详细文档 |
| `docs/SYSTEM_SETTINGS_IMPLEMENTATION_SUMMARY.md` | 本实施总结文档 |

## 权限项定义

### 新增/更新的权限项

```sql
-- 系统设置一级模块
('perm_system', 'system', '系统设置', '系统设置相关功能', 'system', NULL, 'menu', 6, TRUE)

-- 系统设置二级模块
('perm_system_model', 'system.model', 'LLM模型配置', '配置LLM模型参数', 'system', 'system', 'menu', 1, TRUE)
('perm_system_embedding', 'system.embedding', 'Embedding配置', '配置向量嵌入模型', 'system', 'system', 'menu', 2, TRUE)
('perm_system_settings', 'system.settings', '应用设置', '配置应用系统参数', 'system', 'system', 'menu', 3, TRUE)
('perm_system_asr', 'system.asr', 'ASR配置', '配置语音识别服务', 'system', 'system', 'menu', 4, TRUE)
('perm_system_prompt', 'system.prompt', 'Prompt管理', '管理系统提示词模板', 'system', 'system', 'menu', 5, TRUE)
('perm_system_category', 'system.category', '分类管理', '管理知识库分类', 'system', 'system', 'menu', 6, TRUE)
```

## 角色权限分配策略

### 管理员 (admin)
- ✅ 拥有所有 `system.*` 权限
- ✅ 可以访问和配置所有系统设置模块

### 部门经理 (manager)
- ❌ 不拥有任何 `system.*` 权限
- ❌ 不能访问系统设置模块
- 说明：系统配置属于管理员专属功能

### 普通员工 (employee)
- ❌ 不拥有任何 `system.*` 权限
- ❌ 不能访问系统设置模块

### 客户 (customer)
- ❌ 不拥有任何 `system.*` 权限
- ❌ 不能访问系统设置模块

## 技术实现细节

### 后端权限控制

#### 依赖注入方式
```python
from app.utils.permission import require_permission

@router.get("/api/settings/llm-models")
def list_models(
    store=Depends(get_llm_store),
    current_user: TokenData = Depends(require_permission("system.model"))
):
    """只有拥有 system.model 权限的用户才能访问"""
    return [_to_out(store, m) for m in store.list_models()]
```

#### 权限检查流程
1. 用户请求到达路由
2. `require_permission` 依赖注入被触发
3. 从JWT Token中提取用户信息
4. 查询数据库获取用户的所有权限
5. 检查是否拥有所需权限
6. 权限不足时返回 HTTP 403 Forbidden

### 前端权限控制

#### Hook使用方式
```typescript
const { hasPermission, isAdmin } = usePermission();

const canAccessLLM = hasPermission('system.model');
const canAccessEmbedding = hasPermission('system.embedding');
const canAccessApp = hasPermission('system.settings');
const canAccessASR = hasPermission('system.asr');
const canAccessPrompts = hasPermission('system.prompt');
```

#### Tab动态渲染
```tsx
{canAccessLLM && (
  <button onClick={() => setCurrentTab('llm')}>
    🤖 LLM模型
  </button>
)}
```

#### 初始Tab选择
```typescript
const getFirstAccessibleTab = () => {
  if (canAccessLLM) return 'llm';
  if (canAccessEmbedding) return 'embedding';
  if (canAccessApp) return 'app';
  if (canAccessASR) return 'asr';
  if (canAccessPrompts) return 'prompts';
  return 'llm'; // 默认
};

const [currentTab, setCurrentTab] = useState(getFirstAccessibleTab());
```

## 测试场景

### 场景1：管理员访问
**预期结果**：
- ✅ 可以看到所有5个Tab
- ✅ 可以切换和访问每个Tab的内容
- ✅ 可以执行所有CRUD操作

### 场景2：普通员工访问
**预期结果**：
- ❌ 看不到任何系统设置Tab
- ❌ 如果通过API直接访问，返回403错误

### 场景3：部门经理访问
**预期结果**：
- ❌ 看不到任何系统设置Tab
- ❌ 如果通过API直接访问，返回403错误

### 场景4：客户访问
**预期结果**：
- ❌ 看不到任何系统设置Tab
- ❌ 如果通过API直接访问，返回403错误

## API端点权限映射

### LLM模型配置 (system.model)
```
GET    /api/settings/llm-models              → 获取模型列表
POST   /api/settings/llm-models              → 创建模型
PUT    /api/settings/llm-models/{id}         → 更新模型
DELETE /api/settings/llm-models/{id}         → 删除模型
POST   /api/settings/llm-models/{id}/set-default → 设置默认
POST   /api/settings/llm-models/{id}/test    → 测试连接
```

### Embedding配置 (system.embedding)
```
GET    /api/settings/embedding-providers              → 获取提供商列表
POST   /api/settings/embedding-providers              → 创建提供商
PUT    /api/settings/embedding-providers/{id}         → 更新提供商
DELETE /api/settings/embedding-providers/{id}         → 删除提供商
POST   /api/settings/embedding-providers/{id}/set-default → 设置默认
POST   /api/settings/embedding-providers/{id}/test    → 测试连接
```

### 应用设置 (system.settings)
```
GET    /api/settings/app                     → 获取应用设置
PUT    /api/settings/app                     → 更新应用设置
PUT    /api/settings/search/google-key       → 更新Google搜索凭证
POST   /api/settings/search/test             → 测试Google搜索
```

### ASR配置 (system.asr)
```
GET    /api/asr-configs                      → 获取ASR配置列表
GET    /api/asr-configs/{id}                 → 获取ASR配置详情
POST   /api/asr-configs                      → 创建ASR配置
PATCH  /api/asr-configs/{id}                 → 更新ASR配置
DELETE /api/asr-configs/{id}                 → 删除ASR配置
POST   /api/asr-configs/{id}/test            → 测试ASR配置
POST   /api/asr-configs/import/curl          → 从curl导入配置
```

### Prompt管理 (system.prompt)
```
GET    /api/apps/tender/prompts/modules      → 获取模块列表
GET    /api/apps/tender/prompts/             → 获取Prompt列表
GET    /api/apps/tender/prompts/{id}         → 获取Prompt详情
POST   /api/apps/tender/prompts/             → 创建Prompt
PUT    /api/apps/tender/prompts/{id}         → 更新Prompt
DELETE /api/apps/tender/prompts/{id}         → 删除Prompt
GET    /api/apps/tender/prompts/{id}/history → 获取变更历史
GET    /api/apps/tender/prompts/{id}/history/{version} → 获取指定版本
```

## 部署步骤

### 1. 执行数据库迁移
```bash
cd /aidata/x-llmapp1/backend/migrations
./run_rbac_migration.sh
```

### 2. 重启后端服务
```bash
cd /aidata/x-llmapp1/backend
# 停止现有服务
# 启动新服务
python -m uvicorn app.main:app --reload
```

### 3. 重新构建前端
```bash
cd /aidata/x-llmapp1/frontend
npm run build
# 或开发模式
npm run dev
```

### 4. 验证权限
```bash
# 使用管理员账号登录，验证可以访问所有Tab
# 使用普通用户登录，验证看不到系统设置Tab
```

## 注意事项

1. **向后兼容**：
   - 现有管理员用户会自动获得所有 `system.*` 权限
   - 现有非管理员用户不会获得任何 `system.*` 权限

2. **前端体验**：
   - 无权限的用户不会看到系统设置的Tab按钮
   - 即使通过URL直接访问，后端API也会拒绝请求（403）

3. **权限粒度**：
   - 当前权限控制到二级模块级别
   - 同一模块内的所有操作（CRUD）共享同一权限代码

4. **测试建议**：
   - 创建测试账号，分配不同角色
   - 验证各个角色的访问权限
   - 测试API的403响应

## 相关文档链接

- [系统设置权限详细文档](./SYSTEM_SETTINGS_PERMISSIONS.md)
- [权限管理完整文档](./PERMISSION_MANAGEMENT.md)
- [数据权限状态文档](./DATA_PERMISSION_STATUS.md)

## 后续工作

1. **前端优化**：
   - 添加权限不足时的友好提示
   - 优化Tab自动选择逻辑

2. **权限细化**（可选）：
   - 如需要，可以将权限进一步细化到具体操作
   - 例如：`system.model.view`, `system.model.create`, `system.model.edit`, `system.model.delete`

3. **审计日志**（可选）：
   - 记录系统设置的修改日志
   - 追踪谁在何时修改了哪些配置

## 更新历史

| 日期 | 版本 | 修改内容 | 修改人 |
|------|------|----------|--------|
| 2025-12-28 | v1.0 | 初始版本，完成系统设置模块权限控制 | AI Assistant |

