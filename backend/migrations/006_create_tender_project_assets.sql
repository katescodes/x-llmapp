-- 006_create_tender_project_assets.sql
-- 招投标应用改造：项目资产表和自定义规则集表

-- 1. 创建项目资产表（统一管理四类文件：招标/投标/模板/自定义规则）
CREATE TABLE IF NOT EXISTS tender_project_assets (
  id              TEXT PRIMARY KEY,
  project_id      TEXT NOT NULL REFERENCES tender_projects(id) ON DELETE CASCADE,
  
  -- 文件类型: tender(招标) | bid(投标) | template(模板) | custom_rule(自定义规则)
  kind            TEXT NOT NULL,
  
  -- 文件基本信息
  title           TEXT,
  filename        TEXT,
  mime_type       TEXT,
  size_bytes      BIGINT,
  
  -- tender/bid/custom_rule：入库后用于证据回溯
  kb_doc_id       TEXT,
  
  -- template：保存到磁盘路径
  storage_path    TEXT,
  
  -- 投标人名称（kind=bid 时必填）
  bidder_name     TEXT,
  
  -- 扩展元数据
  meta_json       JSONB DEFAULT '{}'::jsonb,
  
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_tender_assets_project ON tender_project_assets(project_id);
CREATE INDEX IF NOT EXISTS idx_tender_assets_kind ON tender_project_assets(project_id, kind);
CREATE INDEX IF NOT EXISTS idx_tender_assets_kbdoc ON tender_project_assets(kb_doc_id);

-- 2. 创建自定义审核规则集表
CREATE TABLE IF NOT EXISTS tender_custom_rule_sets (
  id                      TEXT PRIMARY KEY,
  project_id              TEXT NOT NULL REFERENCES tender_projects(id) ON DELETE CASCADE,
  
  name                    TEXT NOT NULL,
  description             TEXT,
  
  -- 来源文件（asset_ids 数组）
  source_asset_ids_json   JSONB NOT NULL DEFAULT '[]'::jsonb,
  
  -- 抽取的结构化规则（数组）
  rules_json              JSONB NOT NULL DEFAULT '[]'::jsonb,
  
  created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_tender_rule_sets_project ON tender_custom_rule_sets(project_id);

-- 3. 为现有表增加证据字段（如果不存在）
ALTER TABLE tender_project_info ADD COLUMN IF NOT EXISTS evidence_chunk_ids_json JSONB DEFAULT '[]'::jsonb;

ALTER TABLE tender_risks ADD COLUMN IF NOT EXISTS tags_json JSONB DEFAULT '[]'::jsonb;
ALTER TABLE tender_risks ADD COLUMN IF NOT EXISTS evidence_chunk_ids_json JSONB DEFAULT '[]'::jsonb;

ALTER TABLE tender_directory_nodes ADD COLUMN IF NOT EXISTS evidence_chunk_ids_json JSONB DEFAULT '[]'::jsonb;

ALTER TABLE tender_review_items ADD COLUMN IF NOT EXISTS tender_evidence_chunk_ids_json JSONB DEFAULT '[]'::jsonb;
ALTER TABLE tender_review_items ADD COLUMN IF NOT EXISTS bid_evidence_chunk_ids_json JSONB DEFAULT '[]'::jsonb;

-- 4. 为 tender_runs 增加字段（支持更灵活的任务管理）
ALTER TABLE tender_runs ADD COLUMN IF NOT EXISTS kind TEXT;
ALTER TABLE tender_runs ADD COLUMN IF NOT EXISTS progress FLOAT;
ALTER TABLE tender_runs ADD COLUMN IF NOT EXISTS message TEXT;
ALTER TABLE tender_runs ADD COLUMN IF NOT EXISTS result_json JSONB;

-- 5. 注释说明
COMMENT ON TABLE tender_project_assets IS '招投标项目资产表：统一管理招标文件、投标文件、模板文件、自定义规则文件';
COMMENT ON COLUMN tender_project_assets.kind IS '文件类型：tender(招标) | bid(投标) | template(模板) | custom_rule(自定义规则)';
COMMENT ON COLUMN tender_project_assets.kb_doc_id IS 'tender/bid/custom_rule文件入库后的kb_documents.id，用于证据回溯';
COMMENT ON COLUMN tender_project_assets.storage_path IS 'template文件的磁盘存储路径';
COMMENT ON COLUMN tender_project_assets.bidder_name IS '投标人名称（kind=bid时必填）';

COMMENT ON TABLE tender_custom_rule_sets IS '自定义审核规则集表：从规则文件中抽取的结构化规则';
COMMENT ON COLUMN tender_custom_rule_sets.source_asset_ids_json IS '来源文件的asset_ids（JSONB数组）';
COMMENT ON COLUMN tender_custom_rule_sets.rules_json IS '抽取的结构化规则（JSONB数组）';
