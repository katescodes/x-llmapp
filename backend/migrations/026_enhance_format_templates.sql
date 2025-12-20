-- 026_enhance_format_templates.sql
-- 增强格式模板表结构，确保所有 Work 层需要的字段都存在
-- 此迁移是幂等的，可重复执行

-- ==================== 1. 增强 format_templates 表 ====================

-- 确保所有必要字段存在
ALTER TABLE format_templates
  ADD COLUMN IF NOT EXISTS file_sha256 TEXT,
  ADD COLUMN IF NOT EXISTS template_storage_path TEXT,
  ADD COLUMN IF NOT EXISTS template_sha256 TEXT,
  ADD COLUMN IF NOT EXISTS template_spec_json JSONB,
  ADD COLUMN IF NOT EXISTS template_spec_version TEXT,
  ADD COLUMN IF NOT EXISTS template_spec_analyzed_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS template_spec_diagnostics_json JSONB,
  ADD COLUMN IF NOT EXISTS analysis_json JSONB,
  ADD COLUMN IF NOT EXISTS analysis_status TEXT NOT NULL DEFAULT 'PENDING',
  ADD COLUMN IF NOT EXISTS analysis_error TEXT,
  ADD COLUMN IF NOT EXISTS analysis_updated_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS parse_status TEXT NOT NULL DEFAULT 'PENDING',
  ADD COLUMN IF NOT EXISTS parse_error TEXT,
  ADD COLUMN IF NOT EXISTS parse_result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS parse_updated_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS preview_docx_path TEXT,
  ADD COLUMN IF NOT EXISTS preview_pdf_path TEXT;

-- 添加注释（幂等操作）
COMMENT ON COLUMN format_templates.file_sha256 IS '原始文件 SHA256（用于去重）';
COMMENT ON COLUMN format_templates.template_storage_path IS '模板文件存储路径（容器内路径）';
COMMENT ON COLUMN format_templates.template_sha256 IS '模板内容 SHA256（用于缓存）';
COMMENT ON COLUMN format_templates.template_spec_json IS 'LLM 分析的模板规格（旧版）';
COMMENT ON COLUMN format_templates.template_spec_version IS '模板规格版本';
COMMENT ON COLUMN format_templates.template_spec_analyzed_at IS '模板规格分析时间';
COMMENT ON COLUMN format_templates.template_spec_diagnostics_json IS '模板规格诊断信息';
COMMENT ON COLUMN format_templates.analysis_json IS '模板分析结果JSON：包含 applyAssets、styleProfile、roleMapping、blocks';
COMMENT ON COLUMN format_templates.analysis_status IS '分析状态：PENDING/SUCCESS/FAILED';
COMMENT ON COLUMN format_templates.analysis_error IS '分析失败原因';
COMMENT ON COLUMN format_templates.analysis_updated_at IS '分析结果更新时间';
COMMENT ON COLUMN format_templates.parse_status IS '确定性解析状态：PENDING/SUCCESS/FAILED';
COMMENT ON COLUMN format_templates.parse_error IS '解析失败原因';
COMMENT ON COLUMN format_templates.parse_result_json IS '解析结果摘要（headingLevels/variants/headerFooter/sections）';
COMMENT ON COLUMN format_templates.parse_updated_at IS '解析结果更新时间';
COMMENT ON COLUMN format_templates.preview_docx_path IS '示范预览 docx 文件路径';
COMMENT ON COLUMN format_templates.preview_pdf_path IS '示范预览 pdf 文件路径';

-- 创建索引（如果不存在）
CREATE INDEX IF NOT EXISTS idx_format_templates_owner ON format_templates(owner_id);
CREATE INDEX IF NOT EXISTS idx_format_templates_sha256 ON format_templates(file_sha256);
CREATE INDEX IF NOT EXISTS idx_format_templates_status ON format_templates(analysis_status, parse_status);

-- ==================== 2. 确保 format_template_assets 表存在 ====================

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
  meta_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 创建索引（如果不存在）
CREATE INDEX IF NOT EXISTS idx_format_template_assets_tpl ON format_template_assets(template_id);
CREATE INDEX IF NOT EXISTS idx_format_template_assets_type ON format_template_assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_format_template_assets_variant ON format_template_assets(template_id, variant);

-- 添加注释
COMMENT ON TABLE format_template_assets IS '格式模板资产表（源文件、图片、预览文件等）';
COMMENT ON COLUMN format_template_assets.asset_type IS '资产类型：SOURCE_DOCX/HEADER_IMG/FOOTER_IMG/PREVIEW_DOCX/PREVIEW_PDF';
COMMENT ON COLUMN format_template_assets.variant IS '变体（页面规格）：DEFAULT/A4_PORTRAIT/A4_LANDSCAPE/A3_LANDSCAPE';
COMMENT ON COLUMN format_template_assets.storage_path IS '文件存储路径（容器内路径）';
COMMENT ON COLUMN format_template_assets.meta_json IS '资产元数据（扩展信息）';

