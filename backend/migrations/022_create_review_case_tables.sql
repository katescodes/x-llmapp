-- 022_create_review_case_tables.sql
-- ReviewCase 审核案例表 - 为多业务系统提供统一的审核案例管理能力

-- 审核案例表（包含项目+文档版本）
CREATE TABLE IF NOT EXISTS review_cases (
  id TEXT PRIMARY KEY,
  namespace TEXT NOT NULL,                          -- e.g. "tender", "contract"
  project_id TEXT NOT NULL,                         -- 项目ID（业务系统的项目ID）
  tender_doc_version_ids JSONB DEFAULT '[]'::jsonb, -- 招标文档版本ID列表
  bid_doc_version_ids JSONB DEFAULT '[]'::jsonb,    -- 投标文档版本ID列表
  attachment_doc_version_ids JSONB DEFAULT '[]'::jsonb, -- 附件文档版本ID列表
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_review_cases_namespace ON review_cases(namespace);
CREATE INDEX IF NOT EXISTS idx_review_cases_project_id ON review_cases(project_id);
CREATE INDEX IF NOT EXISTS idx_review_cases_created ON review_cases(created_at DESC);

-- 审核运行表（每次审核运行）
CREATE TABLE IF NOT EXISTS review_runs (
  id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES review_cases(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'running',           -- running | succeeded | failed
  model_id TEXT,                                    -- 使用的模型ID
  rule_set_version_id TEXT,                         -- 规则集版本ID（可选，未来 Step6 使用）
  result_json JSONB DEFAULT '{}'::jsonb,            -- 运行结果摘要
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_review_runs_case_id ON review_runs(case_id);
CREATE INDEX IF NOT EXISTS idx_review_runs_status ON review_runs(status);
CREATE INDEX IF NOT EXISTS idx_review_runs_created ON review_runs(created_at DESC);

-- 审核发现表（审核结果条目）
CREATE TABLE IF NOT EXISTS review_findings (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES review_runs(id) ON DELETE CASCADE,
  source TEXT NOT NULL,                             -- "compare" | "rule"
  dimension TEXT,                                   -- 维度：资格审查、报价审查、技术审查等
  requirement_text TEXT,                            -- 招标要求（摘要）
  response_text TEXT,                               -- 投标响应（摘要）
  result TEXT NOT NULL,                             -- pass | risk | fail
  rigid BOOLEAN DEFAULT false,                      -- 是否刚性要求
  remark TEXT,                                      -- 原因/建议/缺失点/冲突点
  evidence_jsonb JSONB DEFAULT '{}'::jsonb,         -- 证据链（包含 tender/bid spans）
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_review_findings_run_id ON review_findings(run_id);
CREATE INDEX IF NOT EXISTS idx_review_findings_source ON review_findings(source);
CREATE INDEX IF NOT EXISTS idx_review_findings_result ON review_findings(result);
CREATE INDEX IF NOT EXISTS idx_review_findings_created ON review_findings(created_at DESC);

