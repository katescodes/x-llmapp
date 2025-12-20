-- 016_add_format_template_analysis_json.sql
-- 为 format_templates 表增加 analysis_json 字段
-- 存储模板分析结果（applyAssets + styleProfile + roleMapping）

ALTER TABLE format_templates
  ADD COLUMN IF NOT EXISTS analysis_json JSONB;

COMMENT ON COLUMN format_templates.analysis_json IS '模板分析结果JSON：包含 applyAssets（LLM理解的保留/删除计划）、styleProfile（样式定义）、roleMapping（h1~h9映射）';

