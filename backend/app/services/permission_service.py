"""
权限管理服务
"""
import uuid
import json
from datetime import datetime
from typing import List, Optional, Dict, Set
from fastapi import HTTPException, status

from app.models.permission import (
    PermissionCreate, PermissionUpdate, PermissionResponse, PermissionTreeNode,
    RoleCreate, RoleUpdate, RoleResponse, RoleWithPermissions,
    UserRoleResponse, DataPermissionCreate, DataPermissionUpdate, DataPermissionResponse,
    UserPermissionsResponse, PermissionCheckResponse, PermissionStats
)
from app.services.db.postgres import get_conn

# ==================== 权限项管理 ====================
def create_permission(perm_data: PermissionCreate) -> PermissionResponse:
    """创建权限项"""
    perm_id = f"perm_{uuid.uuid4().hex[:16]}"
    
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 检查权限代码是否已存在
            cur.execute("SELECT id FROM permissions WHERE code = %s", (perm_data.code,))
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Permission code '{perm_data.code}' already exists"
                )
            
            # 如果有父权限，检查父权限是否存在
            if perm_data.parent_code:
                cur.execute("SELECT id FROM permissions WHERE code = %s", (perm_data.parent_code,))
                if not cur.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Parent permission '{perm_data.parent_code}' not found"
                    )
            
            cur.execute("""
                INSERT INTO permissions 
                (id, code, name, description, module, parent_code, resource_type, display_order, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, code, name, description, module, parent_code, resource_type, 
                          display_order, is_active, created_at, updated_at
            """, (
                perm_id, perm_data.code, perm_data.name, perm_data.description,
                perm_data.module, perm_data.parent_code, perm_data.resource_type,
                perm_data.display_order, perm_data.is_active
            ))
            
            row = cur.fetchone()
            conn.commit()
            
            return PermissionResponse(
                    id=row['id'], code=row['code'], name=row['name'], description=row['description'],
                    module=row['module'], parent_code=row['parent_code'], resource_type=row['resource_type'],
                    display_order=row['display_order'], is_active=row['is_active'], 
                    created_at=row['created_at'], updated_at=row['updated_at']
                )

def get_permissions(module: Optional[str] = None, active_only: bool = True) -> List[PermissionResponse]:
    """获取权限列表"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT id, code, name, description, module, parent_code, resource_type,
                       display_order, is_active, created_at, updated_at
                FROM permissions
                WHERE 1=1
            """
            params = []
            
            if module:
                query += " AND module = %s"
                params.append(module)
            
            if active_only:
                query += " AND is_active = TRUE"
            
            query += " ORDER BY display_order, code"
            
            cur.execute(query, params)
            rows = cur.fetchall()
            
            return [
                PermissionResponse(
                    id=row['id'], code=row['code'], name=row['name'], description=row['description'],
                    module=row['module'], parent_code=row['parent_code'], resource_type=row['resource_type'],
                    display_order=row['display_order'], is_active=row['is_active'], 
                    created_at=row['created_at'], updated_at=row['updated_at']
                )
                for row in rows
            ]

def get_permissions_tree(module: Optional[str] = None) -> List[PermissionTreeNode]:
    """获取权限树（父子结构）"""
    permissions = get_permissions(module=module, active_only=True)
    
    # 构建权限字典
    perm_dict = {p.code: PermissionTreeNode(**p.model_dump(), children=[]) for p in permissions}
    
    # 构建树结构
    root_perms = []
    for perm in perm_dict.values():
        if perm.parent_code and perm.parent_code in perm_dict:
            perm_dict[perm.parent_code].children.append(perm)
        else:
            root_perms.append(perm)
    
    return root_perms

def get_permission_by_id(perm_id: str) -> Optional[PermissionResponse]:
    """根据ID获取权限"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, code, name, description, module, parent_code, resource_type,
                       display_order, is_active, created_at, updated_at
                FROM permissions WHERE id = %s
            """, (perm_id,))
            
            row = cur.fetchone()
            if not row:
                return None
            
            return PermissionResponse(
                    id=row['id'], code=row['code'], name=row['name'], description=row['description'],
                    module=row['module'], parent_code=row['parent_code'], resource_type=row['resource_type'],
                    display_order=row['display_order'], is_active=row['is_active'], 
                    created_at=row['created_at'], updated_at=row['updated_at']
                )

