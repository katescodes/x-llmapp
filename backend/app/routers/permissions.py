"""
权限管理API路由
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query

from app.models.permission import (
    PermissionCreate, PermissionUpdate, PermissionResponse, PermissionTreeNode,
    RoleCreate, RoleUpdate, RoleResponse, RoleWithPermissions,
    UserRoleResponse, RolePermissionAssign, UserRoleAssign,
    DataPermissionCreate, DataPermissionResponse,
    UserPermissionsResponse, PermissionCheckResponse, PermissionStats
)
from app.models.user import TokenData, UserResponse
from app.services import permission_service, user_service
from app.utils.auth import get_current_user, require_admin
from app.utils.permission import require_permission

router = APIRouter(prefix="/api/permissions", tags=["Permissions"])

# ==================== 权限项管理 ====================
@router.get("/items", response_model=List[PermissionResponse])
async def list_permissions(
    module: Optional[str] = Query(None, description="过滤模块"),
    active_only: bool = Query(True, description="仅活跃权限"),
    current_user: TokenData = Depends(require_permission("permission.item.view"))
):
    """
    获取权限项列表
    
    权限要求：permission.item.view
    """
    return permission_service.get_permissions(module=module, active_only=active_only)

@router.get("/items/tree", response_model=List[PermissionTreeNode])
async def get_permissions_tree(
    module: Optional[str] = Query(None, description="过滤模块"),
    current_user: TokenData = Depends(require_permission("permission.item.view"))
):
    """
    获取权限树（父子结构）
    
    权限要求：permission.item.view
    """
    return permission_service.get_permissions_tree(module=module)

@router.get("/items/{perm_id}", response_model=PermissionResponse)
async def get_permission(
    perm_id: str,
    current_user: TokenData = Depends(require_permission("permission.item.view"))
):
    """
    获取单个权限项
    
    权限要求：permission.item.view
    """
    perm = permission_service.get_permission_by_id(perm_id)
    if not perm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found"
        )
    return perm

@router.post("/items", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
async def create_permission(
    perm_data: PermissionCreate,
    current_user: TokenData = Depends(require_admin)
):
    """
    创建权限项（仅管理员）
    
    权限要求：admin
    """
    return permission_service.create_permission(perm_data)

@router.put("/items/{perm_id}", response_model=PermissionResponse)
async def update_permission(
    perm_id: str,
    perm_data: PermissionUpdate,
    current_user: TokenData = Depends(require_permission("permission.item.edit"))
):
    """
    更新权限项
    
    权限要求：permission.item.edit
    """
    return permission_service.update_permission(perm_id, perm_data)

# ==================== 角色管理 ====================
@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(
    active_only: bool = Query(True, description="仅活跃角色"),
    current_user: TokenData = Depends(require_permission("permission.role.view"))
):
    """
    获取角色列表
    
    权限要求：permission.role.view
    """
    return permission_service.get_roles(active_only=active_only)

@router.get("/roles/{role_id}", response_model=RoleWithPermissions)
async def get_role(
    role_id: str,
    current_user: TokenData = Depends(require_permission("permission.role.view"))
):
    """
    获取角色详情（含权限列表）
    
    权限要求：permission.role.view
    """
    role = permission_service.get_role_with_permissions(role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    return role

@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    current_user: TokenData = Depends(require_permission("permission.role.create"))
):
    """
    创建角色
    
    权限要求：permission.role.create
    """
    return permission_service.create_role(role_data)

@router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: str,
    role_data: RoleUpdate,
    current_user: TokenData = Depends(require_permission("permission.role.edit"))
):
    """
    更新角色
    
    权限要求：permission.role.edit
    """
    return permission_service.update_role(role_id, role_data)

@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: str,
    current_user: TokenData = Depends(require_permission("permission.role.delete"))
):
    """
    删除角色
    
    权限要求：permission.role.delete
    """
    permission_service.delete_role(role_id)

# ==================== 角色-权限管理 ====================
@router.get("/roles/{role_id}/permissions", response_model=List[PermissionResponse])
async def get_role_permissions(
    role_id: str,
    current_user: TokenData = Depends(require_permission("permission.role.view"))
):
    """
    获取角色的权限列表
    
    权限要求：permission.role.view
    """
    return permission_service.get_role_permissions(role_id)

@router.post("/roles/assign-permissions")
async def assign_permissions_to_role(
    assign_data: RolePermissionAssign,
    current_user: TokenData = Depends(require_permission("permission.role.assign_perm"))
):
    """
    为角色分配权限
    
    权限要求：permission.role.assign_perm
    """
    permission_service.assign_permissions_to_role(
        assign_data.role_id,
        assign_data.permission_ids
    )
    return {"message": "Permissions assigned successfully"}

@router.post("/roles/remove-permissions")
async def remove_permissions_from_role(
    remove_data: RolePermissionAssign,
    current_user: TokenData = Depends(require_permission("permission.role.assign_perm"))
):
    """
    移除角色的权限
    
    权限要求：permission.role.assign_perm
    """
    permission_service.remove_permissions_from_role(
        remove_data.role_id,
        remove_data.permission_ids
    )
    return {"message": "Permissions removed successfully"}

# ==================== 用户-角色管理 ====================
@router.get("/users/{user_id}/roles", response_model=List[UserRoleResponse])
async def get_user_roles(
    user_id: str,
    current_user: TokenData = Depends(require_permission("permission.user.view"))
):
    """
    获取用户的角色列表
    
    权限要求：permission.user.view
    """
    return permission_service.get_user_roles(user_id)

@router.post("/users/assign-roles")
async def assign_roles_to_user(
    assign_data: UserRoleAssign,
    current_user: TokenData = Depends(require_permission("permission.user.assign_role"))
):
    """
    为用户分配角色
    
    权限要求：permission.user.assign_role
    """
    permission_service.assign_roles_to_user(
        assign_data.user_id,
        assign_data.role_ids,
        granted_by=current_user.user_id
    )
    return {"message": "Roles assigned successfully"}

@router.post("/users/remove-roles")
async def remove_roles_from_user(
    remove_data: UserRoleAssign,
    current_user: TokenData = Depends(require_permission("permission.user.assign_role"))
):
    """
    移除用户的角色
    
    权限要求：permission.user.assign_role
    """
    permission_service.remove_roles_from_user(
        remove_data.user_id,
        remove_data.role_ids
    )
    return {"message": "Roles removed successfully"}

# ==================== 用户权限查询 ====================
@router.get("/users/{user_id}/all-permissions", response_model=UserPermissionsResponse)
async def get_user_all_permissions(
    user_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    获取用户的所有权限
    
    - 普通用户只能查询自己的权限
    - 管理员可以查询任何用户的权限
    """
    # 只能查询自己的权限，除非是管理员
    if current_user.user_id != user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own permissions"
        )
    
    return permission_service.get_user_permissions(user_id)

