-- 029_add_evidence_to_section_body.sql
-- 为 project_section_body 添加证据追踪字段

ALTER TABLE project_section_body
ADD COLUMN IF NOT EXISTS evidence_chunk_ids TEXT[] DEFAULT ARRAY[]::TEXT[];

-- 添加索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_project_section_body_evidence 
ON project_section_body USING GIN (evidence_chunk_ids);

-- 添加注释
COMMENT ON COLUMN project_section_body.evidence_chunk_ids IS '生成内容时引用的企业资料片段ID列表';

