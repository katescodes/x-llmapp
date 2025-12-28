# 权限控制逻辑详解

## 📋 目录
1. [核心概念](#核心概念)
2. [权限控制流程](#权限控制流程)
3. [后端权限控制](#后端权限控制)
4. [前端权限控制](#前端权限控制)
5. [UI显示控制](#ui显示控制)
6. [数据权限控制](#数据权限控制)
7. [完整示例](#完整示例)

---

## 核心概念

### 1. RBAC (基于角色的访问控制)
系统采用标准的RBAC模型，包含以下核心实体：

```
用户 (users)
  └─ 关联 → 角色 (roles) [多对多: user_roles]
              └─ 关联 → 权限 (permissions) [多对多: role_permissions]

数据权限 (data_permissions)
  └─ 定义用户对特定资源的数据访问范围
```

### 2. 权限代码 (Permission Code)
权限使用层级化的代码表示，格式为 `模块.功能`，例如：
- `system.model` - 系统设置 > LLM模型配置
- `tender.edit` - 招投标 > 编辑权限
- `kb.view` - 知识库 > 查看权限

### 3. 数据范围 (Data Scope)
定义用户可以访问的数据范围：
- `self` - 仅自己创建的数据
- `dept` - 部门内的数据
- `all` - 所有数据（管理员）

---

## 权限控制流程

### 完整流程图

```
┌─────────────┐
│  用户登录    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────┐
│  JWT Token 包含 user_id     │
└──────────┬──────────────────┘
           │
           ▼
    ┌─────────────────┐
    │  发起 API 请求   │
    └─────────┬────────┘
              │
              ▼
    ┌──────────────────────────┐
    │  后端验证 JWT Token      │
    │  解析出 user_id          │
    └──────────┬───────────────┘
               │
               ▼
    ┌──────────────────────────┐
    │  require_permission()    │
    │  检查用户权限            │
    └──────────┬───────────────┘
               │
          YES  │  NO
       ┌───────┴────────┐
       ▼                ▼
┌─────────────┐  ┌──────────────┐
│  执行业务    │  │  403 Forbidden│
│  逻辑        │  └──────────────┘
└──────┬──────┘
       │
       ▼
┌──────────────────────────┐
│  DataFilter 过滤数据     │
│  (根据 data_scope)       │
└──────────┬───────────────┘
           │
           ▼
    ┌──────────────┐
    │  返回结果     │
    └──────────────┘
```

---

## 后端权限控制

### 1. 权限检查依赖 (`require_permission`)

**位置**: `/backend/app/utils/permission.py`

```python
def require_permission(permission_code: str):
    """
    依赖注入：要求特定权限
    用法: current_user: TokenData = Depends(require_permission("chat.create"))
    """
    async def check_permission(current_user: TokenData = Depends(get_current_user)) -> TokenData:
        # 检查用户是否拥有该权限
        if not permission_service.has_permission(current_user.user_id, permission_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission_code}"
            )
        return current_user
    
    return check_permission
```

**工作原理**:
1. 接收一个权限代码作为参数
2. 返回一个FastAPI依赖函数
3. 该依赖函数会：
   - 从JWT Token中获取当前用户信息
   - 查询数据库检查用户是否拥有指定权限
   - 如果有权限，返回用户信息继续执行
   - 如果无权限，抛出403异常

### 2. API端点保护

**示例**: `/backend/app/routers/llm_config.py`

```python
@router.get("/models", response_model=List[LLMModelOut])
async def list_models(
    user: TokenData = Depends(require_permission("system.model")),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100)
):
    """
    获取所有 LLM 模型列表（需要 system.model 权限）
    """
    models = llm_config_service.list_models(skip=skip, limit=limit)
    return models
```

**关键点**:
- `Depends(require_permission("system.model"))` 确保只有拥有 `system.model` 权限的用户才能访问
- 如果用户没有权限，请求会在此处被拦截，返回403错误
- 业务逻辑不会执行

### 3. 权限检查服务

**位置**: `/backend/app/services/permission_service.py`

```python
def has_permission(user_id: str, permission_code: str) -> bool:
    """
    检查用户是否拥有指定权限
    
    流程:
    1. 从 user_roles 表获取用户的角色
    2. 从 role_permissions 表获取角色的权限
    3. 检查权限列表中是否包含目标权限代码
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM user_roles ur
                JOIN role_permissions rp ON ur.role_id = rp.role_id
                JOIN permissions p ON rp.permission_id = p.id
                WHERE ur.user_id = %s 
                  AND p.code = %s 
                  AND p.is_active = TRUE
            """, (user_id, permission_code))
            
            result = cur.fetchone()
            return result[0] > 0 if result else False
```

---

## 前端权限控制

### 1. 权限Hook (`usePermission`)

**位置**: `/frontend/src/hooks/usePermission.ts`

```typescript
export const usePermission = (): PermissionCheck => {
  const { user } = useAuth();
  const [userPermissions, setUserPermissions] = useState<UserPermissions | null>(null);

  // 用户登录后自动加载权限
  useEffect(() => {
    const loadPermissions = async () => {
      if (user) {
        try {
          // 调用 API 获取当前用户的所有权限
          const perms = await userRoleApi.getMyPermissions();
          setUserPermissions(perms);
        } catch (err) {
          console.error('加载用户权限失败:', err);
        }
      }
    };
    loadPermissions();
  }, [user]);

  // 提取权限代码列表
  const permissionCodes = userPermissions?.permissions.map((p) => p.code) || [];

  // 检查是否拥有某个权限
  const hasPermission = useCallback(
    (permissionCode: string): boolean => {
      return permissionCodes.includes(permissionCode);
    },
    [permissionCodes]
  );

  return {
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
    permissions: permissionCodes,
    // ... 其他辅助方法
  };
};
```

**工作原理**:
1. 用户登录后，调用 `/api/permissions/my-permissions` 获取权限列表
2. 权限列表保存在 React state 中
3. 提供 `hasPermission(code)` 方法供组件使用
4. 返回布尔值，指示用户是否拥有某个权限

---

## UI显示控制

### 策略1: 条件渲染 - 隐藏无权限的UI元素

**示例**: `/frontend/src/components/SystemSettings.tsx`

```typescript
const SystemSettings: React.FC = () => {
  const { hasPermission } = usePermission();
  
  // 检查各个模块的权限
  const canAccessLLM = hasPermission('system.model');
  const canAccessEmbedding = hasPermission('system.embedding');
  const canAccessApp = hasPermission('system.settings');
  const canAccessASR = hasPermission('system.asr');
  const canAccessPrompts = hasPermission('system.prompt');

  return (
    <div>
      {/* Tab导航：只显示有权限的标签 */}
      <div style={{ display: "flex", gap: "10px" }}>
        {canAccessLLM && (
          <button onClick={() => setCurrentTab('llm')}>
            🤖 LLM模型
          </button>
        )}
        
        {canAccessEmbedding && (
          <button onClick={() => setCurrentTab('embedding')}>
            🔌 向量模型
          </button>
        )}
        
        {canAccessApp && (
          <button onClick={() => setCurrentTab('app')}>
            📱 应用设置
          </button>
        )}
        
        {canAccessASR && (
          <button onClick={() => setCurrentTab('asr')}>
            🎤 语音转文本
          </button>
        )}
        
        {canAccessPrompts && (
          <button onClick={() => setCurrentTab('prompts')}>
            📝 Prompt管理
          </button>
        )}
      </div>

      {/* 内容区：只渲染有权限的tab */}
      {currentTab === 'llm' && canAccessLLM && (
        <LLMConfigComponent />
      )}
      
      {currentTab === 'embedding' && canAccessEmbedding && (
        <EmbeddingConfigComponent />
      )}
      
      {/* ... 其他tab */}
    </div>
  );
};
```

**效果**:
- ✅ **有权限**: 标签页和内容正常显示
- ❌ **无权限**: 标签页和内容完全不渲染（DOM中不存在）

### 策略2: 禁用状态 - 显示但不可操作

```typescript
const ActionButton: React.FC = () => {
  const { hasPermission } = usePermission();
  const canEdit = hasPermission('tender.edit');

  return (
    <button
      disabled={!canEdit}
      style={{
        opacity: canEdit ? 1 : 0.5,
        cursor: canEdit ? 'pointer' : 'not-allowed',
      }}
      title={!canEdit ? '您没有编辑权限' : ''}
    >
      编辑
    </button>
  );
};
```

**效果**:
- ✅ **有权限**: 按钮正常，可点击
- ⚠️ **无权限**: 按钮显示但禁用，鼠标悬停显示提示

### 策略3: 灰色提示 - 引导用户

```typescript
const FeatureSection: React.FC = () => {
  const { hasPermission } = usePermission();
  const canAccess = hasPermission('feature.access');

  if (!canAccess) {
    return (
      <div style={{
        padding: '20px',
        background: 'rgba(255, 255, 0, 0.1)',
        border: '1px dashed #fbbf24',
        borderRadius: '8px',
        color: '#fbbf24'
      }}>
        ⚠️ 您没有访问此功能的权限，请联系管理员开通。
      </div>
    );
  }

  return <ActualFeatureComponent />;
};
```

**效果**:
- ✅ **有权限**: 显示实际功能
- ⚠️ **无权限**: 显示提示信息，引导用户联系管理员

---

## 数据权限控制

### 1. 数据过滤器 (`DataFilter`)

**位置**: `/backend/app/utils/permission.py`

```python
class DataFilter:
    @staticmethod
    def get_owner_filter(current_user: TokenData, resource_type: str = None) -> dict:
        """
        获取数据所有者过滤条件
        
        返回格式:
        - {"owner_id": user_id}      # 仅查询自己的数据
        - {"all": True}               # 可以查询所有数据
        - {"owner_ids": [id1, id2]}  # 可以查询指定用户的数据
        """
        user_id = current_user.user_id
        
        with get_conn() as conn:
            with conn.cursor() as cur:
                # 1. 检查用户表中的 data_scope
                cur.execute("SELECT data_scope FROM users WHERE id = %s", (user_id,))
                row = cur.fetchone()
                data_scope = row[0] if row and row[0] else "self"
                
                # 2. 如果指定了资源类型，检查数据权限表
                if resource_type:
                    cur.execute("""
                        SELECT data_scope, custom_scope_json
                        FROM data_permissions
                        WHERE user_id = %s AND resource_type = %s
                    """, (user_id, resource_type))
                    
                    dp_row = cur.fetchone()
                    if dp_row:
                        data_scope = dp_row[0]
                        # 处理自定义范围...
                
                # 3. 根据数据范围返回过滤条件
                if data_scope == "all":
                    return {"all": True}
                elif data_scope == "dept":
                    # TODO: 实现部门数据范围
                    return {"owner_id": user_id}
                else:  # self
                    return {"owner_id": user_id}
```

### 2. 应用数据过滤

**示例**: 查询项目列表

```python
@router.get("/projects")
async def list_projects(
    current_user: TokenData = Depends(require_permission("tender.view"))
):
    """
    获取项目列表（自动过滤数据）
    """
    query = "SELECT * FROM projects WHERE 1=1"
    params = []
    
    # 应用数据权限过滤
    query, params = DataFilter.apply_owner_filter(
        query, 
        params, 
        current_user, 
        resource_type="tender"
    )
    
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            projects = cur.fetchall()
    
    return projects
```

**SQL生成示例**:

- **普通用户** (data_scope="self", user_id="user123"):
  ```sql
  SELECT * FROM projects WHERE 1=1 AND owner_id = 'user123'
  ```

- **管理员** (data_scope="all"):
  ```sql
  SELECT * FROM projects WHERE 1=1
  ```

### 3. 资源访问检查

**示例**: 检查是否可以访问特定资源

```python
@router.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    current_user: TokenData = Depends(require_permission("tender.view"))
):
    """
    获取项目详情
    """
    # 1. 查询项目
    project = get_project_from_db(project_id)
    
    if not project:
        raise HTTPException(404, "Project not found")
    
    # 2. 检查数据权限
    if not DataFilter.can_access_resource(
        current_user, 
        project.owner_id, 
        resource_type="tender"
    ):
        raise HTTPException(403, "You don't have permission to access this project")
    
    return project
```

---

## 完整示例

### 场景: 招投标项目管理

#### 1. 数据库权限配置

```sql
-- 权限项
INSERT INTO permissions (id, code, name, module, resource_type)
VALUES 
  ('perm_tender_view', 'tender.view', '查看项目', 'tender', 'menu'),
  ('perm_tender_edit', 'tender.edit', '编辑项目', 'tender', 'button');

-- 角色权限分配
-- 管理员：所有权限 + 所有数据
INSERT INTO role_permissions (role_id, permission_id)
VALUES ('role_admin', 'perm_tender_view'), ('role_admin', 'perm_tender_edit');

UPDATE users SET data_scope = 'all' WHERE id = 'admin_user_id';

-- 部门经理：所有功能权限 + 自己的数据
INSERT INTO role_permissions (role_id, permission_id)
VALUES ('role_manager', 'perm_tender_view'), ('role_manager', 'perm_tender_edit');

UPDATE users SET data_scope = 'self' WHERE id = 'manager_user_id';

-- 普通员工：查看权限 + 自己的数据
INSERT INTO role_permissions (role_id, permission_id)
VALUES ('role_employee', 'perm_tender_view');

UPDATE users SET data_scope = 'self' WHERE id = 'employee_user_id';
```

#### 2. 后端API实现

```python
# /backend/app/routers/tender.py

@router.get("/projects")
async def list_projects(
    current_user: TokenData = Depends(require_permission("tender.view"))
):
    """
    获取项目列表
    - 管理员：看到所有项目
    - 其他用户：只看到自己创建的项目
    """
    query = "SELECT * FROM projects WHERE 1=1"
    params = []
    
    # 数据过滤
    query, params = DataFilter.apply_owner_filter(
        query, params, current_user, resource_type="tender"
    )
    
    # 执行查询...
    return projects


@router.post("/projects")
async def create_project(
    data: ProjectCreate,
    current_user: TokenData = Depends(require_permission("tender.edit"))
):
    """
    创建项目
    - 自动设置 owner_id 为当前用户
    """
    project_id = generate_id()
    
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO projects (id, name, owner_id, created_at)
                VALUES (%s, %s, %s, NOW())
            """, (project_id, data.name, current_user.user_id))
    
    return {"id": project_id, "message": "Project created"}


@router.put("/projects/{project_id}")
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    current_user: TokenData = Depends(require_permission("tender.edit"))
):
    """
    更新项目
    - 检查是否有权限修改此项目
    """
    # 获取项目
    project = get_project(project_id)
    
    if not project:
        raise HTTPException(404, "Project not found")
    
    # 检查数据权限
    require_resource_access(
        current_user, 
        project.owner_id, 
        resource_type="tender",
        resource_name="project"
    )
    
    # 执行更新...
    return {"message": "Project updated"}
```

#### 3. 前端组件实现

```typescript
// /frontend/src/components/TenderProjects.tsx

const TenderProjects: React.FC = () => {
  const { hasPermission } = usePermission();
  const [projects, setProjects] = useState<Project[]>([]);

  // 权限检查
  const canView = hasPermission('tender.view');
  const canEdit = hasPermission('tender.edit');

  // 如果没有查看权限，显示提示
  if (!canView) {
    return (
      <div style={{ padding: '20px', textAlign: 'center', color: '#fbbf24' }}>
        ⚠️ 您没有访问招投标项目的权限
      </div>
    );
  }

  // 加载项目列表（后端会自动过滤数据）
  useEffect(() => {
    const loadProjects = async () => {
      const response = await authFetch(`${API_BASE_URL}/api/tender/projects`);
      const data = await response.json();
      setProjects(data);
    };
    loadProjects();
  }, []);

  return (
    <div>
      <h2>招投标项目</h2>

      {/* 创建按钮：只在有编辑权限时显示 */}
      {canEdit && (
        <button onClick={handleCreate}>
          ➕ 创建新项目
        </button>
      )}

      {/* 项目列表 */}
      <div>
        {projects.map(project => (
          <div key={project.id}>
            <h3>{project.name}</h3>
            
            {/* 编辑按钮：只在有编辑权限时显示 */}
            {canEdit && (
              <button onClick={() => handleEdit(project.id)}>
                ✏️ 编辑
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
```

#### 4. 实际效果

**管理员登录**:
- ✅ 看到"创建新项目"按钮
- ✅ 看到所有用户的项目（100个项目）
- ✅ 每个项目都有"编辑"按钮

**部门经理登录**:
- ✅ 看到"创建新项目"按钮
- ✅ 只看到自己创建的项目（5个项目）
- ✅ 自己的项目有"编辑"按钮

**普通员工登录**:
- ❌ 没有"创建新项目"按钮
- ✅ 只看到自己创建的项目（2个项目）
- ❌ 没有"编辑"按钮

**客户登录**:
- ❌ 直接显示"您没有访问招投标项目的权限"
- ❌ 完全看不到项目列表

---

## 权限控制检查清单

### 后端检查
- [ ] 所有API端点都使用了 `Depends(require_permission(...))`
- [ ] 需要数据过滤的API使用了 `DataFilter`
- [ ] 修改/删除操作使用了 `require_resource_access` 检查资源所有权
- [ ] 创建操作自动设置 `owner_id` 为当前用户

### 前端检查
- [ ] 组件导入了 `usePermission` hook
- [ ] 使用 `hasPermission()` 检查功能权限
- [ ] 无权限的UI元素使用条件渲染隐藏
- [ ] 关键操作按钮根据权限禁用或隐藏
- [ ] 提供友好的无权限提示信息

### 数据库检查
- [ ] 所有权限项已在 `permissions` 表中定义
- [ ] 角色权限关系已在 `role_permissions` 表中配置
- [ ] 用户角色关系已在 `user_roles` 表中配置
- [ ] 用户的 `data_scope` 已正确设置

---

## 常见问题

### Q1: 用户看不到某个功能模块？
**排查步骤**:
1. 检查用户是否登录成功
2. 检查用户的角色分配（`user_roles` 表）
3. 检查角色的权限分配（`role_permissions` 表）
4. 检查权限项是否激活（`permissions.is_active = TRUE`）
5. 检查前端是否正确使用了 `hasPermission()`

### Q2: API返回403 Forbidden？
**原因**:
- 用户没有该API要求的权限
- 后端的 `require_permission()` 检查失败

**解决**:
- 联系管理员分配相应权限

### Q3: 用户可以看到功能，但点击后403？
**原因**:
- 前端权限检查和后端不一致
- 前端只检查了一部分权限

**解决**:
- 确保前端和后端使用相同的权限代码
- 前端应该完全隐藏无权限的功能

### Q4: 管理员看不到某些用户的数据？
**排查步骤**:
1. 检查用户的 `data_scope` 是否为 `all`
2. 检查 `data_permissions` 表是否有覆盖配置
3. 检查后端是否正确应用了 `DataFilter`

---

## 总结

### 权限控制三层防护

```
┌──────────────────────────────────┐
│  第一层: 前端UI控制               │
│  - 隐藏无权限的按钮和菜单          │
│  - 用户体验友好                   │
│  - 但可以被绕过（F12）            │
└──────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│  第二层: API权限验证              │
│  - require_permission()           │
│  - 拦截所有未授权请求              │
│  - 核心安全保障                   │
└──────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│  第三层: 数据权限过滤              │
│  - DataFilter                     │
│  - SQL级别过滤数据                │
│  - 防止越权访问                   │
└──────────────────────────────────┘
```

### 最佳实践
1. **后端优先**: 始终在后端实现完整的权限控制
2. **前端优化**: 前端权限检查用于提升用户体验
3. **双重验证**: 功能权限 + 数据权限
4. **明确提示**: 无权限时给出清晰的提示信息
5. **最小权限**: 默认不授予任何权限，按需分配

---

## 相关文档
- [权限管理API参考](./PERMISSION_MANAGEMENT.md)
- [系统设置权限配置](./SYSTEM_SETTINGS_PERMISSIONS.md)
- [新功能权限配置](./NEW_FEATURES_PERMISSIONS.md)

