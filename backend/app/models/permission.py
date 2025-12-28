"""
权限管理相关模型
"""
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field

# ==================== 权限项模型 ====================
class PermissionBase(BaseModel):
    """权限项基础模型"""
    code: str = Field(..., max_length=100, description="权限代码")
    name: str = Field(..., max_length=100, description="权限名称")
    description: Optional[str] = Field(None, description="权限描述")
    module: str = Field(..., max_length=50, description="所属模块")
    parent_code: Optional[str] = Field(None, max_length=100, description="父权限代码")
    resource_type: Optional[str] = Field(None, max_length=50, description="资源类型")
    display_order: int = Field(0, description="显示顺序")
    is_active: bool = Field(True, description="是否启用")

class PermissionCreate(PermissionBase):
    """创建权限项请求"""
    pass

class PermissionUpdate(BaseModel):
    """更新权限项请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None

class PermissionResponse(PermissionBase):
    """权限项响应"""
    id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class PermissionTreeNode(PermissionResponse):
    """权限树节点（包含子权限）"""
    children: List['PermissionTreeNode'] = []

# ==================== 角色模型 ====================
class RoleBase(BaseModel):
    """角色基础模型"""
    code: str = Field(..., max_length=50, description="角色代码")
    name: str = Field(..., max_length=100, description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")
    is_active: bool = Field(True, description="是否启用")

class RoleCreate(RoleBase):
    """创建角色请求"""
    pass

class RoleUpdate(BaseModel):
    """更新角色请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class RoleResponse(RoleBase):
    """角色响应"""
    id: str
    is_system: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class RoleWithPermissions(RoleResponse):
    """角色及其权限"""
    permissions: List[PermissionResponse] = []

# ==================== 角色-权限关联 ====================
class RolePermissionAssign(BaseModel):
    """分配权限给角色"""
    role_id: str
    permission_ids: List[str]

class RolePermissionRemove(BaseModel):
    """移除角色的权限"""
    role_id: str
    permission_ids: List[str]

# ==================== 用户-角色关联 ====================
class UserRoleAssign(BaseModel):
    """分配角色给用户"""
    user_id: str
    role_ids: List[str]
    expires_at: Optional[datetime] = None

class UserRoleRemove(BaseModel):
    """移除用户的角色"""
    user_id: str
    role_ids: List[str]

class UserRoleResponse(BaseModel):
    """用户角色响应"""
    id: str
    user_id: str
    role_id: str
    role_code: str
    role_name: str
    granted_by: Optional[str] = None
    granted_at: datetime
    expires_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# ==================== 数据权限模型 ====================
DataScope = Literal["all", "dept", "self", "custom"]

class DataPermissionBase(BaseModel):
    """数据权限基础模型"""
    user_id: str
    resource_type: str = Field(..., max_length=50, description="资源类型")
    data_scope: DataScope = Field("self", description="数据范围")
    custom_scope_json: Optional[dict] = Field(None, description="自定义范围")

class DataPermissionCreate(DataPermissionBase):
    """创建数据权限请求"""
    pass

class DataPermissionUpdate(BaseModel):
    """更新数据权限请求"""
    data_scope: Optional[DataScope] = None
    custom_scope_json: Optional[dict] = None

class DataPermissionResponse(DataPermissionBase):
    """数据权限响应"""
    id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# ==================== 权限验证 ====================
class PermissionCheck(BaseModel):
    """权限检查请求"""
    user_id: str
    permission_codes: List[str]

class PermissionCheckResponse(BaseModel):
    """权限检查响应"""
    user_id: str
    permissions: dict[str, bool]  # permission_code -> has_permission

class UserPermissionsResponse(BaseModel):
    """用户所有权限响应"""
    user_id: str
    username: str
    roles: List[RoleResponse]
    permissions: List[PermissionResponse]
    data_scope: Optional[DataScope] = None

# ==================== 权限统计 ====================
class PermissionStats(BaseModel):
    """权限统计"""
    total_permissions: int
    total_roles: int
    total_user_roles: int
    active_permissions: int
    active_roles: int

