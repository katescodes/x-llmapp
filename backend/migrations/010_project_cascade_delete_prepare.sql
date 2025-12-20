-- 010_project_cascade_delete_prepare.sql
-- 为项目级联删除做准备：添加删除审计表和扩展字段

-- 1. 创建项目删除审计表（记录删除操作）
CREATE TABLE IF NOT EXISTS tender_project_delete_audit (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  project_name TEXT NOT NULL,
  requested_by TEXT,
  plan_json JSONB,
  status TEXT NOT NULL, -- PENDING | RUNNING | SUCCESS | FAILED
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_project_delete_audit_project_id ON tender_project_delete_audit(project_id);
CREATE INDEX IF NOT EXISTS idx_project_delete_audit_status ON tender_project_delete_audit(status);

COMMENT ON TABLE tender_project_delete_audit IS '项目删除审计日志：记录所有项目删除操作及其详情';
COMMENT ON COLUMN tender_project_delete_audit.plan_json IS '删除计划详情（资源清单、数量等）';
COMMENT ON COLUMN tender_project_delete_audit.status IS '删除状态：PENDING(待确认) | RUNNING(执行中) | SUCCESS(成功) | FAILED(失败)';

-- 2. 检查关联表的 project_id 和索引（大部分已存在，这里做补充检查）
-- tender_project_documents 已有 project_id（外键）
-- tender_runs 已有 project_id（外键）
-- tender_project_info 已有 project_id（主键）
-- tender_risks 已有 project_id（外键）
-- tender_directory_nodes 已有 project_id（外键）
-- tender_review_items 已有 project_id（外键）
-- tender_project_assets 已有 project_id（外键）

-- 3. 确保 kb_documents 和 kb_chunks 有必要的索引用于清理（可能已存在）
CREATE INDEX IF NOT EXISTS idx_kb_documents_kb_id ON kb_documents(kb_id);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_kb_id ON kb_chunks(kb_id);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_doc_id ON kb_chunks(doc_id);

-- 4. 为 format_templates 添加更多分析字段（补充 009 迁移）
-- file_key: 文件存储键（用于删除物理文件）
-- 注意：file_key 暂时不需要，因为格式模板目前不存储到对象存储，直接保存在 meta_json 或作为临时文件处理

-- 5. 添加项目的 updated_at 触发器（如果不存在）
CREATE OR REPLACE FUNCTION update_tender_projects_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tender_projects_updated_at_trigger ON tender_projects;
CREATE TRIGGER tender_projects_updated_at_trigger
  BEFORE UPDATE ON tender_projects
  FOR EACH ROW
  EXECUTE FUNCTION update_tender_projects_updated_at();