@router.get("/me/permissions", response_model=UserPermissionsResponse)
async def get_my_permissions(
    current_user: TokenData = Depends(get_current_user)
):
    """
    获取当前用户的所有权限
    """
    return permission_service.get_user_permissions(current_user.user_id)

@router.post("/users/{user_id}/check", response_model=PermissionCheckResponse)
async def check_user_permissions(
    user_id: str,
    permission_codes: List[str],
    current_user: TokenData = Depends(get_current_user)
):
    """
    检查用户是否拥有指定权限
    
    - 普通用户只能检查自己的权限
    - 管理员可以检查任何用户的权限
    """
    if current_user.user_id != user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only check your own permissions"
        )
    
    result = permission_service.check_user_permissions(user_id, permission_codes)
    
    return PermissionCheckResponse(
        user_id=user_id,
        permissions=result
    )

# ==================== 数据权限管理 ====================
@router.get("/users/{user_id}/data-permissions/{resource_type}", response_model=DataPermissionResponse)
async def get_user_data_permission(
    user_id: str,
    resource_type: str,
    current_user: TokenData = Depends(require_admin)
):
    """
    获取用户的数据权限（仅管理员）
    
    权限要求：admin
    """
    data_perm = permission_service.get_data_permission(user_id, resource_type)
    if not data_perm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data permission not found"
        )
    return data_perm

@router.post("/users/{user_id}/data-permissions", response_model=DataPermissionResponse)
async def set_user_data_permission(
    user_id: str,
    data_perm: DataPermissionCreate,
    current_user: TokenData = Depends(require_admin)
):
    """
    设置用户的数据权限（仅管理员）
    
    权限要求：admin
    """
    return permission_service.set_data_permission(
        user_id,
        data_perm.resource_type,
        data_perm.data_scope,
        data_perm.custom_scope_json
    )

# ==================== 统计信息 ====================
@router.get("/stats", response_model=PermissionStats)
async def get_permission_stats(
    current_user: TokenData = Depends(require_admin)
):
    """
    获取权限统计信息（仅管理员）
    
    权限要求：admin
    """
    return permission_service.get_permission_stats()

