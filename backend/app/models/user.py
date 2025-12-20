"""
用户模型
"""
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, EmailStr, Field

# 用户角色类型
UserRole = Literal["admin", "employee", "customer"]

class UserBase(BaseModel):
    """用户基础模型"""
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    display_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    department: Optional[str] = Field(None, max_length=100)
    company: Optional[str] = Field(None, max_length=100)

class UserCreate(UserBase):
    """创建用户请求"""
    password: str = Field(..., min_length=6, max_length=100)
    role: UserRole = "customer"

class UserUpdate(BaseModel):
    """更新用户请求"""
    email: Optional[EmailStr] = None
    display_name: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    company: Optional[str] = None
    is_active: Optional[bool] = None

class UserChangePassword(BaseModel):
    """修改密码请求"""
    old_password: str
    new_password: str = Field(..., min_length=6)

class UserInDB(UserBase):
    """数据库中的用户模型"""
    id: str
    password_hash: str
    role: UserRole
    avatar_url: Optional[str] = None
    is_active: bool = True
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class UserResponse(UserBase):
    """用户响应模型（不包含密码）"""
    id: str
    role: UserRole
    avatar_url: Optional[str] = None
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str

class LoginResponse(BaseModel):
    """登录响应"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    expires_in: int = 86400  # 24小时

class TokenData(BaseModel):
    """Token 数据"""
    user_id: str
    username: str
    role: UserRole

