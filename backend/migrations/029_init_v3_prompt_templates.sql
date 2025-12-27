-- 注意：此迁移文件已废弃，请使用 scripts/init_prompts.py 脚本初始化Prompt数据

-- 初始化 Prompt 模板数据
-- 新版模块：project_info_v3, requirements_v1, bid_response_v1, risks_v2, directory_v2, review_v2

-- 1. 招标信息提取 V3 (project_info_v3)
INSERT INTO prompt_templates (
    id, module, name, description, content, version, is_active, created_at, updated_at
)
SELECT
    'prompt_project_info_v3_001',
    'project_info_v3',
    '招标信息提取 V3',
    '从招标文件中提取九大类结构化信息（项目概况、范围与标段、进度与提交、投标人资格、评审与评分、商务条款、技术要求、文件编制、投标保证金）',
    pg_read_file('/path/to/backend/app/works/tender/prompts/project_info_v3.md')::text,
    1,
    TRUE,
    now(),
    now()
WHERE NOT EXISTS (
    SELECT 1 FROM prompt_templates WHERE module = 'project_info_v3' AND is_active = TRUE
);

-- 2. 招标要求抽取 V1 (requirements_v1)
INSERT INTO prompt_templates (
    id, module, name, description, content, version, is_active, created_at, updated_at
)
SELECT
    'prompt_requirements_v1_001',
    'requirements_v1',
    '招标要求抽取 V1',
    '从招标文件中抽取结构化的招标要求（基准条款库），包括7个维度：资格要求、技术要求、商务要求、价格要求、文档结构、进度质量、其他要求',
    pg_read_file('/path/to/backend/app/works/tender/prompts/requirements_v1.md')::text,
    1,
    TRUE,
    now(),
    now()
WHERE NOT EXISTS (
    SELECT 1 FROM prompt_templates WHERE module = 'requirements_v1' AND is_active = TRUE
);

-- 3. 投标响应要素抽取 V1 (bid_response_v1)
INSERT INTO prompt_templates (
    id, module, name, description, content, version, is_active, created_at, updated_at
)
SELECT
    'prompt_bid_response_v1_001',
    'bid_response_v1',
    '投标响应要素抽取 V1',
    '从投标文件中抽取结构化的响应要素，包括7个维度：资格响应、技术响应、商务响应、价格响应、文档结构、进度质量、其他响应',
    pg_read_file('/path/to/backend/app/works/tender/prompts/bid_response_v1.md')::text,
    1,
    TRUE,
    now(),
    now()
WHERE NOT EXISTS (
    SELECT 1 FROM prompt_templates WHERE module = 'bid_response_v1' AND is_active = TRUE
);

-- 可选：将旧版 prompt 标记为 deprecated（不删除，保留历史）
UPDATE prompt_templates 
SET description = '[旧版 - 已弃用] ' || description 
WHERE module IN ('project_info', 'review') 
  AND description NOT LIKE '[旧版%';

-- 验证插入结果
SELECT 
    module, 
    name, 
    version, 
    is_active,
    length(content) as content_length,
    created_at 
FROM prompt_templates 
WHERE module IN ('project_info_v3', 'requirements_v1', 'bid_response_v1')
ORDER BY module;

