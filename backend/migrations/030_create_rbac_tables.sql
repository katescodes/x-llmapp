-- 030_create_rbac_tables.sql
-- 创建 RBAC（基于角色的访问控制）权限管理表

-- ==================== 权限项表 ====================
-- 定义系统中所有的权限点（功能点）
CREATE TABLE IF NOT EXISTS permissions (
    id VARCHAR(36) PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,              -- 权限代码（唯一标识）如 'chat.create'
    name VARCHAR(100) NOT NULL,                      -- 权限名称
    description TEXT,                                -- 权限描述
    module VARCHAR(50) NOT NULL,                     -- 所属模块：chat, kb, tender, declare, recordings, system
    parent_code VARCHAR(100),                        -- 父权限代码（用于二级权限）
    resource_type VARCHAR(50),                       -- 资源类型：menu, api, button, data
    display_order INTEGER DEFAULT 0,                 -- 显示顺序
    is_active BOOLEAN DEFAULT TRUE,                  -- 是否启用
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_code) REFERENCES permissions(code) ON DELETE SET NULL
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_permissions_module ON permissions(module);
CREATE INDEX IF NOT EXISTS idx_permissions_parent ON permissions(parent_code);
CREATE INDEX IF NOT EXISTS idx_permissions_active ON permissions(is_active);

