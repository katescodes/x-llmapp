-- 招标文件格式范本提取表
-- 用于存储从招标文件中提取的格式范本（投标函、授权书等）

CREATE TABLE IF NOT EXISTS tender_format_snippets (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL,
    source_file_id VARCHAR(255),
    norm_key VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL,
    start_block_id VARCHAR(64),
    end_block_id VARCHAR(64),
    blocks_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    suggest_outline_titles TEXT[] DEFAULT '{}',
    confidence FLOAT DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tender_format_snippets_project_id 
    ON tender_format_snippets(project_id);
    
CREATE INDEX IF NOT EXISTS idx_tender_format_snippets_norm_key 
    ON tender_format_snippets(norm_key);

COMMENT ON TABLE tender_format_snippets IS '招标文件格式范本（投标函、授权书等）';
COMMENT ON COLUMN tender_format_snippets.id IS '范本ID';
COMMENT ON COLUMN tender_format_snippets.project_id IS '项目ID';
COMMENT ON COLUMN tender_format_snippets.source_file_id IS '来源文件ID/路径';
COMMENT ON COLUMN tender_format_snippets.norm_key IS '范本类型枚举（bid_letter/power_of_attorney等）';
COMMENT ON COLUMN tender_format_snippets.title IS '范本标题（如"投标函"）';
COMMENT ON COLUMN tender_format_snippets.start_block_id IS '起始块ID';
COMMENT ON COLUMN tender_format_snippets.end_block_id IS '结束块ID';
COMMENT ON COLUMN tender_format_snippets.blocks_json IS '完整blocks结构（段落/表格）';
COMMENT ON COLUMN tender_format_snippets.suggest_outline_titles IS '建议匹配的目录节点标题';
COMMENT ON COLUMN tender_format_snippets.confidence IS 'LLM识别置信度';
COMMENT ON COLUMN tender_format_snippets.created_at IS '创建时间';
COMMENT ON COLUMN tender_format_snippets.updated_at IS '更新时间';

