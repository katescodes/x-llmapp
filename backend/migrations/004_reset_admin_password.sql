-- 重置admin用户密码为admin123
-- 使用正确的bcrypt hash

-- 删除旧的admin用户
DELETE FROM users WHERE username = 'admin';

-- 插入新的admin用户（密码：admin123）
-- bcrypt hash: $2b$12$S68.M9ETnMv6jFhaUzwUQeN0sRGcuZJteZaOujy/UNtvQWA9QRKRa
INSERT INTO users (
    id,
    username,
    password_hash,
    email,
    role,
    display_name,
    is_active,
    created_at,
    updated_at
) VALUES (
    'admin-user-001',
    'admin',
    '$2b$12$S68.M9ETnMv6jFhaUzwUQeN0sRGcuZJteZaOujy/UNtvQWA9QRKRa',
    'admin@example.com',
    'admin',
    '系统管理员',
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

-- 验证
SELECT 
    username,
    role,
    is_active,
    LEFT(password_hash, 20) as pwd_preview,
    LENGTH(password_hash) as pwd_len
FROM users 
WHERE username = 'admin';

