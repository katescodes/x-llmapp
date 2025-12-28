"""
认证相关的API路由
"""
from datetime import timedelta
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends

from app.models.user import (
    UserCreate, UserUpdate, UserResponse, LoginRequest, LoginResponse,
    UserChangePassword, UserRole
)
from app.services import user_service
from app.utils.auth import (
    create_access_token, get_current_user, require_admin,
    TokenData, ACCESS_TOKEN_EXPIRE_HOURS
)
from app.utils.permission import require_permission

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    """
    注册新用户
    
    - 默认角色为 customer（客户）
    - 管理员可以通过用户管理API创建其他角色
    """
    # 限制注册时的角色（仅允许注册为客户）
    if user_data.role not in ["customer"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only register as customer. Contact admin for other roles."
        )
    
    return user_service.create_user(user_data)

@router.post("/login", response_model=LoginResponse)
async def login(credentials: LoginRequest):
    """
    用户登录
    
    返回 JWT access token 和用户信息
    """
    user = user_service.authenticate_user(credentials.username, credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # 生成 JWT token
    access_token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        expires_delta=timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    )
    
    # 返回用户信息（不包含密码）
    user_response = UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        display_name=user.display_name,
        phone=user.phone,
        department=user.department,
        company=user.company,
        avatar_url=user.avatar_url,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        created_at=user.created_at
    )
    
    return LoginResponse(
        access_token=access_token,
        user=user_response,
        expires_in=ACCESS_TOKEN_EXPIRE_HOURS * 3600
    )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: TokenData = Depends(get_current_user)):
    """
    获取当前登录用户信息
    
    需要认证
    """
    user = user_service.get_user_by_id(current_user.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    update_data: UserUpdate,
    current_user: TokenData = Depends(get_current_user)
):
    """
    更新当前用户信息
    
    需要认证
    """
    return user_service.update_user(current_user.user_id, update_data)

@router.post("/change-password")
async def change_password(
    password_data: UserChangePassword,
    current_user: TokenData = Depends(get_current_user)
):
    """
    修改密码
    
    需要认证
    """
    user_service.change_password(
        current_user.user_id,
        password_data.old_password,
        password_data.new_password
    )
    return {"message": "Password changed successfully"}

@router.post("/logout")
async def logout(current_user: TokenData = Depends(get_current_user)):
    """
    登出（客户端需要删除token）
    
    需要认证
    """
    # JWT 是无状态的，实际的登出由客户端删除token完成
    # 这里可以记录登出日志或将token加入黑名单（如果需要）
    return {"message": "Logged out successfully"}

# ===== 管理员功能 =====

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    role: UserRole = None,
    current_user: TokenData = Depends(require_permission("permission.user.view"))
):
    """
    获取用户列表
    
    权限要求：permission.user.view
    
    可选参数:
    - role: 按角色筛选
    """
    return user_service.get_all_users(role=role)

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user_admin(
    user_data: UserCreate,
    current_user: TokenData = Depends(require_permission("permission.user.create"))
):
    """
    创建用户
    
    权限要求：permission.user.create
    
    管理员可以创建任意角色的用户
    """
    return user_service.create_user(user_data)

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: TokenData = Depends(require_permission("permission.user.view"))
):
    """
    获取指定用户信息
    
    权限要求：permission.user.view
    """
    user = user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user_admin(
    user_id: str,
    update_data: UserUpdate,
    current_user: TokenData = Depends(require_permission("permission.user.edit"))
):
    """
    更新用户信息
    
    权限要求：permission.user.edit
    """
    return user_service.update_user(user_id, update_data)

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: TokenData = Depends(require_permission("permission.user.delete"))
):
    """
    删除用户
    
    权限要求：permission.user.delete
    """
    # 防止删除自己
    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself"
        )
    
    deleted = user_service.delete_user(user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {"message": "User deleted successfully"}

