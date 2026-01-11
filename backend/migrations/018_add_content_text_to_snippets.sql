-- 为格式范本表添加纯文本内容字段
-- 用于快速预览和搜索

ALTER TABLE tender_format_snippets 
ADD COLUMN IF NOT EXISTS content_text TEXT DEFAULT '';

-- 创建全文搜索索引（可选，提升搜索性能）
CREATE INDEX IF NOT EXISTS idx_tender_format_snippets_content_text 
    ON tender_format_snippets USING gin(to_tsvector('simple', content_text));

-- 添加注释
COMMENT ON COLUMN tender_format_snippets.content_text IS '范本的纯文本内容，从blocks_json提取';
