-- 009_add_template_spec_fields.sql
-- 为 format_templates 表添加模板规格分析相关字段

ALTER TABLE format_templates
  ADD COLUMN IF NOT EXISTS template_sha256 VARCHAR(64),
  ADD COLUMN IF NOT EXISTS template_spec_json TEXT,
  ADD COLUMN IF NOT EXISTS template_spec_version VARCHAR(32),
  ADD COLUMN IF NOT EXISTS template_spec_analyzed_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS template_spec_diagnostics_json TEXT;

CREATE INDEX IF NOT EXISTS idx_format_template_sha256 ON format_templates(template_sha256);

COMMENT ON COLUMN format_templates.template_sha256 IS '模板文件的 SHA256 哈希，用于缓存和变更检测';
COMMENT ON COLUMN format_templates.template_spec_json IS 'LLM 分析生成的模板规格 JSON（TemplateSpec）';
COMMENT ON COLUMN format_templates.template_spec_version IS '模板规格分析器版本号（如 v1）';
COMMENT ON COLUMN format_templates.template_spec_analyzed_at IS '模板规格分析时间';
COMMENT ON COLUMN format_templates.template_spec_diagnostics_json IS '分析诊断信息（置信度、警告等）';