-- ==================== 3. 确保 tender_directory_nodes 有 meta_json ====================

-- 检查并添加 meta_json 字段（如果不存在）
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 
    FROM information_schema.columns 
    WHERE table_name = 'tender_directory_nodes' 
    AND column_name = 'meta_json'
  ) THEN
    ALTER TABLE tender_directory_nodes 
      ADD COLUMN meta_json JSONB NOT NULL DEFAULT '{}'::jsonb;
    
    RAISE NOTICE 'Added meta_json column to tender_directory_nodes';
  ELSE
    RAISE NOTICE 'meta_json column already exists in tender_directory_nodes';
  END IF;
END $$;

-- 添加注释
COMMENT ON COLUMN tender_directory_nodes.meta_json IS '目录节点元数据（包含 format_template_id 等）';

-- 创建索引支持快速查找绑定了格式模板的根节点
CREATE INDEX IF NOT EXISTS idx_tender_dir_meta_format_template 
  ON tender_directory_nodes((meta_json->>'format_template_id'))
  WHERE meta_json->>'format_template_id' IS NOT NULL;

-- ==================== 4. 创建辅助视图（可选） ====================

-- 格式模板统计视图
CREATE OR REPLACE VIEW v_format_template_stats AS
SELECT 
  ft.id,
  ft.name,
  ft.owner_id,
  ft.is_public,
  ft.analysis_status,
  ft.parse_status,
  ft.created_at,
  ft.updated_at,
  COUNT(DISTINCT fta.id) FILTER (WHERE fta.asset_type = 'HEADER_IMG') as header_img_count,
  COUNT(DISTINCT fta.id) FILTER (WHERE fta.asset_type = 'FOOTER_IMG') as footer_img_count,
  COUNT(DISTINCT fta.id) FILTER (WHERE fta.asset_type = 'PREVIEW_DOCX') as preview_docx_count,
  COUNT(DISTINCT fta.id) FILTER (WHERE fta.asset_type = 'PREVIEW_PDF') as preview_pdf_count,
  COUNT(DISTINCT tdn.project_id) as used_in_projects_count
FROM format_templates ft
LEFT JOIN format_template_assets fta ON ft.id = fta.template_id
LEFT JOIN tender_directory_nodes tdn ON tdn.meta_json->>'format_template_id' = ft.id
GROUP BY ft.id, ft.name, ft.owner_id, ft.is_public, ft.analysis_status, ft.parse_status, ft.created_at, ft.updated_at;

COMMENT ON VIEW v_format_template_stats IS '格式模板统计视图（包含资产数量和使用次数）';

-- ==================== 5. 数据完整性约束 ====================

-- 确保资产类型有效
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint 
    WHERE conname = 'chk_format_template_assets_type'
  ) THEN
    ALTER TABLE format_template_assets
      ADD CONSTRAINT chk_format_template_assets_type
      CHECK (asset_type IN ('SOURCE_DOCX', 'HEADER_IMG', 'FOOTER_IMG', 'PREVIEW_DOCX', 'PREVIEW_PDF'));
    
    RAISE NOTICE 'Added asset_type constraint';
  END IF;
END $$;

-- 确保分析状态有效
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint 
    WHERE conname = 'chk_format_templates_analysis_status'
  ) THEN
    ALTER TABLE format_templates
      ADD CONSTRAINT chk_format_templates_analysis_status
      CHECK (analysis_status IN ('PENDING', 'SUCCESS', 'FAILED'));
    
    RAISE NOTICE 'Added analysis_status constraint';
  END IF;
END $$;

-- 确保解析状态有效
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint 
    WHERE conname = 'chk_format_templates_parse_status'
  ) THEN
    ALTER TABLE format_templates
      ADD CONSTRAINT chk_format_templates_parse_status
      CHECK (parse_status IN ('PENDING', 'SUCCESS', 'FAILED'));
    
    RAISE NOTICE 'Added parse_status constraint';
  END IF;
END $$;

-- ==================== 6. 清理和优化 ====================

-- 分析表以更新统计信息
ANALYZE format_templates;
ANALYZE format_template_assets;
ANALYZE tender_directory_nodes;

-- 完成提示
DO $$
BEGIN
  RAISE NOTICE '=====================================';
  RAISE NOTICE 'Migration 026 completed successfully';
  RAISE NOTICE 'Format templates tables enhanced';
  RAISE NOTICE '=====================================';
END $$;

