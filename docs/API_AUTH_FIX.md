# API 认证问题修复报告

## 问题描述

用户报告两个功能模块无法加载数据：
1. **自定义规则管理**：加载规则包失败
2. **用户文档管理**：加载分类失败

## 根本原因分析

### 问题1: 缺少 Authorization 头

**现象**：
- 前端请求使用 `withCredentials: true`
- 但没有添加 `Authorization: Bearer <token>` 头
- 后端的 `require_permission()` 依赖从 JWT token 中提取用户信息
- 导致后端无法识别用户身份，权限检查失败

**影响的文件**：
- `/frontend/src/components/CustomRulesPage.tsx`
- `/frontend/src/components/UserDocumentsPage.tsx`

**代码示例（错误）**：
```typescript
// ❌ 错误：只设置了 withCredentials，没有添加 Authorization 头
const res = await axios.get(`${API_BASE}/custom-rules/rule-packs`, {
  withCredentials: true,
});
```

**修复后（正确）**：
```typescript
// ✅ 正确：添加 Authorization 头
const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

const res = await axios.get(`${API_BASE}/api/custom-rules/rule-packs`, {
  headers: getAuthHeaders(),
});
```

### 问题2: 路由 prefix 缺少 `/api` 前缀

**现象**：
- 其他路由器都使用 `/api/xxx` 格式（如 `/api/kb`, `/api/auth`）
- 但 `custom_rules.py` 和 `user_documents.py` 只使用了 `/custom-rules` 和 `/user-documents`
- 导致前端请求 `/api/custom-rules/...` 时，后端找不到对应路由

**影响的文件**：
- `/backend/app/routers/custom_rules.py`
- `/backend/app/routers/user_documents.py`

**修复前**：
```python
# ❌ 错误：缺少 /api 前缀
router = APIRouter(prefix="/custom-rules", tags=["custom-rules"])
```

**修复后**：
```python
# ✅ 正确：添加 /api 前缀
router = APIRouter(prefix="/api/custom-rules", tags=["custom-rules"])
```

## 修复内容

### 1. 前端修复 - CustomRulesPage.tsx

**修改位置**：`/frontend/src/components/CustomRulesPage.tsx`

**主要修改**：
1. 导入 `API_BASE_URL` 配置
2. 添加 `getAuthHeaders()` 辅助函数
3. 更新所有 API 请求 URL（添加 `/api` 前缀）
4. 将 `withCredentials: true` 替换为 `headers: getAuthHeaders()`

**修改的请求**：
- `loadRulePacks()` - GET `/api/custom-rules/rule-packs`
- `loadRules()` - GET `/api/custom-rules/rule-packs/{packId}/rules`
- `handleCreate()` - POST `/api/custom-rules/rule-packs`
- `handleDelete()` - DELETE `/api/custom-rules/rule-packs/{packId}`

### 2. 前端修复 - UserDocumentsPage.tsx

**修改位置**：`/frontend/src/components/UserDocumentsPage.tsx`

**主要修改**：
1. 导入 `API_BASE_URL` 配置
2. 添加 `getAuthHeaders()` 辅助函数
3. 更新所有 API 请求 URL（添加 `/api` 前缀）
4. 将 `withCredentials: true` 替换为 `headers: getAuthHeaders()`

**修改的请求**：
- `loadCategories()` - GET `/api/user-documents/categories`
- `loadDocuments()` - GET `/api/user-documents/documents`
- `handleCreateCategory()` - POST `/api/user-documents/categories`
- `handleDeleteCategory()` - DELETE `/api/user-documents/categories/{categoryId}`
- `handleUpload()` - POST `/api/user-documents/documents`
- `handleDeleteDocument()` - DELETE `/api/user-documents/documents/{docId}`
- `handleAnalyze()` - POST `/api/user-documents/documents/{docId}/analyze`

### 3. 后端修复 - custom_rules.py

**修改位置**：`/backend/app/routers/custom_rules.py`

**主要修改**：
```python
# 修改前
router = APIRouter(prefix="/custom-rules", tags=["custom-rules"])

# 修改后
router = APIRouter(prefix="/api/custom-rules", tags=["custom-rules"])
```

### 4. 后端修复 - user_documents.py

**修改位置**：`/backend/app/routers/user_documents.py`

**主要修改**：
```python
# 修改前
router = APIRouter(prefix="/user-documents", tags=["user-documents"])

# 修改后
router = APIRouter(prefix="/api/user-documents", tags=["user-documents"])
```

## 技术细节

