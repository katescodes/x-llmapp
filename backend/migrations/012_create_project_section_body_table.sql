-- 012_create_project_section_body_table.sql
-- 创建项目章节正文表，用于存储目录节点的正文内容（范本挂载或用户编辑）

CREATE TABLE IF NOT EXISTS project_section_body (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES tender_projects(id) ON DELETE CASCADE,
  node_id VARCHAR(128) NOT NULL,        -- outline node id（前端/后端一致）
  source VARCHAR(32) NOT NULL,          -- EMPTY / TEMPLATE_SAMPLE / USER / AI
  fragment_id TEXT,                     -- 关联的 doc_fragment.id（可为空）
  content_html TEXT,                    -- 用户编辑的HTML内容（可为空）
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (project_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_project_section_body_project ON project_section_body(project_id);
CREATE INDEX IF NOT EXISTS idx_project_section_body_node ON project_section_body(node_id);
CREATE INDEX IF NOT EXISTS idx_project_section_body_fragment ON project_section_body(fragment_id);

COMMENT ON TABLE project_section_body IS '项目章节正文表：存储每个目录节点的正文内容';
COMMENT ON COLUMN project_section_body.source IS '内容来源：EMPTY（空）/ TEMPLATE_SAMPLE（范本挂载）/ USER（用户编辑）/ AI（AI生成）';
COMMENT ON COLUMN project_section_body.fragment_id IS '关联的范本片段ID，source为TEMPLATE_SAMPLE时使用';
COMMENT ON COLUMN project_section_body.content_html IS '用户编辑的HTML内容，source为USER时使用';
