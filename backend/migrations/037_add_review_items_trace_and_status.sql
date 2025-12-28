-- Migration: 037_add_review_items_trace_and_status.sql
-- Purpose: 审核结果表支持 PENDING 状态 + 可审计 trace
-- Date: 2025-12-28
-- Step 4: 审核结果表支持 PENDING + trace

-- 添加状态字段（支持 PENDING）
-- 注意：保留原有 result 字段（pass/risk/fail），新增 status 字段
ALTER TABLE tender_review_items 
  ADD COLUMN IF NOT EXISTS status TEXT NULL;

-- 添加规则追踪字段（记录命中的规则、条件、优先级、冲突消解等）
ALTER TABLE tender_review_items 
  ADD COLUMN IF NOT EXISTS rule_trace_json JSONB NULL;

-- 添加计算追踪字段（记录数值/算术校验过程）
ALTER TABLE tender_review_items 
  ADD COLUMN IF NOT EXISTS computed_trace_json JSONB NULL;

-- 添加证据详情字段（最终证据，包含页码和引用）
ALTER TABLE tender_review_items 
  ADD COLUMN IF NOT EXISTS evidence_json JSONB NULL;

-- 添加索引
CREATE INDEX IF NOT EXISTS idx_tender_review_status 
  ON tender_review_items(status) WHERE status IS NOT NULL;

-- 添加注释
COMMENT ON COLUMN tender_review_items.status IS '审核状态：PASS/WARN/FAIL/PENDING（PENDING 表示需人工复核）';
COMMENT ON COLUMN tender_review_items.rule_trace_json IS '规则追踪：命中规则、条件、优先级、冲突消解等';
COMMENT ON COLUMN tender_review_items.computed_trace_json IS '计算追踪：数值/算术校验过程';
COMMENT ON COLUMN tender_review_items.evidence_json IS '证据详情：[{page_start, page_end, quote, heading_path, segment_id, source}]';

-- 数据迁移：将现有 result 映射到 status
-- pass -> PASS, risk -> WARN, fail -> FAIL
UPDATE tender_review_items 
SET status = CASE 
    WHEN result = 'pass' THEN 'PASS'
    WHEN result = 'risk' THEN 'WARN'
    WHEN result = 'fail' THEN 'FAIL'
    ELSE result
END
WHERE status IS NULL;