def update_permission(perm_id: str, perm_data: PermissionUpdate) -> PermissionResponse:
    """更新权限"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 构建更新字段
            update_fields = []
            params = []
            
            if perm_data.name is not None:
                update_fields.append("name = %s")
                params.append(perm_data.name)
            
            if perm_data.description is not None:
                update_fields.append("description = %s")
                params.append(perm_data.description)
            
            if perm_data.display_order is not None:
                update_fields.append("display_order = %s")
                params.append(perm_data.display_order)
            
            if perm_data.is_active is not None:
                update_fields.append("is_active = %s")
                params.append(perm_data.is_active)
            
            if not update_fields:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No fields to update"
                )
            
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.append(perm_id)
            
            cur.execute(f"""
                UPDATE permissions 
                SET {', '.join(update_fields)}
                WHERE id = %s
                RETURNING id, code, name, description, module, parent_code, resource_type,
                          display_order, is_active, created_at, updated_at
            """, params)
            
            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Permission not found"
                )
            
            conn.commit()
            
            return PermissionResponse(
                    id=row['id'], code=row['code'], name=row['name'], description=row['description'],
                    module=row['module'], parent_code=row['parent_code'], resource_type=row['resource_type'],
                    display_order=row['display_order'], is_active=row['is_active'], 
                    created_at=row['created_at'], updated_at=row['updated_at']
                )

# ==================== 角色管理 ====================
def create_role(role_data: RoleCreate) -> RoleResponse:
    """创建角色"""
    role_id = f"role_{uuid.uuid4().hex[:16]}"
    
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 检查角色代码是否已存在
            cur.execute("SELECT id FROM roles WHERE code = %s", (role_data.code,))
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Role code '{role_data.code}' already exists"
                )
            
            cur.execute("""
                INSERT INTO roles (id, code, name, description, is_system, is_active)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, code, name, description, is_system, is_active, created_at, updated_at
            """, (role_id, role_data.code, role_data.name, role_data.description, False, role_data.is_active))
            
            row = cur.fetchone()
            conn.commit()
            
            return RoleResponse(
                id=row['id'], code=row['code'], name=row['name'], description=row['description'], is_system=row['is_system'], is_active=row['is_active'], created_at=row['created_at'], updated_at=row['updated_at']
            )

def get_roles(active_only: bool = True) -> List[RoleResponse]:
    """获取角色列表"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT id, code, name, description, is_system, is_active, created_at, updated_at
                FROM roles
                WHERE 1=1
            """
            
            if active_only:
                query += " AND is_active = TRUE"
            
            query += " ORDER BY is_system DESC, code"
            
            cur.execute(query)
            rows = cur.fetchall()
            
            return [
                RoleResponse(
                    id=row['id'], code=row['code'], name=row['name'], description=row['description'], is_system=row['is_system'], is_active=row['is_active'], created_at=row['created_at'], updated_at=row['updated_at']
                )
                for row in rows
            ]

def get_role_by_id(role_id: str) -> Optional[RoleResponse]:
    """根据ID获取角色"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, code, name, description, is_system, is_active, created_at, updated_at
                FROM roles WHERE id = %s
            """, (role_id,))
            
            row = cur.fetchone()
            if not row:
                return None
            
            return RoleResponse(
                id=row['id'], code=row['code'], name=row['name'], description=row['description'], is_system=row['is_system'], is_active=row['is_active'], created_at=row['created_at'], updated_at=row['updated_at']
            )

def get_role_with_permissions(role_id: str) -> Optional[RoleWithPermissions]:
    """获取角色及其权限"""
    role = get_role_by_id(role_id)
    if not role:
        return None
    
    permissions = get_role_permissions(role_id)
    
    return RoleWithPermissions(**role.model_dump(), permissions=permissions)

def update_role(role_id: str, role_data: RoleUpdate) -> RoleResponse:
    """更新角色"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 检查是否为系统角色
            cur.execute("SELECT is_system FROM roles WHERE id = %s", (role_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Role not found"
                )
            
            if row['is_system']:  # is_system
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot modify system role"
                )
            
            # 构建更新字段
            update_fields = []
            params = []
            
            if role_data.name is not None:
                update_fields.append("name = %s")
                params.append(role_data.name)
            
            if role_data.description is not None:
                update_fields.append("description = %s")
                params.append(role_data.description)
            
            if role_data.is_active is not None:
                update_fields.append("is_active = %s")
                params.append(role_data.is_active)
            
            if not update_fields:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No fields to update"
                )
            
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.append(role_id)
            
            cur.execute(f"""
                UPDATE roles 
                SET {', '.join(update_fields)}
                WHERE id = %s
                RETURNING id, code, name, description, is_system, is_active, created_at, updated_at
            """, params)
            
            row = cur.fetchone()
            conn.commit()
            
            return RoleResponse(
                id=row['id'], code=row['code'], name=row['name'], description=row['description'], is_system=row['is_system'], is_active=row['is_active'], created_at=row['created_at'], updated_at=row['updated_at']
            )