-- ==================== 角色表 ====================
-- 定义系统中的角色（角色组）
CREATE TABLE IF NOT EXISTS roles (
    id VARCHAR(36) PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,                -- 角色代码：admin, manager, employee, customer
    name VARCHAR(100) NOT NULL,                      -- 角色名称
    description TEXT,                                -- 角色描述
    is_system BOOLEAN DEFAULT FALSE,                 -- 是否系统内置角色（不可删除）
    is_active BOOLEAN DEFAULT TRUE,                  -- 是否启用
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_roles_code ON roles(code);
CREATE INDEX IF NOT EXISTS idx_roles_active ON roles(is_active);

-- ==================== 角色-权限关联表 ====================
-- 角色拥有哪些权限
CREATE TABLE IF NOT EXISTS role_permissions (
    id VARCHAR(36) PRIMARY KEY,
    role_id VARCHAR(36) NOT NULL,
    permission_id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
    FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE,
    UNIQUE(role_id, permission_id)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_role_permissions_role ON role_permissions(role_id);
CREATE INDEX IF NOT EXISTS idx_role_permissions_permission ON role_permissions(permission_id);

-- ==================== 用户-角色关联表 ====================
-- 用户拥有哪些角色（支持一个用户多个角色）
CREATE TABLE IF NOT EXISTS user_roles (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    role_id VARCHAR(36) NOT NULL,
    granted_by VARCHAR(36),                          -- 授予人
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,                            -- 可选：过期时间
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
    FOREIGN KEY (granted_by) REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE(user_id, role_id)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_role ON user_roles(role_id);

-- ==================== 数据权限表 ====================
-- 记录用户可以访问的数据范围
-- data_scope: all(全部数据), dept(本部门), self(仅自己), custom(自定义)
CREATE TABLE IF NOT EXISTS data_permissions (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,              -- 资源类型：chat_session, kb, tender_project, recording 等
    data_scope VARCHAR(20) NOT NULL DEFAULT 'self',  -- 数据范围
    custom_scope_json JSONB,                         -- 自定义范围（JSON格式，存储具体的资源ID列表等）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, resource_type)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_data_permissions_user ON data_permissions(user_id);
CREATE INDEX IF NOT EXISTS idx_data_permissions_resource ON data_permissions(resource_type);

-- ==================== 用户表扩展 ====================
-- 为现有 users 表添加权限相关字段
ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS data_scope VARCHAR(20) DEFAULT 'self';  -- 默认数据权限范围

-- 为现有数据表添加 owner_id 字段（如果还没有）
ALTER TABLE chat_sessions 
    ADD COLUMN IF NOT EXISTS owner_id VARCHAR(36);

-- 为 owner_id 创建索引
CREATE INDEX IF NOT EXISTS idx_chat_sessions_owner ON chat_sessions(owner_id);

-- 对于 tender_projects（如果存在）
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'tender_projects') THEN
        ALTER TABLE tender_projects ADD COLUMN IF NOT EXISTS owner_id VARCHAR(36);
        CREATE INDEX IF NOT EXISTS idx_tender_projects_owner ON tender_projects(owner_id);
    END IF;
END $$;

-- 对于 declare_projects（如果存在）
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'declare_projects') THEN
        ALTER TABLE declare_projects ADD COLUMN IF NOT EXISTS owner_id VARCHAR(36);
        CREATE INDEX IF NOT EXISTS idx_declare_projects_owner ON declare_projects(owner_id);
    END IF;
END $$;

-- ==================== 插入系统内置角色 ====================
INSERT INTO roles (id, code, name, description, is_system, is_active)
VALUES 
    ('role_admin', 'admin', '系统管理员', '拥有所有权限，可以管理用户、角色、权限', TRUE, TRUE),
    ('role_manager', 'manager', '部门经理', '可以管理本部门数据和员工', TRUE, TRUE),
    ('role_employee', 'employee', '普通员工', '可以使用基本功能，访问自己的数据', TRUE, TRUE),
    ('role_customer', 'customer', '客户', '仅能访问自己的数据，功能受限', TRUE, TRUE)
ON CONFLICT (id) DO NOTHING;

-- ==================== 插入系统权限项 ====================
-- 一级权限：模块权限
INSERT INTO permissions (id, code, name, description, module, parent_code, resource_type, display_order, is_active)
VALUES 
    -- 对话模块
    ('perm_chat', 'chat', '对话管理', '对话相关功能', 'chat', NULL, 'menu', 1, TRUE),
    ('perm_chat_create', 'chat.create', '创建对话', '创建新对话会话', 'chat', 'chat', 'api', 1, TRUE),
    ('perm_chat_view', 'chat.view', '查看对话', '查看对话列表和内容', 'chat', 'chat', 'api', 2, TRUE),
    ('perm_chat_delete', 'chat.delete', '删除对话', '删除对话会话', 'chat', 'chat', 'api', 3, TRUE),
    ('perm_chat_export', 'chat.export', '导出对话', '导出对话记录', 'chat', 'chat', 'button', 4, TRUE),
    
    -- 知识库模块
    ('perm_kb', 'kb', '知识库管理', '知识库相关功能', 'kb', NULL, 'menu', 2, TRUE),
    ('perm_kb_create', 'kb.create', '创建知识库', '创建新知识库', 'kb', 'kb', 'api', 1, TRUE),
    ('perm_kb_view', 'kb.view', '查看知识库', '查看知识库列表和内容', 'kb', 'kb', 'api', 2, TRUE),
    ('perm_kb_edit', 'kb.edit', '编辑知识库', '编辑知识库信息', 'kb', 'kb', 'api', 3, TRUE),
    ('perm_kb_delete', 'kb.delete', '删除知识库', '删除知识库', 'kb', 'kb', 'api', 4, TRUE),
    ('perm_kb_upload', 'kb.upload', '上传文档', '向知识库上传文档', 'kb', 'kb', 'button', 5, TRUE),
    ('perm_kb_share', 'kb.share', '共享知识库', '共享知识库给其他用户', 'kb', 'kb', 'button', 6, TRUE),
    
    -- 招投标模块
    ('perm_tender', 'tender', '招投标管理', '招投标相关功能', 'tender', NULL, 'menu', 3, TRUE),
    ('perm_tender_create', 'tender.create', '创建项目', '创建招投标项目', 'tender', 'tender', 'api', 1, TRUE),
    ('perm_tender_view', 'tender.view', '查看项目', '查看招投标项目', 'tender', 'tender', 'api', 2, TRUE),
    ('perm_tender_edit', 'tender.edit', '编辑项目', '编辑招投标项目', 'tender', 'tender', 'api', 3, TRUE),
    ('perm_tender_delete', 'tender.delete', '删除项目', '删除招投标项目', 'tender', 'tender', 'api', 4, TRUE),
    ('perm_tender_export', 'tender.export', '导出文档', '导出招投标文档', 'tender', 'tender', 'button', 5, TRUE),
    ('perm_tender_template', 'tender.template', '模板管理', '管理招投标模板', 'tender', 'tender', 'button', 6, TRUE),
    ('perm_tender_userdoc', 'tender.userdoc', '用户文档管理', '管理招投标项目的用户文档', 'tender', 'tender', 'api', 7, TRUE),
    
    -- 申报书模块
    ('perm_declare', 'declare', '申报书管理', '申报书相关功能', 'declare', NULL, 'menu', 4, TRUE),
    ('perm_declare_create', 'declare.create', '创建申报书', '创建申报书项目', 'declare', 'declare', 'api', 1, TRUE),
    ('perm_declare_view', 'declare.view', '查看申报书', '查看申报书项目', 'declare', 'declare', 'api', 2, TRUE),
    ('perm_declare_edit', 'declare.edit', '编辑申报书', '编辑申报书项目', 'declare', 'declare', 'api', 3, TRUE),
    ('perm_declare_delete', 'declare.delete', '删除申报书', '删除申报书项目', 'declare', 'declare', 'api', 4, TRUE),
    ('perm_declare_export', 'declare.export', '导出申报书', '导出申报书文档', 'declare', 'declare', 'button', 5, TRUE),
    
    -- 录音模块
    ('perm_recording', 'recording', '录音管理', '录音相关功能', 'recordings', NULL, 'menu', 5, TRUE),
    ('perm_recording_create', 'recording.create', '创建录音', '录制或上传录音', 'recordings', 'recording', 'api', 1, TRUE),
    ('perm_recording_view', 'recording.view', '查看录音', '查看录音列表', 'recordings', 'recording', 'api', 2, TRUE),
    ('perm_recording_delete', 'recording.delete', '删除录音', '删除录音记录', 'recordings', 'recording', 'api', 3, TRUE),
    ('perm_recording_import', 'recording.import', '导入知识库', '将录音导入知识库', 'recordings', 'recording', 'button', 4, TRUE),
    
    -- 系统设置模块
    ('perm_system', 'system', '系统设置', '系统设置相关功能', 'system', NULL, 'menu', 6, TRUE),
    ('perm_system_model', 'system.model', 'LLM模型配置', '配置LLM模型参数', 'system', 'system', 'menu', 1, TRUE),
    ('perm_system_embedding', 'system.embedding', 'Embedding配置', '配置向量嵌入模型', 'system', 'system', 'menu', 2, TRUE),
    ('perm_system_settings', 'system.settings', '应用设置', '配置应用系统参数', 'system', 'system', 'menu', 3, TRUE),
    ('perm_system_asr', 'system.asr', 'ASR配置', '配置语音识别服务', 'system', 'system', 'menu', 4, TRUE),
    ('perm_system_prompt', 'system.prompt', 'Prompt管理', '管理系统提示词模板', 'system', 'system', 'menu', 5, TRUE),
    ('perm_system_category', 'system.category', '分类管理', '管理知识库分类', 'system', 'system', 'menu', 6, TRUE),
    
    -- 权限管理模块（新增）
    ('perm_permission', 'permission', '权限管理', '权限管理相关功能', 'system', 'system', 'menu', 7, TRUE),
    ('perm_permission_user', 'permission.user', '用户管理', '管理系统用户', 'system', 'permission', 'menu', 1, TRUE),
    ('perm_permission_user_create', 'permission.user.create', '创建用户', '创建新用户', 'system', 'permission.user', 'api', 1, TRUE),
    ('perm_permission_user_view', 'permission.user.view', '查看用户', '查看用户列表', 'system', 'permission.user', 'api', 2, TRUE),
    ('perm_permission_user_edit', 'permission.user.edit', '编辑用户', '编辑用户信息', 'system', 'permission.user', 'api', 3, TRUE),
    ('perm_permission_user_delete', 'permission.user.delete', '删除用户', '删除用户', 'system', 'permission.user', 'api', 4, TRUE),
    ('perm_permission_user_assign_role', 'permission.user.assign_role', '分配角色', '为用户分配角色', 'system', 'permission.user', 'button', 5, TRUE),
    
    ('perm_permission_role', 'permission.role', '角色管理', '管理系统角色', 'system', 'permission', 'menu', 2, TRUE),
    ('perm_permission_role_create', 'permission.role.create', '创建角色', '创建新角色', 'system', 'permission.role', 'api', 1, TRUE),
    ('perm_permission_role_view', 'permission.role.view', '查看角色', '查看角色列表', 'system', 'permission.role', 'api', 2, TRUE),
    ('perm_permission_role_edit', 'permission.role.edit', '编辑角色', '编辑角色信息', 'system', 'permission.role', 'api', 3, TRUE),
    ('perm_permission_role_delete', 'permission.role.delete', '删除角色', '删除角色', 'system', 'permission.role', 'api', 4, TRUE),
    ('perm_permission_role_assign_perm', 'permission.role.assign_perm', '分配权限', '为角色分配权限', 'system', 'permission.role', 'button', 5, TRUE),
    
    ('perm_permission_item', 'permission.item', '权限项管理', '管理权限项', 'system', 'permission', 'menu', 3, TRUE),
    ('perm_permission_item_view', 'permission.item.view', '查看权限项', '查看权限项列表', 'system', 'permission.item', 'api', 1, TRUE),
    ('perm_permission_item_edit', 'permission.item.edit', '编辑权限项', '编辑权限项信息', 'system', 'permission.item', 'api', 2, TRUE)
ON CONFLICT (id) DO NOTHING;

-- ==================== 为系统角色分配默认权限 ====================
-- 管理员：拥有所有权限
INSERT INTO role_permissions (id, role_id, permission_id)
SELECT 
    md5('rp_admin_' || p.id)::uuid,
    'role_admin',
    p.id
FROM permissions p
WHERE p.is_active = TRUE
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 部门经理：除了权限管理和系统设置外的所有功能
INSERT INTO role_permissions (id, role_id, permission_id)
SELECT 
    md5('rp_manager_' || p.id)::uuid,
    'role_manager',
    p.id
FROM permissions p
WHERE p.is_active = TRUE 
    AND p.code NOT LIKE 'permission.%'
    AND p.code NOT LIKE 'system.%'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 普通员工：基本功能权限
INSERT INTO role_permissions (id, role_id, permission_id)
SELECT 
    md5('rp_employee_' || p.id)::uuid,
    'role_employee',
    p.id
FROM permissions p
WHERE p.is_active = TRUE 
    AND p.code IN (
        'chat', 'chat.create', 'chat.view', 'chat.delete', 'chat.export',
        'kb', 'kb.view', 'kb.upload',
        'tender', 'tender.create', 'tender.view', 'tender.edit', 'tender.delete', 'tender.export', 'tender.userdoc',
        'declare', 'declare.create', 'declare.view', 'declare.edit', 'declare.delete', 'declare.export',
        'recording', 'recording.create', 'recording.view', 'recording.delete', 'recording.import'
    )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 客户：仅查看和基本操作
INSERT INTO role_permissions (id, role_id, permission_id)
SELECT 
    md5('rp_customer_' || p.id)::uuid,
    'role_customer',
    p.id
FROM permissions p
WHERE p.is_active = TRUE 
    AND p.code IN (
        'chat', 'chat.create', 'chat.view',
        'kb', 'kb.view',
        'recording', 'recording.create', 'recording.view'
    )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- ==================== 为现有用户分配角色 ====================
-- 将现有用户根据 role 字段分配对应的系统角色
INSERT INTO user_roles (id, user_id, role_id)
SELECT 
    md5('ur_' || u.id || '_' || r.id)::uuid,
    u.id,
    r.id
FROM users u
JOIN roles r ON (
    (u.role = 'admin' AND r.code = 'admin') OR
    (u.role = 'employee' AND r.code = 'employee') OR
    (u.role = 'customer' AND r.code = 'customer')
)
ON CONFLICT (user_id, role_id) DO NOTHING;

-- ==================== 创建视图：简化权限查询 ====================
-- 用户权限视图：显示每个用户拥有的所有权限
CREATE OR REPLACE VIEW user_permissions_view AS
SELECT DISTINCT
    u.id AS user_id,
    u.username,
    r.code AS role_code,
    r.name AS role_name,
    p.code AS permission_code,
    p.name AS permission_name,
    p.module,
    p.resource_type
FROM users u
JOIN user_roles ur ON u.id = ur.user_id
JOIN roles r ON ur.role_id = r.id
JOIN role_permissions rp ON r.id = rp.role_id
JOIN permissions p ON rp.permission_id = p.id
WHERE u.is_active = TRUE 
    AND r.is_active = TRUE 
    AND p.is_active = TRUE;

-- 用户模块权限视图：按模块汇总用户权限
CREATE OR REPLACE VIEW user_module_permissions_view AS
SELECT 
    user_id,
    username,
    module,
    array_agg(DISTINCT permission_code ORDER BY permission_code) AS permissions
FROM user_permissions_view
GROUP BY user_id, username, module;

