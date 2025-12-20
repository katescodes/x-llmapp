-- 014_add_format_template_parse_and_assets.sql
-- 为格式模板新增“确定性解析 + 预览资产”能力：
-- 1) format_templates 增加 parse 状态/结果/预览文件路径
-- 2) 新增 format_template_assets 表存 header/footer 图片与 preview 文件

ALTER TABLE format_templates
  ADD COLUMN IF NOT EXISTS parse_status TEXT NOT NULL DEFAULT 'PENDING',
  ADD COLUMN IF NOT EXISTS parse_error TEXT,
  ADD COLUMN IF NOT EXISTS parse_result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS parse_updated_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS preview_docx_path TEXT,
  ADD COLUMN IF NOT EXISTS preview_pdf_path TEXT;

COMMENT ON COLUMN format_templates.parse_status IS '确定性模板解析状态：PENDING/SUCCESS/FAILED';
COMMENT ON COLUMN format_templates.parse_error IS '解析失败原因（摘要）';
COMMENT ON COLUMN format_templates.parse_result_json IS '解析结果摘要（headingLevels/variants/headerFooter/sections 等）';
COMMENT ON COLUMN format_templates.parse_updated_at IS '解析结果更新时间';
COMMENT ON COLUMN format_templates.preview_docx_path IS '示范预览 docx 文件路径（容器内路径，APP_DATA_DIR 下）';
COMMENT ON COLUMN format_templates.preview_pdf_path IS '示范预览 pdf 文件路径（容器内路径，APP_DATA_DIR 下）';

CREATE TABLE IF NOT EXISTS format_template_assets (
  id TEXT PRIMARY KEY,
  template_id TEXT NOT NULL REFERENCES format_templates(id) ON DELETE CASCADE,
  asset_type TEXT NOT NULL,          -- SOURCE_DOCX / HEADER_IMG / FOOTER_IMG / PREVIEW_DOCX / PREVIEW_PDF
  variant TEXT NOT NULL DEFAULT 'DEFAULT', -- A4_PORTRAIT / A4_LANDSCAPE / A3_LANDSCAPE / DEFAULT
  file_name TEXT,
  content_type TEXT,
  storage_path TEXT NOT NULL,
  width_px INT,
  height_px INT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_format_template_assets_tpl ON format_template_assets(template_id);
CREATE INDEX IF NOT EXISTS idx_format_template_assets_type ON format_template_assets(asset_type);


