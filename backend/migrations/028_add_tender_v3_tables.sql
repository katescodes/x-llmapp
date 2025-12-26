-- 028_add_tender_v3_tables.sql
-- Step 2: 新增支持 tender_info_v3、审核、自定义规则、响应要素的数据表
-- 此迁移不删除旧表，只新增所需能力

-- ============================================
-- 1. 招标要求基准条款库 (TenderRequirements)
-- ============================================
-- 从招标文件抽取的结构化要求（供审核使用）

CREATE TABLE IF NOT EXISTS tender_requirements (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES tender_projects(id) ON DELETE CASCADE,
  requirement_id TEXT NOT NULL,                      -- 要求ID（业务唯一标识）
  dimension TEXT NOT NULL,                           -- 维度（qualification/technical/business/price/doc_structure/schedule_quality/other）
  req_type TEXT NOT NULL,                            -- 要求类型（threshold/must_provide/must_not_deviate/scoring/format/other）
  requirement_text TEXT NOT NULL,                    -- 要求内容
  is_hard BOOLEAN NOT NULL DEFAULT false,            -- 是否硬性要求
  allow_deviation BOOLEAN NOT NULL DEFAULT false,    -- 是否允许偏离
  value_schema_json JSONB,                           -- 值约束（如{min:50, max:100, unit:"万元"}）
  evidence_chunk_ids TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],  -- 证据chunk IDs
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_tender_requirements_project ON tender_requirements(project_id);
CREATE INDEX IF NOT EXISTS idx_tender_requirements_dimension ON tender_requirements(dimension);
CREATE INDEX IF NOT EXISTS idx_tender_requirements_req_id ON tender_requirements(requirement_id);

-- 复合索引
CREATE INDEX IF NOT EXISTS idx_tender_requirements_project_dimension 
  ON tender_requirements(project_id, dimension);


-- ============================================
-- 2. 规则包 (RulePacks)
-- ============================================
-- 管理规则包（内置规则 + 用户自定义规则）