def delete_role(role_id: str) -> None:
    """删除角色"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 检查是否为系统角色
            cur.execute("SELECT is_system FROM roles WHERE id = %s", (role_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Role not found"
                )
            
            if row['is_system']:  # is_system
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete system role"
                )
            
            cur.execute("DELETE FROM roles WHERE id = %s", (role_id,))
            conn.commit()

# ==================== 角色-权限管理 ====================
def get_role_permissions(role_id: str) -> List[PermissionResponse]:
    """获取角色的权限列表"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.id, p.code, p.name, p.description, p.module, p.parent_code, 
                       p.resource_type, p.display_order, p.is_active, p.created_at, p.updated_at
                FROM permissions p
                JOIN role_permissions rp ON p.id = rp.permission_id
                WHERE rp.role_id = %s AND p.is_active = TRUE
                ORDER BY p.display_order, p.code
            """, (role_id,))
            
            rows = cur.fetchall()
            
            return [
                PermissionResponse(
                    id=row['id'], code=row['code'], name=row['name'], description=row['description'],
                    module=row['module'], parent_code=row['parent_code'], resource_type=row['resource_type'],
                    display_order=row['display_order'], is_active=row['is_active'], 
                    created_at=row['created_at'], updated_at=row['updated_at']
                )
                for row in rows
            ]

def assign_permissions_to_role(role_id: str, permission_ids: List[str]) -> None:
    """为角色分配权限"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 检查角色是否存在
            cur.execute("SELECT id FROM roles WHERE id = %s", (role_id,))
            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Role not found"
                )
            
            # 检查权限是否存在
            cur.execute("""
                SELECT id FROM permissions WHERE id = ANY(%s)
            """, (permission_ids,))
            existing_perms = {row['id'] for row in cur.fetchall()}
            
            invalid_perms = set(permission_ids) - existing_perms
            if invalid_perms:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid permission IDs: {invalid_perms}"
                )
            
            # 批量插入（忽略已存在的）
            for perm_id in permission_ids:
                rp_id = f"rp_{uuid.uuid4().hex[:16]}"
                cur.execute("""
                    INSERT INTO role_permissions (id, role_id, permission_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (role_id, permission_id) DO NOTHING
                """, (rp_id, role_id, perm_id))
            
            conn.commit()

def remove_permissions_from_role(role_id: str, permission_ids: List[str]) -> None:
    """移除角色的权限"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM role_permissions
                WHERE role_id = %s AND permission_id = ANY(%s)
            """, (role_id, permission_ids))
            
            conn.commit()

# ==================== 用户-角色管理 ====================
def get_user_roles(user_id: str) -> List[UserRoleResponse]:
    """获取用户的角色列表"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ur.id, ur.user_id, ur.role_id, r.code, r.name, 
                       ur.granted_by, ur.granted_at, ur.expires_at
                FROM user_roles ur
                JOIN roles r ON ur.role_id = r.id
                WHERE ur.user_id = %s AND r.is_active = TRUE
                ORDER BY ur.granted_at DESC
            """, (user_id,))
            
            rows = cur.fetchall()
            
            return [
                UserRoleResponse(
                    id=row['id'], user_id=row['user_id'], role_id=row['role_id'], role_code=row['role_code'], role_name=row['role_name'], granted_by=row['granted_by'], granted_at=row['granted_at'], expires_at=row['expires_at']
                )
                for row in rows
            ]

