-- 041_add_meta_json_to_documents.sql
-- 为 documents 表添加 meta_json 字段
-- 日期：2025-12-31

-- 添加 meta_json 字段
ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS meta_json JSONB DEFAULT '{}'::jsonb;

-- 创建索引以提升查询性能
CREATE INDEX IF NOT EXISTS idx_documents_meta_json ON documents USING GIN (meta_json);
CREATE INDEX IF NOT EXISTS idx_documents_kb_id ON documents ((meta_json->>'kb_id')) WHERE meta_json->>'kb_id' IS NOT NULL;

-- 添加注释
COMMENT ON COLUMN documents.meta_json IS '元数据JSON，包含kb_id、kb_category等信息';

SELECT '✓ documents 表已添加 meta_json 字段' as status;

