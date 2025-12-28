-- Migration: 039_fix_review_run_id_type.sql
-- Purpose: 修复 review_run_id 类型从 UUID 改为 TEXT，兼容 tender_runs.id (tr_xxx 格式)
-- Date: 2025-12-29

-- 1. 修改 review_run_id 列类型为 TEXT
ALTER TABLE tender_review_items 
  ALTER COLUMN review_run_id TYPE TEXT USING review_run_id::TEXT;

-- 2. 重建索引保持性能
DROP INDEX IF EXISTS idx_tender_review_run;
CREATE INDEX idx_tender_review_run ON tender_review_items(review_run_id) WHERE review_run_id IS NOT NULL;

-- 3. 添加注释
COMMENT ON COLUMN tender_review_items.review_run_id IS '本次审核运行的ID (tender_runs.id, 格式: tr_xxx)';

