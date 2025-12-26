-- 初始化 V3 Prompt 模板到数据库
-- 将 project_info_v3, requirements_v1, bid_response_v1 的 prompt 内容导入到 prompt_templates 表

-- 如果表不存在，先创建（通常已经由 prompt 管理系统创建）
CREATE TABLE IF NOT EXISTS prompt_templates (
    id TEXT PRIMARY KEY,
    module TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    content TEXT NOT NULL,
    version INT NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    deprecated BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT,
    UNIQUE (module, version)
);

-- 说明：
-- 实际的 prompt 内容需要从文件中读取
-- 这里提供占位符，需要手动替换或通过应用程序导入

-- 删除可能存在的旧记录（防止重复）
DELETE FROM prompt_templates WHERE module IN ('project_info_v3', 'requirements_v1', 'bid_response_v1');

-- 插入 project_info_v3 prompt
-- 注意：content 字段需要从 backend/app/works/tender/prompts/project_info_v3.md 读取
INSERT INTO prompt_templates (
    id, module, name, description, content, version, is_active, deprecated, created_at, updated_at
) VALUES (
    'prompt_project_info_v3_001',
    'project_info_v3',
    '招标信息提取 V3',
    '从招标文件中提取六大类结构化信息（项目概况【含范围、进度、保证金】、投标人资格、评审与评分、商务条款、技术要求、文件编制）',
    '<<FILE_CONTENT: backend/app/works/tender/prompts/project_info_v3.md>>',
    1,
    TRUE,
    FALSE,
    NOW(),
    NOW()
);

-- 插入 requirements_v1 prompt
INSERT INTO prompt_templates (
    id, module, name, description, content, version, is_active, deprecated, created_at, updated_at
) VALUES (
    'prompt_requirements_v1_001',
    'requirements_v1',
    '招标要求抽取 V1',
    '从招标文件中抽取结构化的招标要求（基准条款库），包括7个维度：资格要求、技术要求、商务要求、价格要求、文档结构、进度质量、其他要求',
    '<<FILE_CONTENT: backend/app/works/tender/prompts/requirements_v1.md>>',
    1,
    TRUE,
    FALSE,
    NOW(),
    NOW()
);

-- 插入 bid_response_v1 prompt
INSERT INTO prompt_templates (
    id, module, name, description, content, version, is_active, deprecated, created_at, updated_at
) VALUES (
    'prompt_bid_response_v1_001',
    'bid_response_v1',
    '投标响应要素抽取 V1',
    '从投标文件中抽取结构化的响应要素，包括7个维度：资格响应、技术响应、商务响应、价格响应、文档结构、进度质量、其他响应',
    '<<FILE_CONTENT: backend/app/works/tender/prompts/bid_response_v1.md>>',
    1,
    TRUE,
    FALSE,
    NOW(),
    NOW()
);

-- 标记旧版 prompts 为已弃用
UPDATE prompt_templates 
SET 
    description = '[旧版 - 已弃用] ' || description,
    deprecated = TRUE
WHERE module IN ('project_info', 'review') 
  AND description NOT LIKE '[旧版%'
  AND description NOT LIKE '%已弃用%';

-- 验证结果
SELECT 
    module, 
    name, 
    version, 
    is_active,
    deprecated,
    LENGTH(content) as content_length,
    created_at
FROM prompt_templates
WHERE module IN ('project_info_v3', 'requirements_v1', 'bid_response_v1', 'project_info', 'review')
ORDER BY deprecated ASC, module ASC;