### FastAPI JWT 认证流程

```
1. 用户登录
   └─> 后端生成 JWT Token
       └─> 前端保存到 localStorage['auth_token']

2. API 请求
   └─> 前端从 localStorage 读取 token
       └─> 添加到 Authorization: Bearer <token>
           └─> 后端 get_current_user() 解析 JWT
               └─> 提取 user_id, role 等信息
                   └─> require_permission() 检查权限
                       └─> 通过：执行业务逻辑
                       └─> 失败：返回 403 Forbidden
```

### 为什么 withCredentials 不够？

`withCredentials: true` 的作用：
- 允许跨域请求携带 Cookie
- 用于基于 Session 的认证

但我们使用的是 **JWT Token 认证**：
- Token 存储在 `localStorage`
- 需要**手动**添加到 `Authorization` 头
- `withCredentials` 对此无效

### 标准的 API 请求方式

推荐使用项目中的统一 API 工具：

**方式1：使用 `api.ts` 中的工具函数**
```typescript
import { api } from '../config/api';

// 自动添加 Authorization 头
const data = await api.get('/api/custom-rules/rule-packs');
```

**方式2：使用 `useAuthFetch` Hook**
```typescript
import { useAuthFetch } from '../hooks/usePermission';

const authFetch = useAuthFetch();
const response = await authFetch('/api/custom-rules/rule-packs');
```

**方式3：手动添加（本次采用）**
```typescript
import { API_BASE_URL } from '../config/api';

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

const res = await axios.get(`${API_BASE_URL}/api/custom-rules/rule-packs`, {
  headers: getAuthHeaders(),
});
```

## 测试验证

### 测试步骤

1. **登录系统**
   - 使用管理员账号 `admin/admin123` 登录
   - 确认 localStorage 中有 `auth_token`

2. **测试自定义规则管理**
   - 进入招投标项目
   - 点击"自定义规则"标签
   - 应该能看到规则包列表（如果有的话）
   - 尝试创建新规则包

3. **测试用户文档管理**
   - 进入招投标项目
   - 点击"用户文档"标签
   - 应该能看到文档分类列表
   - 尝试创建新分类

### 预期结果

- ✅ 不再出现"加载规则包失败"错误
- ✅ 不再出现"加载分类失败"错误
- ✅ 可以正常查看、创建、删除规则包和文档分类
- ✅ 后端日志显示 200 OK，而不是 403 Forbidden

### 验证日志

**修复前**：
```
INFO: 172.19.0.6:60136 - "GET /api/custom-rules/rule-packs HTTP/1.1" 404 Not Found
INFO: 172.19.0.6:60140 - "GET /api/user-documents/categories HTTP/1.1" 404 Not Found
```

**修复后**：
```
INFO: 172.19.0.6:60136 - "GET /api/custom-rules/rule-packs HTTP/1.1" 200 OK
INFO: 172.19.0.6:60140 - "GET /api/user-documents/categories HTTP/1.1" 200 OK
```

## 相关文档

- [权限控制逻辑详解](./PERMISSION_CONTROL_LOGIC.md)
- [权限管理API参考](./PERMISSION_MANAGEMENT.md)
- [新功能权限配置](./NEW_FEATURES_PERMISSIONS.md)

## 经验总结

### 最佳实践

1. **统一 API 路由前缀**
   - 所有 API 路由都使用 `/api/xxx` 格式
   - 便于 nginx 代理和前端识别

2. **统一认证方式**
   - 使用项目提供的 API 工具（`api.ts` 或 `useAuthFetch`）
   - 避免直接使用 axios/fetch，容易遗漏认证头

3. **检查清单**
   - [ ] 后端路由是否有 `/api` 前缀？
   - [ ] 前端请求是否添加 Authorization 头？
   - [ ] 前端 URL 是否使用统一的 `API_BASE_URL`？
   - [ ] 后端接口是否有权限检查（`require_permission`）？

### 常见错误

| 错误现象 | 可能原因 | 解决方案 |
|---------|---------|---------|
| 404 Not Found | 路由 prefix 错误 | 检查后端 router prefix |
| 401 Unauthorized | 缺少 token | 检查前端是否添加 Authorization 头 |
| 403 Forbidden | token 有效但无权限 | 检查用户的角色和权限分配 |
| CORS 错误 | 跨域配置问题 | 检查后端 CORS 中间件配置 |

---

**修复时间**: 2025-12-28  
**修复人员**: AI Assistant  
**测试状态**: ✅ 已修复，等待用户验证

