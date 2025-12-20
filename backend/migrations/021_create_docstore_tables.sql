-- 021_create_docstore_tables.sql
-- DocStore 文档底座表 - 为多业务系统提供统一的文档管理能力

-- 文档表（逻辑文档，可以有多个版本）
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  namespace TEXT NOT NULL,                    -- e.g. "tender", "contract", "compliance"
  doc_type TEXT NOT NULL,                     -- e.g. "tender", "bid", "template", "custom_rule"
  owner_id VARCHAR(36),                       -- 文档所有者
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_documents_namespace ON documents(namespace);
CREATE INDEX IF NOT EXISTS idx_documents_doc_type ON documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_documents_owner ON documents(owner_id);
CREATE INDEX IF NOT EXISTS idx_documents_created ON documents(created_at DESC);

-- 文档版本表（每次上传/修改生成新版本）
CREATE TABLE IF NOT EXISTS document_versions (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  sha256 TEXT NOT NULL,                       -- 文件内容哈希
  filename TEXT NOT NULL,                     -- 原始文件名
  storage_path TEXT,                          -- 存储路径（如果有）
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_document_versions_document ON document_versions(document_id);
CREATE INDEX IF NOT EXISTS idx_document_versions_sha256 ON document_versions(sha256);
CREATE INDEX IF NOT EXISTS idx_document_versions_created ON document_versions(created_at DESC);

-- 文档片段表（分段/分块后的内容）
CREATE TABLE IF NOT EXISTS doc_segments (
  id TEXT PRIMARY KEY,
  doc_version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
  segment_no INT NOT NULL,                    -- 片段序号（从0开始）
  content_text TEXT NOT NULL,                 -- 文本内容
  meta_json JSONB DEFAULT '{}'::jsonb,        -- 元数据（可存 chunk_id 映射、页码等）
  tsv tsvector,                               -- 全文搜索向量（自动生成）
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_doc_segments_version ON doc_segments(doc_version_id);
CREATE INDEX IF NOT EXISTS idx_doc_segments_segment_no ON doc_segments(doc_version_id, segment_no);

-- 复合索引：按文档版本和序号查询
CREATE INDEX IF NOT EXISTS idx_doc_segments_version_segment ON doc_segments(doc_version_id, segment_no);

-- 全文搜索索引（GIN）
CREATE INDEX IF NOT EXISTS idx_doc_segments_tsv ON doc_segments USING GIN(tsv);

-- 触发器函数：自动更新 tsv
CREATE OR REPLACE FUNCTION doc_segments_tsv_trigger() RETURNS trigger AS $$
BEGIN
  NEW.tsv := to_tsvector('simple', NEW.content_text);
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

-- 触发器：INSERT 或 UPDATE 时自动生成 tsv
DROP TRIGGER IF EXISTS tsvectorupdate ON doc_segments;
CREATE TRIGGER tsvectorupdate BEFORE INSERT OR UPDATE ON doc_segments
  FOR EACH ROW EXECUTE FUNCTION doc_segments_tsv_trigger();

