-- 创建用户表
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100),
    role VARCHAR(20) NOT NULL DEFAULT 'customer',  -- 'admin', 'employee', 'customer'
    display_name VARCHAR(100),
    avatar_url VARCHAR(500),
    phone VARCHAR(20),
    department VARCHAR(100),  -- 部门（员工）
    company VARCHAR(100),  -- 公司（客户）
    is_active BOOLEAN DEFAULT TRUE,
    last_login_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_role CHECK (role IN ('admin', 'employee', 'customer'))
);

-- 创建索引
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active);

-- 扩展知识库表：添加所有者字段
ALTER TABLE knowledge_bases ADD COLUMN IF NOT EXISTS owner_id VARCHAR(36);
ALTER TABLE knowledge_bases ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT FALSE;
ALTER TABLE knowledge_bases ADD COLUMN IF NOT EXISTS share_mode VARCHAR(20) DEFAULT 'private';
-- share_mode: 'private' (仅自己), 'shared' (指定用户), 'public' (所有人)

CREATE INDEX IF NOT EXISTS idx_kb_owner ON knowledge_bases(owner_id);
CREATE INDEX IF NOT EXISTS idx_kb_public ON knowledge_bases(is_public);

-- 知识库共享表
CREATE TABLE IF NOT EXISTS kb_shares (
    id VARCHAR(36) PRIMARY KEY,
    kb_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    permission VARCHAR(20) DEFAULT 'read',  -- 'read', 'write'
    granted_by VARCHAR(36),  -- 授权人
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,  -- 可选：过期时间
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(kb_id, user_id)
);

CREATE INDEX idx_kb_shares_user ON kb_shares(user_id);
CREATE INDEX idx_kb_shares_kb ON kb_shares(kb_id);

-- 创建默认管理员用户
-- 密码: admin123 (请在生产环境中修改)
INSERT INTO users (id, username, password_hash, email, role, display_name, is_active)
VALUES (
    'admin-default-001',
    'admin',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzpLhJ3K8.',  -- admin123
    'admin@localgpt.com',
    'admin',
    '系统管理员',
    TRUE
)
ON CONFLICT (username) DO NOTHING;

-- 注释说明
COMMENT ON TABLE users IS '用户表：存储所有用户信息和角色';
COMMENT ON TABLE kb_shares IS '知识库共享表：管理知识库的访问权限';
COMMENT ON COLUMN users.role IS '用户角色：admin(管理员), employee(员工), customer(客户)';
COMMENT ON COLUMN kb_shares.permission IS '权限类型：read(只读), write(读写)';

