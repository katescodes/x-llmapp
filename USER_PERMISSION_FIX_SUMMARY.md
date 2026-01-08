# 用户注册权限问题 - 修复总结

## 🔍 问题描述
用户反馈："用户注册后，应该是没有权限的，需要管理员分配角色后才有权限。目前是新用户注册后拥有管理员权限了"

## 🐛 根本原因分析

经过系统性排查，发现了**核心安全漏洞**：

### 1. **Chat API 完全没有权限检查** ❌
- `/api/chat` 和 `/api/chat/stream` 没有任何身份验证和权限检查
- **任何人（包括未登录用户）都可以访问Chat功能**
- 这是最严重的安全漏洞

### 2. **Recording API 权限检查不完善** ⚠️
- `/api/recordings/upload` 只有身份验证，没有权限检查
- `/api/recordings/{id}/import` 只有身份验证，没有权限检查
- `/api/recordings/{id}/summary` 和 `/api/recordings/{id}/mindmap` 同样问题

### 3. **Tender API 权限检查不完善** ⚠️
- `/api/tender/projects` 创建项目只有身份验证，没有权限检查

### 4. **新用户注册逻辑** ✅（无问题）
- 新用户注册时：
  - `users.role` = "customer"（旧字段，保持兼容性）
  - `user_roles` 表：**没有任何记录**（RBAC系统中无角色）
  - **没有任何权限**（permissions = []）
- 注册逻辑本身是正确的，问题在于API没有进行权限检查

## 🛠️ 修复内容

### 1. Chat API权限检查（`backend/app/routers/chat.py`）

#### 添加导入：
```python
from fastapi import APIRouter, Depends, HTTPException  # 添加Depends
from app.utils.permission import require_permission
from app.models.user import TokenData
```

#### 修复chat endpoint：
```python
# 修复前
@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest) -> ChatResponse:
    ...

# 修复后
@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    req: ChatRequest,
    current_user: TokenData = Depends(require_permission("chat.create"))
) -> ChatResponse:
    ...
```

#### 修复chat stream endpoint：
```python
# 修复前
@router.post("/chat/stream")
async def chat_stream_endpoint(req: ChatRequest):
    ...

# 修复后
@router.post("/chat/stream")
async def chat_stream_endpoint(
    req: ChatRequest,
    current_user: TokenData = Depends(require_permission("chat.create"))
):
    ...
```

### 2. Recording API权限检查（`backend/app/routers/recordings.py`）

#### 添加导入：
```python
from app.utils.permission import require_permission
```

#### 修复各endpoint：
```python
# 1. 上传录音
@router.post("/upload")
async def upload_audio_file(..., current_user: TokenData = Depends(require_permission("recording.create"))):

# 2. 导入到知识库
@router.post("/{recording_id}/import")
async def import_recording(..., current_user: TokenData = Depends(require_permission("recording.import"))):

# 3. 生成摘要
@router.post("/{recording_id}/summary")
async def generate_recording_summary(..., current_user: TokenData = Depends(require_permission("recording.view"))):

# 4. 生成思维导图
@router.post("/{recording_id}/mindmap")
async def generate_recording_mindmap(..., current_user: TokenData = Depends(require_permission("recording.view"))):
```

### 3. Tender API权限检查（`backend/app/routers/tender.py`）

#### 添加导入：
```python
from app.utils.permission import require_permission
```

#### 修复创建项目endpoint：
```python
# 修复前
@router.post("/projects", response_model=ProjectOut)
def create_project(req: ProjectCreateReq, request: Request, user=Depends(get_current_user_sync)):
    ...

# 修复后
@router.post("/projects", response_model=ProjectOut)
def create_project(req: ProjectCreateReq, request: Request, user=Depends(require_permission("tender.create"))):
    ...
```

## ✅ 验证测试

### 测试1: 无权限用户（新注册用户）
```bash
# 注册新用户
POST /api/auth/register {"username": "testuser", "password": "test123456", "role": "customer"}
✅ 成功创建，但RBAC中无角色

# 获取权限
GET /api/permissions/me/permissions
✅ 返回：{"roles": [], "permissions": [], "data_scope": "self"}

# 尝试访问核心功能
POST /api/chat
❌ 403 Forbidden: "Permission required: chat.create"

POST /api/kb
❌ 403 Forbidden: "Permission required: kb.create"

POST /api/tender/projects
❌ 403 Forbidden: "Permission required: tender.create"

POST /api/recordings/upload
❌ 403 Forbidden: "Permission required: recording.create"

GET /api/auth/users
❌ 403 Forbidden: "Permission required: permission.user.view"
```

### 测试2: Admin用户
```bash
# 登录admin
POST /api/auth/login {"username": "admin", "password": "admin123"}

# 访问核心功能
POST /api/chat - ✅ 成功
POST /api/kb - ✅ 成功
GET /api/auth/users - ✅ 成功
```

## 📊 修复效果

| 功能 | 修复前 | 修复后 |
|------|--------|--------|
| Chat创建 | ❌ 无限制访问 | ✅ 需要 `chat.create` 权限 |
| KB创建 | ✅ 已有权限检查 | ✅ 正常 |
| Tender创建 | ⚠️ 只验证身份 | ✅ 需要 `tender.create` 权限 |
| Recording上传 | ⚠️ 只验证身份 | ✅ 需要 `recording.create` 权限 |
| Recording导入 | ⚠️ 只验证身份 | ✅ 需要 `recording.import` 权限 |
| 新用户注册 | ✅ 无RBAC角色 | ✅ 保持无RBAC角色 |

## 🔐 安全改进

### 修复前的安全风险：
1. **任何人都可以调用Chat API**，即使未登录
2. 新注册用户虽然没有RBAC角色，但能通过"无权限检查的API"使用核心功能
3. 前端基于`users.role`字段判断权限，但后端API未统一检查RBAC权限

### 修复后的安全保障：
1. ✅ **所有核心API都要求RBAC权限**
2. ✅ 新用户注册后**完全无权限**，无法使用任何功能
3. ✅ 需要管理员手动分配角色后才能使用系统
4. ✅ Admin用户拥有所有权限，正常使用

## 🚀 使用说明

### 管理员为新用户分配权限：

1. **登录管理员账号**（username: `admin`, password: `admin123`）

2. **查看新注册用户**：
```bash
GET /api/auth/users
```

3. **为用户分配角色**（通过前端或API）：
```bash
# 分配employee角色（基础员工权限）
POST /api/permissions/users/{user_id}/roles
{
  "role_ids": ["role_employee"]
}

# 或分配customer角色（客户权限）
POST /api/permissions/users/{user_id}/roles
{
  "role_ids": ["role_customer"]
}
```

4. **验证用户权限**：
```bash
GET /api/permissions/users/{user_id}/all-permissions
```

### 内置角色权限说明：

| 角色 | 权限范围 |
|------|---------|
| `admin` | 所有权限（系统管理、用户管理、所有功能） |
| `manager` | 部门经理权限（除系统设置和权限管理外的所有功能） |
| `employee` | 员工权限（chat, kb.view, kb.upload, tender, declare, recording） |
| `customer` | 客户权限（chat.create, chat.view, kb.view, recording.create, recording.view） |

---

**修复完成时间**：2026-01-08  
**测试状态**：✅ 通过  
**部署状态**：✅ 已部署

**关键改进**：从"API无权限检查"到"严格的RBAC权限控制"，彻底解决了安全漏洞。
