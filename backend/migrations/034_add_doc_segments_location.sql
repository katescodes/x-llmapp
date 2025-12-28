-- Migration: 034_add_doc_segments_location.sql
-- Purpose: 添加位置字段以支持证据可定位化
-- Date: 2025-12-28
-- Step 1: 证据可定位化 - doc_segments 补齐位置字段

-- 添加页码范围字段
ALTER TABLE doc_segments 
  ADD COLUMN IF NOT EXISTS page_start INT NULL,
  ADD COLUMN IF NOT EXISTS page_end INT NULL;

-- 添加章节路径字段（如"第三章/资格审查/营业执照"）
ALTER TABLE doc_segments 
  ADD COLUMN IF NOT EXISTS heading_path TEXT NULL;

-- 添加片段类型字段（paragraph/table/list/header/other）
ALTER TABLE doc_segments 
  ADD COLUMN IF NOT EXISTS segment_type TEXT NULL;

-- 添加索引以加速按页码查询
CREATE INDEX IF NOT EXISTS idx_doc_segments_page_start ON doc_segments(page_start) WHERE page_start IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_doc_segments_segment_type ON doc_segments(segment_type) WHERE segment_type IS NOT NULL;

-- 添加注释
COMMENT ON COLUMN doc_segments.page_start IS '片段起始页码（PDF 页码，从 1 开始）';
COMMENT ON COLUMN doc_segments.page_end IS '片段结束页码（PDF 页码，包含）';
COMMENT ON COLUMN doc_segments.heading_path IS '章节路径，如"第三章/资格审查/营业执照"';
COMMENT ON COLUMN doc_segments.segment_type IS '片段类型：paragraph/table/list/header/other';

