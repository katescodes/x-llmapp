#!/usr/bin/env python3
"""
创建默认管理员账号
"""
import sys
import uuid
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.db.postgres import get_conn
from app.utils.auth import hash_password

def create_admin():
    """创建默认管理员账号"""
    username = "admin"
    password = "admin123"  # 请在生产环境中修改
    email = "admin@example.com"
    display_name = "系统管理员"
    
    user_id = f"user_{uuid.uuid4().hex[:16]}"
    password_hash = hash_password(password)
    
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 检查是否已存在
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cur.fetchone():
                print(f"❌ 用户 '{username}' 已存在")
                return
            
            # 创建用户
            cur.execute("""
                INSERT INTO users 
                (id, username, password_hash, email, role, display_name, is_active, data_scope)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_id, username, password_hash, email, 'admin', display_name, True, 'all'))
            
            # 分配admin角色
            cur.execute("SELECT id FROM roles WHERE code = 'admin'")
            role_row = cur.fetchone()
            if role_row:
                role_id = role_row[0]
                ur_id = f"ur_{uuid.uuid4().hex[:16]}"
                cur.execute("""
                    INSERT INTO user_roles (id, user_id, role_id)
                    VALUES (%s, %s, %s)
                """, (ur_id, user_id, role_id))
            
            conn.commit()
            
            print("✅ 管理员账号创建成功！")
            print(f"   用户名: {username}")
            print(f"   密码: {password}")
            print(f"   邮箱: {email}")
            print("\n⚠️  请登录后立即修改密码！")

if __name__ == "__main__":
    try:
        create_admin()
    except Exception as e:
        print(f"\n❌ 创建失败: {e}")
        sys.exit(1)

