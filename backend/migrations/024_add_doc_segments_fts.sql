-- 024_add_doc_segments_fts.sql
-- 为 doc_segments 添加全文搜索支持

-- 添加 tsvector 列用于全文搜索
ALTER TABLE doc_segments 
ADD COLUMN IF NOT EXISTS tsv tsvector;

-- 创建函数：自动更新 tsvector
CREATE OR REPLACE FUNCTION doc_segments_tsv_trigger() RETURNS trigger AS $$
begin
  new.tsv :=
     setweight(to_tsvector('english', coalesce(new.content_text,'')), 'A');
  return new;
end
$$ LANGUAGE plpgsql;

-- 创建触发器：插入/更新时自动更新 tsvector
DROP TRIGGER IF EXISTS tsvectorupdate ON doc_segments;
CREATE TRIGGER tsvectorupdate BEFORE INSERT OR UPDATE
    ON doc_segments FOR EACH ROW EXECUTE FUNCTION doc_segments_tsv_trigger();

-- 为现有数据生成 tsvector
UPDATE doc_segments SET tsv = to_tsvector('english', coalesce(content_text, ''));

-- 创建 GIN 索引加速全文搜索
CREATE INDEX IF NOT EXISTS idx_doc_segments_tsv ON doc_segments USING GIN(tsv);

-- 创建复合索引：用于按 doc_version_id 过滤 + 全文搜索
CREATE INDEX IF NOT EXISTS idx_doc_segments_version_tsv ON doc_segments(doc_version_id) WHERE tsv IS NOT NULL;

