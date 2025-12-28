-- Migration: 036_add_bid_response_facts_and_evidence.sql
-- Purpose: 投标响应表升级为"事实字段 + 论述条目"
-- Date: 2025-12-28
-- Step 3: 投标响应表升级 - 增加事实字段和论述条目

-- 添加资产 ID（来源文件）
ALTER TABLE tender_bid_response_items 
  ADD COLUMN IF NOT EXISTS asset_id UUID NULL;

-- 添加批次 ID
ALTER TABLE tender_bid_response_items 
  ADD COLUMN IF NOT EXISTS run_id UUID NULL;

-- 添加提交 ID（同一投标人一次提交）
ALTER TABLE tender_bid_response_items 
  ADD COLUMN IF NOT EXISTS submission_id UUID NULL;

-- 添加规范化事实字段（结构化数据）
ALTER TABLE tender_bid_response_items 
  ADD COLUMN IF NOT EXISTS normalized_fields_json JSONB NULL;

-- 添加证据详情（包含页码、引用文本、位置等）
ALTER TABLE tender_bid_response_items 
  ADD COLUMN IF NOT EXISTS evidence_json JSONB NULL;

-- 添加索引
CREATE INDEX IF NOT EXISTS idx_tender_bid_response_asset 
  ON tender_bid_response_items(asset_id) WHERE asset_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tender_bid_response_run 
  ON tender_bid_response_items(run_id) WHERE run_id IS NOT NULL;

-- 添加注释
COMMENT ON COLUMN tender_bid_response_items.asset_id IS '来源投标文件的资产 ID';
COMMENT ON COLUMN tender_bid_response_items.run_id IS '抽取批次 ID（用于追溯）';
COMMENT ON COLUMN tender_bid_response_items.submission_id IS '投标人提交 ID（同一投标人一次提交）';
COMMENT ON COLUMN tender_bid_response_items.normalized_fields_json IS '规范化事实字段（如工期、质保、证照有效期等）';
COMMENT ON COLUMN tender_bid_response_items.evidence_json IS '证据详情数组：[{page_start, page_end, quote, heading_path, segment_id}]';

