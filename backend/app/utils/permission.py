"""
权限验证工具和装饰器
"""
from typing import List, Optional, Callable
from functools import wraps
from fastapi import HTTPException, status, Depends

from app.models.user import TokenData
from app.utils.auth import get_current_user
from app.services import permission_service

# ==================== 权限检查依赖 ====================
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

def require_any_permission(permission_codes: List[str]):
    """
    依赖注入：要求任一权限
    用法: current_user: TokenData = Depends(require_any_permission(["chat.view", "chat.create"]))
    """
    async def check_permissions(current_user: TokenData = Depends(get_current_user)) -> TokenData:
        # 检查用户是否拥有任一权限
        result = permission_service.check_user_permissions(current_user.user_id, permission_codes)
        if not any(result.values()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"At least one permission required: {', '.join(permission_codes)}"
            )
        return current_user
    
    return check_permissions

def require_all_permissions(permission_codes: List[str]):
    """
    依赖注入：要求所有权限
    用法: current_user: TokenData = Depends(require_all_permissions(["kb.view", "kb.edit"]))
    """
    async def check_permissions(current_user: TokenData = Depends(get_current_user)) -> TokenData:
        # 检查用户是否拥有所有权限
        result = permission_service.check_user_permissions(current_user.user_id, permission_codes)
        if not all(result.values()):
            missing = [code for code, has in result.items() if not has]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permissions: {', '.join(missing)}"
            )
        return current_user
    
    return check_permissions

# ==================== 数据权限过滤 ====================
class DataFilter:
    """数据权限过滤器"""
    
    @staticmethod
    def get_owner_filter(current_user: TokenData, resource_type: str = None) -> dict:
        """
        获取数据所有者过滤条件
        
        返回：
        - {"owner_id": user_id} - 仅查询自己的数据
        - {"all": True} - 可以查询所有数据
        - {"owner_ids": [id1, id2]} - 可以查询指定用户的数据
        """
        user_id = current_user.user_id
        
        # 检查用户的数据权限
        from app.services.db.postgres import get_conn
        
        with get_conn() as conn:
            with conn.cursor() as cur:
                # 首先检查用户表中的 data_scope
                cur.execute("SELECT data_scope FROM users WHERE id = %s", (user_id,))
                row = cur.fetchone()
                
                if row and row[0]:
                    data_scope = row[0]
                else:
                    data_scope = "self"
                
                # 如果指定了资源类型，检查数据权限表
                if resource_type:
                    cur.execute("""
                        SELECT data_scope, custom_scope_json
                        FROM data_permissions
                        WHERE user_id = %s AND resource_type = %s
                    """, (user_id, resource_type))
                    
                    dp_row = cur.fetchone()
                    if dp_row:
                        data_scope = dp_row[0]
                        custom_scope = dp_row[1]
                        
                        if data_scope == "custom" and custom_scope:
                            # 自定义范围
                            import json
                            scope_data = json.loads(custom_scope) if isinstance(custom_scope, str) else custom_scope
                            if "owner_ids" in scope_data:
                                return {"owner_ids": scope_data["owner_ids"]}
                
                # 根据数据范围返回过滤条件
                if data_scope == "all":
                    return {"all": True}
                elif data_scope == "dept":
                    # TODO: 实现部门数据范围（需要部门表）
                    return {"owner_id": user_id}
                else:  # self
                    return {"owner_id": user_id}
    
    @staticmethod
    def apply_owner_filter(query: str, params: list, current_user: TokenData, 
                          resource_type: str = None, table_alias: str = None) -> tuple:
        """
        应用所有者过滤到SQL查询
        
        Args:
            query: SQL查询语句
            params: 查询参数列表
            current_user: 当前用户
            resource_type: 资源类型
            table_alias: 表别名（如果有）
        
        Returns:
            (modified_query, modified_params)
        """
        filter_cond = DataFilter.get_owner_filter(current_user, resource_type)
        
        if filter_cond.get("all"):
            # 可以查询所有数据，不添加过滤条件
            return query, params
        
        table_prefix = f"{table_alias}." if table_alias else ""
        
        if "owner_id" in filter_cond:
            # 仅查询自己的数据
            query += f" AND {table_prefix}owner_id = %s"
            params.append(filter_cond["owner_id"])
        elif "owner_ids" in filter_cond:
            # 查询指定用户的数据
            query += f" AND {table_prefix}owner_id = ANY(%s)"
            params.append(filter_cond["owner_ids"])
        
        return query, params
    
    @staticmethod
    def can_access_resource(current_user: TokenData, resource_owner_id: str, 
                           resource_type: str = None) -> bool:
        """
        检查用户是否可以访问特定资源
        
        Args:
            current_user: 当前用户
            resource_owner_id: 资源所有者ID
            resource_type: 资源类型
        
        Returns:
            True if can access, False otherwise
        """
        filter_cond = DataFilter.get_owner_filter(current_user, resource_type)
        
        if filter_cond.get("all"):
            return True
        
        if "owner_id" in filter_cond:
            return filter_cond["owner_id"] == resource_owner_id
        
        if "owner_ids" in filter_cond:
            return resource_owner_id in filter_cond["owner_ids"]
        
        return False

# ==================== 便捷函数 ====================
def check_permission(user_id: str, permission_code: str) -> bool:
    """检查用户是否拥有权限"""
    return permission_service.has_permission(user_id, permission_code)

def check_any_permission(user_id: str, permission_codes: List[str]) -> bool:
    """检查用户是否拥有任一权限"""
    result = permission_service.check_user_permissions(user_id, permission_codes)
    return any(result.values())

def check_all_permissions(user_id: str, permission_codes: List[str]) -> bool:
    """检查用户是否拥有所有权限"""
    result = permission_service.check_user_permissions(user_id, permission_codes)
    return all(result.values())

def require_resource_access(current_user: TokenData, resource_owner_id: str, 
                           resource_type: str = None, resource_name: str = "resource") -> None:
    """
    要求用户可以访问资源，否则抛出异常
    
    Args:
        current_user: 当前用户
        resource_owner_id: 资源所有者ID
        resource_type: 资源类型
        resource_name: 资源名称（用于错误消息）
    
    Raises:
        HTTPException: 如果用户无权访问
    """
    if not DataFilter.can_access_resource(current_user, resource_owner_id, resource_type):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You don't have permission to access this {resource_name}"
        )

