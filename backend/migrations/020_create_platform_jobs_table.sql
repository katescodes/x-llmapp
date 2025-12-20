-- 020_create_platform_jobs_table.sql
-- 平台统一任务表 - 为多业务系统提供统一的任务运行状态管理

CREATE TABLE IF NOT EXISTS platform_jobs (
  id TEXT PRIMARY KEY,
  namespace TEXT NOT NULL,                    -- e.g. "tender", "contract", "compliance"
  biz_type TEXT NOT NULL,                     -- e.g. "extract_project_info", "extract_risks", "review_run", "ingest_asset"
  biz_id TEXT NOT NULL,                       -- project_id, run_id, asset_id etc.
  status TEXT NOT NULL DEFAULT 'queued',      -- queued | running | succeeded | failed
  progress INT NOT NULL DEFAULT 0,            -- 0-100
  message TEXT,                               -- current status message or error message
  result_json JSONB DEFAULT '{}'::jsonb,      -- final result data
  owner_id VARCHAR(36),                       -- user who created this job
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 索引：按 namespace + biz_type 查询
CREATE INDEX IF NOT EXISTS idx_platform_jobs_namespace ON platform_jobs(namespace);
CREATE INDEX IF NOT EXISTS idx_platform_jobs_biz_type ON platform_jobs(biz_type);
CREATE INDEX IF NOT EXISTS idx_platform_jobs_biz_id ON platform_jobs(biz_id);
CREATE INDEX IF NOT EXISTS idx_platform_jobs_owner ON platform_jobs(owner_id);
CREATE INDEX IF NOT EXISTS idx_platform_jobs_status ON platform_jobs(status);
CREATE INDEX IF NOT EXISTS idx_platform_jobs_created ON platform_jobs(created_at DESC);

-- 复合索引：按业务 ID 快速查询所有相关任务
CREATE INDEX IF NOT EXISTS idx_platform_jobs_namespace_biz_id ON platform_jobs(namespace, biz_id);

