-- 021_1_add_tsv_column.sql
-- 为 doc_segments 添加 tsv 列（补充迁移）
-- 如果已经执行过更新后的 021，此脚本可跳过

-- 添加 tsv 列（如果不存在）
ALTER TABLE doc_segments ADD COLUMN IF NOT EXISTS tsv tsvector;

-- 为现有数据填充 tsv
UPDATE doc_segments SET tsv = to_tsvector('simple', content_text) WHERE tsv IS NULL;

-- 创建 GIN 索引
CREATE INDEX IF NOT EXISTS idx_doc_segments_tsv ON doc_segments USING GIN(tsv);

-- 创建触发器函数（自动更新 tsv）
CREATE OR REPLACE FUNCTION doc_segments_tsv_trigger() RETURNS trigger AS $$
BEGIN
  NEW.tsv := to_tsvector('simple', NEW.content_text);
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

-- 创建触发器
DROP TRIGGER IF EXISTS tsvectorupdate ON doc_segments;
CREATE TRIGGER tsvectorupdate BEFORE INSERT OR UPDATE ON doc_segments
  FOR EACH ROW EXECUTE FUNCTION doc_segments_tsv_trigger();

-- 验证
SELECT 
    COUNT(*) as total_segments,
    COUNT(tsv) as segments_with_tsv,
    COUNT(*) - COUNT(tsv) as segments_without_tsv
FROM doc_segments;

