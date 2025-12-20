"""
认证工具：JWT 生成、验证、密码加密
"""
import os
from datetime import datetime, timedelta
from typing import Optional
import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.models.user import UserRole, TokenData

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT 配置
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# HTTP Bearer Token
security = HTTPBearer()

def hash_password(password: str) -> str:
    """加密密码"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(
    user_id: str,
    username: str,
    role: UserRole,
    expires_delta: Optional[timedelta] = None
) -> str:
    """创建 JWT access token"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    
    to_encode = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> TokenData:
    """解码并验证 JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        username: str = payload.get("username")
        role: str = payload.get("role")
        
        if user_id is None or username is None or role is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        return TokenData(user_id=user_id, username=username, role=role)
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> TokenData:
    """
    依赖注入：获取当前登录用户
    用法: current_user: TokenData = Depends(get_current_user)
    """
    token = credentials.credentials
    return decode_access_token(token)

def get_current_user_sync(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> TokenData:
    """
    依赖注入：获取当前登录用户（同步版本）
    用法: current_user: TokenData = Depends(get_current_user_sync)
    """
    token = credentials.credentials
    return decode_access_token(token)

async def require_admin(
    current_user: TokenData = Depends(get_current_user)
) -> TokenData:
    """
    依赖注入：要求管理员权限
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permission required"
        )
    return current_user

async def require_employee_or_admin(
    current_user: TokenData = Depends(get_current_user)
) -> TokenData:
    """
    依赖注入：要求员工或管理员权限
    """
    if current_user.role not in ["admin", "employee"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee or admin permission required"
        )
    return current_user

