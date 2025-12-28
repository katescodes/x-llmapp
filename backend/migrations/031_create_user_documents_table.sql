-- 031_create_user_documents_table.sql
-- 用户文档管理：用于招投标系统存储用户上传的技术资料、资质文件等
-- 用途：在生成标书时系统自动分析并加入标书使用

-- ============================================
-- 1. 文档分类表 (User Document Categories)
-- ============================================
CREATE TABLE IF NOT EXISTS tender_user_doc_categories (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES tender_projects(id) ON DELETE CASCADE,
  category_name TEXT NOT NULL,                       -- 分类名称（如"技术资料"、"资质文件"、"企业介绍"等）
  category_desc TEXT,                                -- 分类描述
  display_order INT NOT NULL DEFAULT 0,              -- 显示顺序
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_user_doc_categories_project 
  ON tender_user_doc_categories(project_id);
CREATE INDEX IF NOT EXISTS idx_user_doc_categories_order 
  ON tender_user_doc_categories(project_id, display_order);

-- ============================================
-- 2. 用户文档表 (User Documents)
-- ============================================
CREATE TABLE IF NOT EXISTS tender_user_documents (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES tender_projects(id) ON DELETE CASCADE,
  category_id TEXT REFERENCES tender_user_doc_categories(id) ON DELETE SET NULL,
  
  -- 文档基本信息
  doc_name TEXT NOT NULL,                            -- 文档名称
  filename TEXT NOT NULL,                            -- 原始文件名
  file_type TEXT NOT NULL,                           -- 文件类型（pdf/docx/txt/image/jpg/png等）
  mime_type TEXT,                                    -- MIME类型
  file_size BIGINT,                                  -- 文件大小（字节）
  
  -- 存储信息
  storage_path TEXT,                                 -- 文件存储路径
  kb_doc_id TEXT,                                    -- 关联的知识库文档ID（用于检索）
  
  -- 文档属性
  doc_tags TEXT[] DEFAULT ARRAY[]::TEXT[],           -- 文档标签
  description TEXT,                                  -- 文档描述
  
  -- 分析状态
  is_analyzed BOOLEAN DEFAULT false,                 -- 是否已分析
  analysis_json JSONB DEFAULT '{}'::jsonb,           -- 分析结果（摘要、关键信息等）
  
  -- 元数据
  meta_json JSONB DEFAULT '{}'::jsonb,               -- 扩展元数据
  owner_id TEXT,                                     -- 上传者ID
  
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_user_documents_project 
  ON tender_user_documents(project_id);
CREATE INDEX IF NOT EXISTS idx_user_documents_category 
  ON tender_user_documents(category_id);
CREATE INDEX IF NOT EXISTS idx_user_documents_kb_doc 
  ON tender_user_documents(kb_doc_id);
CREATE INDEX IF NOT EXISTS idx_user_documents_owner 
  ON tender_user_documents(owner_id);
CREATE INDEX IF NOT EXISTS idx_user_documents_file_type 
  ON tender_user_documents(project_id, file_type);

-- 复合索引（常用查询）
CREATE INDEX IF NOT EXISTS idx_user_documents_project_category 
  ON tender_user_documents(project_id, category_id);

-- ============================================
-- 3. 注释（备注）
-- ============================================
COMMENT ON TABLE tender_user_doc_categories IS '用户文档分类表 - 管理文档分类（技术资料、资质文件等）';
COMMENT ON TABLE tender_user_documents IS '用户文档表 - 存储用户上传的技术资料、资质文件等，用于自动生成标书';

COMMENT ON COLUMN tender_user_doc_categories.display_order IS '显示顺序（越小越靠前）';

COMMENT ON COLUMN tender_user_documents.file_type IS '文件类型：pdf/docx/txt/jpg/png/image等';
COMMENT ON COLUMN tender_user_documents.storage_path IS '文件在服务器上的存储路径';
COMMENT ON COLUMN tender_user_documents.kb_doc_id IS '关联的知识库文档ID，用于RAG检索';
COMMENT ON COLUMN tender_user_documents.is_analyzed IS '是否已使用AI分析提取关键信息';
COMMENT ON COLUMN tender_user_documents.analysis_json IS 'AI分析结果：摘要、关键信息、适用场景等';
COMMENT ON COLUMN tender_user_documents.doc_tags IS '文档标签数组（如["ISO认证","2024年"]）';

