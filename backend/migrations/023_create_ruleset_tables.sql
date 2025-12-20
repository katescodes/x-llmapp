-- 023_create_ruleset_tables.sql
-- RuleSet 规则集表 - 为自定义规则提供版本化管理能力

-- 规则集表（逻辑规则集）
CREATE TABLE IF NOT EXISTS rule_sets (
  id TEXT PRIMARY KEY,
  namespace TEXT NOT NULL,                          -- e.g. "tender", "contract"
  scope TEXT NOT NULL,                              -- "project" | "org"
  project_id TEXT,                                  -- 项目ID（scope=project 时必填）
  name TEXT NOT NULL,                               -- 规则集名称
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_rule_sets_namespace ON rule_sets(namespace);
CREATE INDEX IF NOT EXISTS idx_rule_sets_scope ON rule_sets(scope);
CREATE INDEX IF NOT EXISTS idx_rule_sets_project_id ON rule_sets(project_id);
CREATE INDEX IF NOT EXISTS idx_rule_sets_created ON rule_sets(created_at DESC);

-- 规则集版本表（每次上传生成新版本）
CREATE TABLE IF NOT EXISTS rule_set_versions (
  id TEXT PRIMARY KEY,
  rule_set_id TEXT NOT NULL REFERENCES rule_sets(id) ON DELETE CASCADE,
  version_no INT NOT NULL DEFAULT 1,                -- 版本号（自增）
  content_sha256 TEXT NOT NULL,                     -- 内容哈希
  content_yaml TEXT NOT NULL,                       -- YAML 内容（原文）
  validate_status TEXT NOT NULL,                    -- "valid" | "invalid"
  validate_message TEXT,                            -- 校验消息/错误信息
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_rule_set_versions_rule_set ON rule_set_versions(rule_set_id);
CREATE INDEX IF NOT EXISTS idx_rule_set_versions_status ON rule_set_versions(validate_status);
CREATE INDEX IF NOT EXISTS idx_rule_set_versions_created ON rule_set_versions(created_at DESC);

-- 复合索引：按规则集和版本号查询
CREATE INDEX IF NOT EXISTS idx_rule_set_versions_set_version ON rule_set_versions(rule_set_id, version_no DESC);

