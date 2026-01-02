-- 027: 为 tender_project_assets 添加企业资料类型支持
-- 用途：支持企业资料、技术文档、案例证明等向量检索

-- 更新kind字段注释
COMMENT ON COLUMN tender_project_assets.kind IS 'tender|bid|company_profile|tech_doc|case_study|finance_doc|cert_doc|template|custom_rule';

-- 添加资产类型字段（用于区分文档和图片）
ALTER TABLE tender_project_assets 
ADD COLUMN IF NOT EXISTS asset_type TEXT DEFAULT 'document';

COMMENT ON COLUMN tender_project_assets.asset_type IS 'document|image|image_description';

-- 创建索引优化查询
CREATE INDEX IF NOT EXISTS idx_tender_project_assets_kind_type ON tender_project_assets(project_id, kind, asset_type);

-- Migration 027: tender_project_assets company resource kinds added successfully

