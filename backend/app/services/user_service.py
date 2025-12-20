"""
用户服务：处理用户相关的数据库操作
"""
import uuid
from datetime import datetime
from typing import Optional, List
from fastapi import HTTPException, status

from app.services.db.postgres import get_conn
from app.models.user import (
    UserCreate, UserUpdate, UserInDB, UserResponse, UserRole
)
from app.utils.auth import hash_password, verify_password

def generate_user_id() -> str:
    """生成用户ID"""
    return f"user_{uuid.uuid4().hex[:12]}"

def create_user(user_data: UserCreate) -> UserResponse:
    """创建新用户"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 检查用户名是否已存在
            cur.execute(
                "SELECT id FROM users WHERE username = %s",
                (user_data.username,)
            )
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already exists"
                )
            
            # 检查邮箱是否已存在（如果提供）
            if user_data.email:
                cur.execute(
                    "SELECT id FROM users WHERE email = %s",
                    (user_data.email,)
                )
                if cur.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email already exists"
                    )
            
            # 创建用户
            user_id = generate_user_id()
            password_hash = hash_password(user_data.password)
            
            cur.execute("""
                INSERT INTO users (
                    id, username, password_hash, email, role,
                    display_name, phone, department, company, is_active
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, username, email, role, display_name, phone,
                          department, company, avatar_url, is_active,
                          last_login_at, created_at, updated_at
            """, (
                user_id, user_data.username, password_hash, user_data.email,
                user_data.role, user_data.display_name, user_data.phone,
                user_data.department, user_data.company, True
            ))
            
            row = cur.fetchone()
            conn.commit()
            
            return UserResponse(
                id=row[0],
                username=row[1],
                email=row[2],
                role=row[3],
                display_name=row[4],
                phone=row[5],
                department=row[6],
                company=row[7],
                avatar_url=row[8],
                is_active=row[9],
                last_login_at=row[10],
                created_at=row[11]
            )

def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    """验证用户登录"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, username, password_hash, email, role,
                       display_name, phone, department, company,
                       avatar_url, is_active, last_login_at,
                       created_at, updated_at
                FROM users
                WHERE username = %s
            """, (username,))
            
            row = cur.fetchone()
            if not row:
                return None
            
            # 验证密码
            if not verify_password(password, row[2]):
                return None
            
            # 检查用户是否激活
            if not row[10]:  # is_active
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is disabled"
                )
            
            # 更新最后登录时间
            cur.execute(
                "UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = %s",
                (row[0],)
            )
            conn.commit()
            
            return UserInDB(
                id=row[0],
                username=row[1],
                password_hash=row[2],
                email=row[3],
                role=row[4],
                display_name=row[5],
                phone=row[6],
                department=row[7],
                company=row[8],
                avatar_url=row[9],
                is_active=row[10],
                last_login_at=row[11] or datetime.now(),
                created_at=row[12],
                updated_at=row[13]
            )

def get_user_by_id(user_id: str) -> Optional[UserResponse]:
    """根据ID获取用户"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, username, email, role, display_name, phone,
                       department, company, avatar_url, is_active,
                       last_login_at, created_at
                FROM users
                WHERE id = %s
            """, (user_id,))
            
            row = cur.fetchone()
            if not row:
                return None
            
            return UserResponse(
                id=row[0],
                username=row[1],
                email=row[2],
                role=row[3],
                display_name=row[4],
                phone=row[5],
                department=row[6],
                company=row[7],
                avatar_url=row[8],
                is_active=row[9],
                last_login_at=row[10],
                created_at=row[11]
            )

def get_all_users(role: Optional[UserRole] = None) -> List[UserResponse]:
    """获取所有用户（管理员功能）"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            if role:
                cur.execute("""
                    SELECT id, username, email, role, display_name, phone,
                           department, company, avatar_url, is_active,
                           last_login_at, created_at
                    FROM users
                    WHERE role = %s
                    ORDER BY created_at DESC
                """, (role,))
            else:
                cur.execute("""
                    SELECT id, username, email, role, display_name, phone,
                           department, company, avatar_url, is_active,
                           last_login_at, created_at
                    FROM users
                    ORDER BY created_at DESC
                """)
            
            rows = cur.fetchall()
            return [
                UserResponse(
                    id=row[0],
                    username=row[1],
                    email=row[2],
                    role=row[3],
                    display_name=row[4],
                    phone=row[5],
                    department=row[6],
                    company=row[7],
                    avatar_url=row[8],
                    is_active=row[9],
                    last_login_at=row[10],
                    created_at=row[11]
                )
                for row in rows
            ]

def update_user(user_id: str, update_data: UserUpdate) -> UserResponse:
    """更新用户信息"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 构建动态更新语句
            update_fields = []
            params = []
            
            if update_data.email is not None:
                update_fields.append("email = %s")
                params.append(update_data.email)
            if update_data.display_name is not None:
                update_fields.append("display_name = %s")
                params.append(update_data.display_name)
            if update_data.phone is not None:
                update_fields.append("phone = %s")
                params.append(update_data.phone)
            if update_data.department is not None:
                update_fields.append("department = %s")
                params.append(update_data.department)
            if update_data.company is not None:
                update_fields.append("company = %s")
                params.append(update_data.company)
            if update_data.is_active is not None:
                update_fields.append("is_active = %s")
                params.append(update_data.is_active)
            
            if not update_fields:
                # 没有字段需要更新
                user = get_user_by_id(user_id)
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found"
                    )
                return user
            
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.append(user_id)
            
            query = f"""
                UPDATE users
                SET {', '.join(update_fields)}
                WHERE id = %s
                RETURNING id, username, email, role, display_name, phone,
                          department, company, avatar_url, is_active,
                          last_login_at, created_at
            """
            
            cur.execute(query, params)
            row = cur.fetchone()
            
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            conn.commit()
            
            return UserResponse(
                id=row[0],
                username=row[1],
                email=row[2],
                role=row[3],
                display_name=row[4],
                phone=row[5],
                department=row[6],
                company=row[7],
                avatar_url=row[8],
                is_active=row[9],
                last_login_at=row[10],
                created_at=row[11]
            )

def change_password(user_id: str, old_password: str, new_password: str) -> bool:
    """修改密码"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 获取当前密码哈希
            cur.execute(
                "SELECT password_hash FROM users WHERE id = %s",
                (user_id,)
            )
            row = cur.fetchone()
            
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # 验证旧密码
            if not verify_password(old_password, row[0]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Incorrect old password"
                )
            
            # 更新为新密码
            new_hash = hash_password(new_password)
            cur.execute(
                "UPDATE users SET password_hash = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (new_hash, user_id)
            )
            conn.commit()
            
            return True

def delete_user(user_id: str) -> bool:
    """删除用户（硬删除）"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            deleted = cur.rowcount > 0
            conn.commit()
            return deleted

