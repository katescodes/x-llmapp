-- Migration: 035_add_requirements_routing_fields.sql
-- Purpose: 升级招标要求表为"可路由条款"，支持分层审核策略
-- Date: 2025-12-28
-- Step 2: 招标要求表升级 - 增加路由条款字段

-- 添加评估方法字段（决定走哪个审核分支）
ALTER TABLE tender_requirements 
  ADD COLUMN IF NOT EXISTS eval_method TEXT NULL;

-- 添加是否必须拒绝字段
ALTER TABLE tender_requirements 
  ADD COLUMN IF NOT EXISTS must_reject BOOLEAN DEFAULT false;

-- 添加预期证据字段（JSONB 格式，灵活存储）
ALTER TABLE tender_requirements 
  ADD COLUMN IF NOT EXISTS expected_evidence_json JSONB NULL;

-- 添加评分细则字段（用于语义评分）
ALTER TABLE tender_requirements 
  ADD COLUMN IF NOT EXISTS rubric_json JSONB NULL;

-- 添加权重字段
ALTER TABLE tender_requirements 
  ADD COLUMN IF NOT EXISTS weight FLOAT NULL;

-- 添加索引以加速按评估方法查询
CREATE INDEX IF NOT EXISTS idx_tender_requirements_eval_method 
  ON tender_requirements(eval_method) WHERE eval_method IS NOT NULL;

-- 添加注释
COMMENT ON COLUMN tender_requirements.eval_method IS '评估方法：PRESENCE/VALIDITY/NUMERIC/EXACT_MATCH/TABLE_COMPARE/SEMANTIC';
COMMENT ON COLUMN tender_requirements.must_reject IS '是否为必须拒绝项（真值为 true 时，不合规直接判 FAIL）';
COMMENT ON COLUMN tender_requirements.expected_evidence_json IS '预期证据类型和结构（如 {"doc_types":["license"], "fields":["expire_date"]}）';
COMMENT ON COLUMN tender_requirements.rubric_json IS '评分细则（用于 SEMANTIC 评估，包含评分标准和权重）';
COMMENT ON COLUMN tender_requirements.weight IS '条款权重（用于加权评分）';

