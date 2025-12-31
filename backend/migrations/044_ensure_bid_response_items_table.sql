-- Migration 044: 确保 tender_bid_response_items 表存在（v0.3.7 审核架构依赖）
-- 
-- 说明：此表用于存储从投标文件中预提取的响应要素，
-- 是 ReviewPipelineV3 审核流程的必需依赖。
-- 
-- 架构设计：
-- 1. 提取招标要求 → tender_requirements
-- 2. 提取投标响应 → tender_bid_response_items ⭐️
-- 3. 执行审核 → ReviewPipelineV3（匹配 requirements 和 responses）
-- 4. 保存审核结果 → tender_review_items
--
-- 注意：如果此表不存在，审核功能将完全失效！

CREATE TABLE IF NOT EXISTS tender_bid_response_items (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  bidder_name TEXT NOT NULL,
  dimension TEXT NOT NULL,
  response_type TEXT NOT NULL,
  response_text TEXT NOT NULL,
  extracted_value_json JSONB,
  evidence_chunk_ids TEXT[] DEFAULT ARRAY[]::TEXT[],
  created_at TIMESTAMPTZ DEFAULT now(),
  
  -- 036 migration 字段
  asset_id UUID,
  run_id UUID,
  submission_id UUID,
  normalized_fields_json JSONB,
  evidence_json JSONB
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_tender_bid_response_project ON tender_bid_response_items(project_id);
CREATE INDEX IF NOT EXISTS idx_tender_bid_response_bidder ON tender_bid_response_items(bidder_name);
CREATE INDEX IF NOT EXISTS idx_tender_bid_response_dimension ON tender_bid_response_items(dimension);
CREATE INDEX IF NOT EXISTS idx_tender_bid_response_project_bidder ON tender_bid_response_items(project_id, bidder_name);
CREATE INDEX IF NOT EXISTS idx_tender_bid_response_project_dimension ON tender_bid_response_items(project_id, dimension);
CREATE INDEX IF NOT EXISTS idx_tender_bid_response_asset ON tender_bid_response_items(asset_id) WHERE asset_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tender_bid_response_run ON tender_bid_response_items(run_id) WHERE run_id IS NOT NULL;

-- 添加注释
COMMENT ON TABLE tender_bid_response_items IS '投标响应要素库 - 从投标文件抽取的结构化响应（v0.3.7 审核架构依赖）';
COMMENT ON COLUMN tender_bid_response_items.normalized_fields_json IS '规范化事实字段（如工期、质保、证照有效期等）';
COMMENT ON COLUMN tender_bid_response_items.evidence_json IS '证据详情数组：[{page_start, page_end, quote, heading_path, segment_id}]';

-- 验证表创建成功
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'tender_bid_response_items') THEN
        RAISE EXCEPTION 'tender_bid_response_items 表创建失败！';
    END IF;
    
    RAISE NOTICE '✅ tender_bid_response_items 表已就绪';
END $$;

