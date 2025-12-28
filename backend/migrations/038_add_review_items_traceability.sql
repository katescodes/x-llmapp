-- Migration: 038_add_review_items_traceability.sql
-- Purpose: 审核结果表支持完整可追溯性（requirement_id + matched_response_id + review_run_id）
-- Date: 2025-12-28
-- Step A: 修复落库可追溯性

-- 添加需求条款 ID（关联 tender_requirements）
ALTER TABLE tender_review_items 
  ADD COLUMN IF NOT EXISTS requirement_id TEXT NULL;

-- 添加匹配的响应 ID（关联 tender_bid_response_items）
ALTER TABLE tender_review_items 
  ADD COLUMN IF NOT EXISTS matched_response_id UUID NULL;

-- 添加审核批次 ID（便于追溯同一次审核）
ALTER TABLE tender_review_items 
  ADD COLUMN IF NOT EXISTS review_run_id UUID NULL;

-- 添加索引
CREATE INDEX IF NOT EXISTS idx_tender_review_requirement 
  ON tender_review_items(requirement_id) WHERE requirement_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tender_review_response 
  ON tender_review_items(matched_response_id) WHERE matched_response_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tender_review_run 
  ON tender_review_items(review_run_id) WHERE review_run_id IS NOT NULL;

-- 添加注释
COMMENT ON COLUMN tender_review_items.requirement_id IS '关联的招标要求ID（tender_requirements.requirement_id）';
COMMENT ON COLUMN tender_review_items.matched_response_id IS '匹配的投标响应ID（tender_bid_response_items.id）';
COMMENT ON COLUMN tender_review_items.review_run_id IS '审核批次ID（便于追溯同一次审核的所有结果）';

