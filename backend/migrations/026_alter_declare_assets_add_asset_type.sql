-- 026: 为 declare_assets 添加 asset_type 字段
-- 用途：区分文档、图片、图片说明Excel

-- 添加 asset_type 字段
ALTER TABLE declare_assets 
ADD COLUMN IF NOT EXISTS asset_type TEXT DEFAULT 'document';

-- 更新kind注释
COMMENT ON COLUMN declare_assets.kind IS 'notice|user_doc|image|company|tech|other';
COMMENT ON COLUMN declare_assets.asset_type IS 'document|image|image_description';

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_declare_assets_asset_type ON declare_assets(project_id, asset_type);

-- Migration 026: declare_assets.asset_type added successfully

