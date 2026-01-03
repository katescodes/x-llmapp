-- 为申报书目录版本添加项目类型字段，支持多项目类型（如"头雁型"、"链主型"等）

ALTER TABLE declare_directory_versions 
ADD COLUMN IF NOT EXISTS project_type TEXT DEFAULT '默认';

COMMENT ON COLUMN declare_directory_versions.project_type IS '项目类型：头雁型、链主型、领航型、未来工厂等';

-- 创建索引以支持按项目类型查询
CREATE INDEX IF NOT EXISTS idx_declare_directory_versions_project_type 
ON declare_directory_versions(project_id, project_type, is_active);

-- 添加项目类型描述字段（可选）
ALTER TABLE declare_directory_versions 
ADD COLUMN IF NOT EXISTS project_description TEXT;

COMMENT ON COLUMN declare_directory_versions.project_description IS '项目类型简要说明';