def assign_roles_to_user(user_id: str, role_ids: List[str], granted_by: Optional[str] = None) -> None:
    """为用户分配角色"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 检查用户是否存在
            cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # 检查角色是否存在
            cur.execute("SELECT id FROM roles WHERE id = ANY(%s)", (role_ids,))
            existing_roles = {row['id'] for row in cur.fetchall()}
            
            invalid_roles = set(role_ids) - existing_roles
            if invalid_roles:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid role IDs: {invalid_roles}"
                )
            
            # 批量插入
            for role_id in role_ids:
                ur_id = f"ur_{uuid.uuid4().hex[:16]}"
                cur.execute("""
                    INSERT INTO user_roles (id, user_id, role_id, granted_by)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id, role_id) DO NOTHING
                """, (ur_id, user_id, role_id, granted_by))
            
            conn.commit()

def remove_roles_from_user(user_id: str, role_ids: List[str]) -> None:
    """移除用户的角色"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM user_roles
                WHERE user_id = %s AND role_id = ANY(%s)
            """, (user_id, role_ids))
            
            conn.commit()

# ==================== 权限检查 ====================
def get_user_permissions(user_id: str) -> UserPermissionsResponse:
    """获取用户的所有权限"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 获取用户信息
            cur.execute("""
                SELECT username, data_scope FROM users WHERE id = %s
            """, (user_id,))
            user_row = cur.fetchone()
            if not user_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            username = user_row['username']
            data_scope = user_row['data_scope']
            
            # 获取用户的角色
            cur.execute("""
                SELECT r.id, r.code, r.name, r.description, r.is_system, r.is_active, 
                       r.created_at, r.updated_at
                FROM roles r
                JOIN user_roles ur ON r.id = ur.role_id
                WHERE ur.user_id = %s AND r.is_active = TRUE
            """, (user_id,))
            
            roles = [
                RoleResponse(
                    id=row['id'], code=row['code'], name=row['name'], description=row['description'], is_system=row['is_system'], is_active=row['is_active'], created_at=row['created_at'], updated_at=row['updated_at']
                )
                for row in cur.fetchall()
            ]
            
            # 检查是否是管理员
            is_admin = any(role.code == 'admin' for role in roles)
            
            if is_admin:
                # 管理员：返回所有激活的权限
                cur.execute("""
                    SELECT DISTINCT p.id, p.code, p.name, p.description, p.module, p.parent_code,
                           p.resource_type, p.display_order, p.is_active, p.created_at, p.updated_at
                    FROM permissions p
                    WHERE p.is_active = TRUE
                    ORDER BY p.display_order, p.code
                """)
            else:
                # 非管理员：获取通过角色分配的权限
                cur.execute("""
                    SELECT DISTINCT p.id, p.code, p.name, p.description, p.module, p.parent_code,
                           p.resource_type, p.display_order, p.is_active, p.created_at, p.updated_at
                    FROM permissions p
                    JOIN role_permissions rp ON p.id = rp.permission_id
                    JOIN user_roles ur ON rp.role_id = ur.role_id
                    WHERE ur.user_id = %s AND p.is_active = TRUE
                    ORDER BY p.display_order, p.code
                """, (user_id,))
            
            permissions = [
                PermissionResponse(
                    id=row['id'], code=row['code'], name=row['name'], description=row['description'],
                    module=row['module'], parent_code=row['parent_code'], resource_type=row['resource_type'],
                    display_order=row['display_order'], is_active=row['is_active'], 
                    created_at=row['created_at'], updated_at=row['updated_at']
                )
                for row in cur.fetchall()
            ]
            
            return UserPermissionsResponse(
                user_id=user_id,
                username=username,
                roles=roles,
                permissions=permissions,
                data_scope=data_scope
            )

