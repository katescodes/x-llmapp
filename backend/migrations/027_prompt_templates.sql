-- Prompt模板管理表
CREATE TABLE IF NOT EXISTS prompt_templates (
    id TEXT PRIMARY KEY,
    module TEXT NOT NULL,  -- 模块名称：project_info, risks, directory, review
    name TEXT NOT NULL,    -- 显示名称
    description TEXT,      -- 描述
    content TEXT NOT NULL, -- Prompt内容（Markdown格式）
    version INT DEFAULT 1, -- 版本号
    is_active BOOLEAN DEFAULT TRUE, -- 是否激活
    created_by TEXT,
    updated_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_prompt_templates_module ON prompt_templates(module);
CREATE INDEX IF NOT EXISTS idx_prompt_templates_active ON prompt_templates(is_active);

-- Prompt变更历史表
CREATE TABLE IF NOT EXISTS prompt_history (
    id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL,
    content TEXT NOT NULL,
    version INT NOT NULL,
    changed_by TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    change_note TEXT,
    FOREIGN KEY (prompt_id) REFERENCES prompt_templates(id)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_prompt_history_prompt_id ON prompt_history(prompt_id);
CREATE INDEX IF NOT EXISTS idx_prompt_history_version ON prompt_history(prompt_id, version);

-- 插入初始数据（从文件导入）
-- 注意：这些INSERT语句需要在后续执行时填充实际的prompt内容

COMMENT ON TABLE prompt_templates IS 'Prompt模板管理表，存储各个模块的提示词';
COMMENT ON TABLE prompt_history IS 'Prompt变更历史表，记录每次修改';

