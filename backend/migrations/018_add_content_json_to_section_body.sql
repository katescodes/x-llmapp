-- 为 project_section_body 表添加 content_json 字段
-- 用于存储结构化的范本内容（段落+表格），使前端能立即预览

ALTER TABLE project_section_body
ADD COLUMN IF NOT EXISTS content_json JSONB;

-- 创建索引以提高查询性能（可选）
CREATE INDEX IF NOT EXISTS idx_project_section_body_content_json 
ON project_section_body USING GIN (content_json);

-- 添加注释
COMMENT ON COLUMN project_section_body.content_json IS '结构化内容：[{type:paragraph|table, text/tableData/...}]';

