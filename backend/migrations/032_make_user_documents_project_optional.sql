-- 032_make_user_documents_project_optional.sql
-- 将用户文档的project_id改为可选，支持共享文档模式

-- 1. 删除外键约束
ALTER TABLE tender_user_doc_categories 
  DROP CONSTRAINT IF EXISTS tender_user_doc_categories_project_id_fkey;

ALTER TABLE tender_user_documents 
  DROP CONSTRAINT IF EXISTS tender_user_documents_project_id_fkey;

-- 2. 将project_id改为可选（NULL）
ALTER TABLE tender_user_doc_categories 
  ALTER COLUMN project_id DROP NOT NULL;

ALTER TABLE tender_user_documents 
  ALTER COLUMN project_id DROP NOT NULL;

-- 3. 为NULL值创建索引（用于查询共享文档）
CREATE INDEX IF NOT EXISTS idx_user_doc_categories_shared 
  ON tender_user_doc_categories(id) WHERE project_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_user_documents_shared 
  ON tender_user_documents(id) WHERE project_id IS NULL;

-- 4. 更新注释
COMMENT ON COLUMN tender_user_doc_categories.project_id IS '项目ID（可选，NULL表示共享文档分类）';
COMMENT ON COLUMN tender_user_documents.project_id IS '项目ID（可选，NULL表示共享文档）';