CREATE TABLE IF NOT EXISTS tender_rule_packs (
  id TEXT PRIMARY KEY,
  pack_name TEXT NOT NULL,                           -- 规则包名称（如"内置标准规则"/"用户自定义规则"）
  pack_type TEXT NOT NULL,                           -- 包类型（builtin/custom）
  project_id TEXT,                                   -- 项目ID（custom 时关联项目）
  priority INT NOT NULL DEFAULT 0,                   -- 优先级（数字越大优先级越高）
  is_active BOOLEAN NOT NULL DEFAULT true,           -- 是否启用
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_tender_rule_packs_project ON tender_rule_packs(project_id);
CREATE INDEX IF NOT EXISTS idx_tender_rule_packs_type ON tender_rule_packs(pack_type);
CREATE INDEX IF NOT EXISTS idx_tender_rule_packs_active ON tender_rule_packs(is_active);


-- ============================================
-- 3. 规则详情 (Rules)
-- ============================================
-- 规则包中的具体规则

CREATE TABLE IF NOT EXISTS tender_rules (
  id TEXT PRIMARY KEY,
  rule_pack_id TEXT NOT NULL REFERENCES tender_rule_packs(id) ON DELETE CASCADE,
  rule_key TEXT NOT NULL,                            -- 规则键（同 key 高优先级覆盖低优先级）
  rule_name TEXT NOT NULL,                           -- 规则名称
  dimension TEXT NOT NULL,                           -- 适用维度
  evaluator TEXT NOT NULL,                           -- 执行器类型（deterministic/semantic_llm）
  condition_json JSONB NOT NULL,                     -- 条件（DSL）
  severity TEXT NOT NULL DEFAULT 'medium',           -- 严重程度（low/medium/high）
  is_hard BOOLEAN NOT NULL DEFAULT false,            -- 是否硬性规则（不可覆盖）
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_tender_rules_pack ON tender_rules(rule_pack_id);
CREATE INDEX IF NOT EXISTS idx_tender_rules_key ON tender_rules(rule_key);
CREATE INDEX IF NOT EXISTS idx_tender_rules_dimension ON tender_rules(dimension);

-- 复合索引
CREATE INDEX IF NOT EXISTS idx_tender_rules_pack_key 
  ON tender_rules(rule_pack_id, rule_key);


-- ============================================
-- 4. 投标响应要素库 (BidResponseIndex)
-- ============================================
-- 从投标文件抽取的结构化响应要素（供审核使用）

CREATE TABLE IF NOT EXISTS tender_bid_response_items (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES tender_projects(id) ON DELETE CASCADE,
  bidder_name TEXT NOT NULL,                         -- 投标人名称
  dimension TEXT NOT NULL,                           -- 维度（与 requirements 对应）
  response_type TEXT NOT NULL,                       -- 响应类型（direct_answer/table_extract/promise/reference/missing）
  response_text TEXT NOT NULL,                       -- 响应内容
  extracted_value_json JSONB,                        -- 提取的值（如{value:80, unit:"万元", status:"符合"}）
  evidence_chunk_ids TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],  -- 证据chunk IDs
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_tender_bid_response_project ON tender_bid_response_items(project_id);
CREATE INDEX IF NOT EXISTS idx_tender_bid_response_bidder ON tender_bid_response_items(bidder_name);
CREATE INDEX IF NOT EXISTS idx_tender_bid_response_dimension ON tender_bid_response_items(dimension);

-- 复合索引
CREATE INDEX IF NOT EXISTS idx_tender_bid_response_project_bidder 
  ON tender_bid_response_items(project_id, bidder_name);
CREATE INDEX IF NOT EXISTS idx_tender_bid_response_project_dimension 
  ON tender_bid_response_items(project_id, dimension);


-- ============================================
-- 5. 扩展审核结果表 (tender_review_items)
-- ============================================
-- 为现有的 tender_review_items 增加新字段（支持新审核模式）

-- 增加 rule_id 字段（关联规则）
ALTER TABLE tender_review_items 
  ADD COLUMN IF NOT EXISTS rule_id TEXT;

-- 增加 requirement_id 字段（关联招标要求）
ALTER TABLE tender_review_items 
  ADD COLUMN IF NOT EXISTS requirement_id TEXT;

-- 增加 severity 字段（严重程度）
ALTER TABLE tender_review_items 
  ADD COLUMN IF NOT EXISTS severity TEXT DEFAULT 'medium';

-- 增加 evaluator 字段（执行器类型）
ALTER TABLE tender_review_items 
  ADD COLUMN IF NOT EXISTS evaluator TEXT;

-- 增加索引
CREATE INDEX IF NOT EXISTS idx_tender_review_rule ON tender_review_items(rule_id);
CREATE INDEX IF NOT EXISTS idx_tender_review_requirement ON tender_review_items(requirement_id);
CREATE INDEX IF NOT EXISTS idx_tender_review_severity ON tender_review_items(severity);


-- ============================================
-- 6. 注释（备注）
-- ============================================

COMMENT ON TABLE tender_requirements IS '招标要求基准条款库 - 从招标文件抽取的结构化要求';
COMMENT ON TABLE tender_rule_packs IS '规则包 - 管理内置和用户自定义规则';
COMMENT ON TABLE tender_rules IS '规则详情 - 具体的审核规则';
COMMENT ON TABLE tender_bid_response_items IS '投标响应要素库 - 从投标文件抽取的结构化响应';

COMMENT ON COLUMN tender_requirements.requirement_id IS '业务唯一标识（如"qual_001"）';
COMMENT ON COLUMN tender_requirements.req_type IS 'threshold/must_provide/must_not_deviate/scoring/format/other';
COMMENT ON COLUMN tender_requirements.value_schema_json IS '值约束（JSON Schema风格）';

COMMENT ON COLUMN tender_rule_packs.pack_type IS 'builtin: 内置规则包, custom: 用户自定义规则包';
COMMENT ON COLUMN tender_rule_packs.priority IS '优先级（数字越大越高）';

COMMENT ON COLUMN tender_rules.rule_key IS '规则键（同 key 高优先级覆盖低优先级）';
COMMENT ON COLUMN tender_rules.evaluator IS 'deterministic: 确定性判断, semantic_llm: LLM语义判断';
COMMENT ON COLUMN tender_rules.condition_json IS 'DSL条件（引用 requirements/bid_response_items/tender_info_v3）';
COMMENT ON COLUMN tender_rules.is_hard IS '硬性规则不可被用户覆盖';

COMMENT ON COLUMN tender_bid_response_items.response_type IS 'direct_answer/table_extract/promise/reference/missing';
COMMENT ON COLUMN tender_bid_response_items.extracted_value_json IS '提取的结构化值';

COMMENT ON COLUMN tender_review_items.rule_id IS '触发的规则ID';
COMMENT ON COLUMN tender_review_items.requirement_id IS '对应的招标要求ID';
COMMENT ON COLUMN tender_review_items.severity IS '严重程度: low/medium/high';
COMMENT ON COLUMN tender_review_items.evaluator IS '执行器类型: deterministic/semantic_llm';

