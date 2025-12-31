-- 为 tender_directory_nodes 添加正文相关字段
-- 用于存储格式范本自动填充的内容

-- 添加 body_content 字段（节点正文内容）
ALTER TABLE tender_directory_nodes 
ADD COLUMN IF NOT EXISTS body_content TEXT;

-- 添加 source_chunk_ids 字段（来源chunk IDs）
ALTER TABLE tender_directory_nodes 
ADD COLUMN IF NOT EXISTS source_chunk_ids TEXT[] DEFAULT ARRAY[]::TEXT[];

-- 添加 updated_at 字段（更新时间）
ALTER TABLE tender_directory_nodes 
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- 添加索引以提升查询性能
CREATE INDEX IF NOT EXISTS idx_tender_dir_body_not_null 
ON tender_directory_nodes(project_id) 
WHERE body_content IS NOT NULL;

-- 注释
COMMENT ON COLUMN tender_directory_nodes.body_content IS '节点正文内容（如格式范本文本）';
COMMENT ON COLUMN tender_directory_nodes.source_chunk_ids IS '正文来源的文档chunk IDs';
COMMENT ON COLUMN tender_directory_nodes.updated_at IS '节点最后更新时间';

