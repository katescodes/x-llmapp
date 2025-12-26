-- 为 doc_fragment 表添加内容字段
ALTER TABLE doc_fragment 
ADD COLUMN IF NOT EXISTS content_type VARCHAR(20);

ALTER TABLE doc_fragment 
ADD COLUMN IF NOT EXISTS content_html TEXT;

ALTER TABLE doc_fragment 
ADD COLUMN IF NOT EXISTS content_text TEXT;

ALTER TABLE doc_fragment 
ADD COLUMN IF NOT EXISTS content_items JSONB;

COMMENT ON COLUMN doc_fragment.content_type IS '内容类型: text/table/mixed';
COMMENT ON COLUMN doc_fragment.content_html IS '富文本HTML内容';
COMMENT ON COLUMN doc_fragment.content_text IS '纯文本内容';
COMMENT ON COLUMN doc_fragment.content_items IS '详细items结构';

CREATE INDEX IF NOT EXISTS idx_doc_fragment_content_type 
ON doc_fragment(content_type);
