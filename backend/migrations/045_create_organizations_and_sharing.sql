-- =====================================================
-- 迁移脚本: 045_create_organizations_and_sharing.sql
-- 目的: 实现资源共享功能 - 创建企业表和添加共享字段
-- 日期: 2026-01-10
-- =====================================================

-- ===== 1. 创建企业表 =====
CREATE TABLE IF NOT EXISTS organizations (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 创建默认企业（单企业部署）
INSERT INTO organizations (id, name) 
VALUES ('org_default', '默认企业')
ON CONFLICT (id) DO NOTHING;

-- ===== 2. 用户表添加企业关联 =====
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS organization_id VARCHAR(255) REFERENCES organizations(id);

-- 将现有用户绑定到默认企业
UPDATE users 
SET organization_id = 'org_default' 
WHERE organization_id IS NULL;

-- ===== 3. 格式模板表添加共享字段 =====
ALTER TABLE format_templates 
ADD COLUMN IF NOT EXISTS scope VARCHAR(50) DEFAULT 'private',
ADD COLUMN IF NOT EXISTS organization_id VARCHAR(255);

-- 初始化现有模板：设为私有，继承owner的企业ID
UPDATE format_templates t
SET 
    scope = 'private',
    organization_id = (SELECT organization_id FROM users WHERE id = t.owner_id)
WHERE scope IS NULL;

-- ===== 4. 自定义规则包表添加共享字段 =====
ALTER TABLE tender_rule_packs 
ADD COLUMN IF NOT EXISTS scope VARCHAR(50) DEFAULT 'private',
ADD COLUMN IF NOT EXISTS organization_id VARCHAR(255);

-- 初始化现有规则包（通过project_id间接获取owner的企业ID）
UPDATE tender_rule_packs rp
SET 
    scope = 'private',
    organization_id = (
        SELECT u.organization_id 
        FROM tender_projects p 
        JOIN users u ON p.owner_id = u.id 
        WHERE p.id = rp.project_id
    )
WHERE scope IS NULL AND project_id IS NOT NULL;

-- 对于没有project_id的规则包，设为默认企业
UPDATE tender_rule_packs
SET organization_id = 'org_default'
WHERE organization_id IS NULL;

-- ===== 5. 知识库表添加共享字段 =====
ALTER TABLE knowledge_bases 
ADD COLUMN IF NOT EXISTS scope VARCHAR(50) DEFAULT 'private',
ADD COLUMN IF NOT EXISTS organization_id VARCHAR(255);

-- 初始化现有知识库
UPDATE knowledge_bases t
SET 
    scope = 'private',
    organization_id = (SELECT organization_id FROM users WHERE id = t.owner_id)
WHERE scope IS NULL;

-- ===== 6. 用户文档表添加共享字段 =====
ALTER TABLE tender_user_documents 
ADD COLUMN IF NOT EXISTS scope VARCHAR(50) DEFAULT 'private',
ADD COLUMN IF NOT EXISTS organization_id VARCHAR(255);

-- 初始化现有用户文档
UPDATE tender_user_documents t
SET 
    scope = 'private',
    organization_id = (SELECT organization_id FROM users WHERE id = t.owner_id)
WHERE scope IS NULL;

-- ===== 7. 添加索引优化查询性能 =====
CREATE INDEX IF NOT EXISTS idx_users_organization ON users(organization_id);
CREATE INDEX IF NOT EXISTS idx_format_templates_scope ON format_templates(scope);
CREATE INDEX IF NOT EXISTS idx_format_templates_org ON format_templates(organization_id);
CREATE INDEX IF NOT EXISTS idx_tender_rule_packs_scope ON tender_rule_packs(scope);
CREATE INDEX IF NOT EXISTS idx_tender_rule_packs_org ON tender_rule_packs(organization_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_bases_scope ON knowledge_bases(scope);
CREATE INDEX IF NOT EXISTS idx_knowledge_bases_org ON knowledge_bases(organization_id);
CREATE INDEX IF NOT EXISTS idx_tender_user_documents_scope ON tender_user_documents(scope);
CREATE INDEX IF NOT EXISTS idx_tender_user_documents_org ON tender_user_documents(organization_id);

-- ===== 8. 添加新的权限 =====
INSERT INTO permissions (id, code, name, description, module) VALUES
('perm_org_view', 'organization.view', '查看企业信息', '可以查看企业基本信息和成员列表', 'organization'),
('perm_org_edit', 'organization.edit', '编辑企业信息', '可以修改企业名称等基本信息', 'organization'),
('perm_org_manage', 'organization.manage', '管理企业', '可以创建、删除企业（多租户模式）', 'organization'),
('perm_org_member', 'organization.member', '管理企业成员', '可以绑定/移除企业成员', 'organization')
ON CONFLICT (id) DO NOTHING;

-- ===== 9. 分配权限给角色 =====
-- 管理员: 查看、编辑、管理成员
INSERT INTO role_permissions (id, role_id, permission_id) VALUES
(gen_random_uuid()::text, 'role_admin', 'perm_org_view'),
(gen_random_uuid()::text, 'role_admin', 'perm_org_edit'),
(gen_random_uuid()::text, 'role_admin', 'perm_org_member')
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 员工: 只能查看
INSERT INTO role_permissions (id, role_id, permission_id) VALUES
(gen_random_uuid()::text, 'role_employee', 'perm_org_view')
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- =====================================================
-- 迁移完成
-- =====================================================
