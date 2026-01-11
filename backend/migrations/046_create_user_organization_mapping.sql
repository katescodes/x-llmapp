-- 创建用户-企业多对多关联表
-- 用于支持一个用户可以属于多个企业

-- 创建用户-企业关联表
CREATE TABLE IF NOT EXISTS user_organization_mappings (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    organization_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, organization_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
);

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_user_org_user_id ON user_organization_mappings(user_id);
CREATE INDEX IF NOT EXISTS idx_user_org_org_id ON user_organization_mappings(organization_id);

-- 迁移现有数据：将 users 表中的 organization_id 迁移到关联表
INSERT INTO user_organization_mappings (user_id, organization_id)
SELECT id, organization_id
FROM users
WHERE organization_id IS NOT NULL
ON CONFLICT (user_id, organization_id) DO NOTHING;

-- 注意：保留 users.organization_id 字段用于向后兼容
-- 如果需要完全迁移，可以在后续版本中删除该字段
-- ALTER TABLE users DROP COLUMN organization_id;

-- 添加注释
COMMENT ON TABLE user_organization_mappings IS '用户-企业多对多关联表';
COMMENT ON COLUMN user_organization_mappings.user_id IS '用户ID';
COMMENT ON COLUMN user_organization_mappings.organization_id IS '企业ID';
COMMENT ON COLUMN user_organization_mappings.created_at IS '关联创建时间';
