-- 004_create_tender_app_tables.sql

CREATE TABLE IF NOT EXISTS tender_projects (
  id TEXT PRIMARY KEY,
  kb_id TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  owner_id VARCHAR(36),
  status TEXT NOT NULL DEFAULT 'draft',
  meta_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tender_projects_kb ON tender_projects(kb_id);
CREATE INDEX IF NOT EXISTS idx_tender_projects_owner ON tender_projects(owner_id);

CREATE TABLE IF NOT EXISTS tender_project_documents (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES tender_projects(id) ON DELETE CASCADE,
  kb_doc_id TEXT NOT NULL,
  doc_role TEXT NOT NULL,               -- tender | bid | attachment
  bidder_name TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tpd_project ON tender_project_documents(project_id);
CREATE INDEX IF NOT EXISTS idx_tpd_doc ON tender_project_documents(kb_doc_id);

CREATE TABLE IF NOT EXISTS tender_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES tender_projects(id) ON DELETE CASCADE,
  run_type TEXT NOT NULL,                 -- project_info | risks | directory | review | docx
  status TEXT NOT NULL DEFAULT 'pending', -- pending | running | success | failed
  model_id TEXT,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  error TEXT,
  meta_json JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_tender_runs_project ON tender_runs(project_id);

CREATE TABLE IF NOT EXISTS tender_project_info (
  project_id TEXT PRIMARY KEY REFERENCES tender_projects(id) ON DELETE CASCADE,
  data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tender_risks (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES tender_projects(id) ON DELETE CASCADE,
  risk_type TEXT NOT NULL,              -- mustReject | other
  title TEXT NOT NULL,
  description TEXT,
  suggestion TEXT,
  severity TEXT NOT NULL DEFAULT 'medium', -- low | medium | high
  tags TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  evidence_chunk_ids TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tender_risks_project ON tender_risks(project_id);

CREATE TABLE IF NOT EXISTS tender_directory_nodes (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES tender_projects(id) ON DELETE CASCADE,
  parent_id TEXT,
  order_no INT NOT NULL DEFAULT 0,
  level INT NOT NULL DEFAULT 1,
  numbering TEXT,
  title TEXT NOT NULL,
  is_required BOOLEAN NOT NULL DEFAULT true,
  source TEXT NOT NULL DEFAULT 'tender', -- tender | inferred | manual
  evidence_chunk_ids TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  meta_json JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_tender_dir_project ON tender_directory_nodes(project_id);
CREATE INDEX IF NOT EXISTS idx_tender_dir_parent ON tender_directory_nodes(parent_id);

CREATE TABLE IF NOT EXISTS tender_review_items (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES tender_projects(id) ON DELETE CASCADE,
  dimension TEXT NOT NULL,              -- qualification | price | tech | business | schedule_quality | doc_structure | other
  clause_title TEXT,
  tender_requirement TEXT NOT NULL,
  bidder_name TEXT,
  bid_response TEXT,
  result TEXT NOT NULL,                 -- pass | risk | fail
  is_hard BOOLEAN NOT NULL DEFAULT false,
  remark TEXT,
  tender_evidence_chunk_ids TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  bid_evidence_chunk_ids TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tender_review_project ON tender_review_items(project_id);

CREATE TABLE IF NOT EXISTS format_templates (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  style_config JSONB NOT NULL DEFAULT '{}'::jsonb,
  owner_id VARCHAR(36),
  is_public BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_format_templates_owner ON format_templates(owner_id);