def check_user_permissions(user_id: str, permission_codes: List[str]) -> Dict[str, bool]:
    """检查用户是否拥有指定权限"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 获取用户拥有的权限代码
            cur.execute("""
                SELECT DISTINCT p.code
                FROM permissions p
                JOIN role_permissions rp ON p.id = rp.permission_id
                JOIN user_roles ur ON rp.role_id = ur.role_id
                WHERE ur.user_id = %s AND p.is_active = TRUE
            """, (user_id,))
            
            user_perms = {row['id'] for row in cur.fetchall()}
            
            # 检查每个权限
            result = {}
            for code in permission_codes:
                result[code] = code in user_perms
            
            return result

def has_permission(user_id: str, permission_code: str) -> bool:
    """
    检查用户是否拥有某个权限
    
    管理员（admin角色）自动拥有所有权限
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 检查用户是否是管理员
            cur.execute("""
                SELECT EXISTS(
                    SELECT 1 
                    FROM user_roles ur
                    JOIN roles r ON ur.role_id = r.id
                    WHERE ur.user_id = %s 
                    AND r.code = 'admin'
                    AND r.is_active = TRUE
                )
            """, (user_id,))
            
            row = cur.fetchone()
            is_admin = list(row.values())[0] if row else False
            if is_admin:
                return True  # 管理员拥有所有权限
            
            # 非管理员：检查通过角色分配的权限
            result = check_user_permissions(user_id, [permission_code])
            return result.get(permission_code, False)

# ==================== 数据权限管理 ====================
def get_data_permission(user_id: str, resource_type: str) -> Optional[DataPermissionResponse]:
    """获取用户对某类资源的数据权限"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, user_id, resource_type, data_scope, custom_scope_json,
                       created_at, updated_at
                FROM data_permissions
                WHERE user_id = %s AND resource_type = %s
            """, (user_id, resource_type))
            
            row = cur.fetchone()
            if not row:
                return None
            
            custom_scope = json.loads(row['custom_scope_json']) if row.get('custom_scope_json') else None
            
            return DataPermissionResponse(
                id=row['id'], user_id=row['user_id'], resource_type=row['resource_type'], data_scope=row['data_scope'], custom_scope_json=custom_scope, created_at=row['created_at'], updated_at=row['updated_at']
            )

def set_data_permission(user_id: str, resource_type: str, data_scope: str, custom_scope_json: Optional[dict] = None) -> DataPermissionResponse:
    """设置用户的数据权限"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 检查用户是否存在
            cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            dp_id = f"dp_{uuid.uuid4().hex[:16]}"
            custom_json_str = json.dumps(custom_scope_json) if custom_scope_json else None
            
            cur.execute("""
                INSERT INTO data_permissions (id, user_id, resource_type, data_scope, custom_scope_json)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (user_id, resource_type) 
                DO UPDATE SET 
                    data_scope = EXCLUDED.data_scope,
                    custom_scope_json = EXCLUDED.custom_scope_json,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id, user_id, resource_type, data_scope, custom_scope_json,
                          created_at, updated_at
            """, (dp_id, user_id, resource_type, data_scope, custom_json_str))
            
            row = cur.fetchone()
            conn.commit()
            
            custom_scope = json.loads(row['custom_scope_json']) if row.get('custom_scope_json') else None
            
            return DataPermissionResponse(
                id=row['id'], user_id=row['user_id'], resource_type=row['resource_type'], data_scope=row['data_scope'], custom_scope_json=custom_scope, created_at=row['created_at'], updated_at=row['updated_at']
            )

# ==================== 统计信息 ====================
def get_permission_stats() -> PermissionStats:
    """获取权限统计信息"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM permissions) AS total_permissions,
                    (SELECT COUNT(*) FROM roles) AS total_roles,
                    (SELECT COUNT(*) FROM user_roles) AS total_user_roles,
                    (SELECT COUNT(*) FROM permissions WHERE is_active = TRUE) AS active_permissions,
                    (SELECT COUNT(*) FROM roles WHERE is_active = TRUE) AS active_roles
            """)
            
            row = cur.fetchone()
            
            return PermissionStats(
                total_permissions=row['total_permissions'], total_roles=row['total_roles'], total_user_roles=row['total_user_roles'], active_permissions=row['active_permissions'], active_roles=row['active_roles']
            )

