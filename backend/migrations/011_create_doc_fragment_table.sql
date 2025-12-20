-- 011_create_doc_fragment_table.sql
-- 创建范本片段表，用于存储从招标书中抽取的投标文件格式范本

CREATE TABLE IF NOT EXISTS doc_fragment (
  id TEXT PRIMARY KEY,
  owner_type VARCHAR(32) NOT NULL,      -- PROJECT / FORMAT_TEMPLATE / GLOBAL
  owner_id TEXT NOT NULL,               -- projectId or templateId
  source_file_key VARCHAR(512) NOT NULL,
  source_file_sha256 VARCHAR(64),

  fragment_type VARCHAR(64) NOT NULL,   -- 范本片段类型（枚举字符串）
  title VARCHAR(512) NOT NULL,
  title_norm VARCHAR(512) NOT NULL,     -- 归一化标题（用于匹配）
  path_hint VARCHAR(1024),              -- 章节路径提示，如 "第六章/投标文件格式/投标函"
  heading_level INT,

  start_body_index INT NOT NULL,        -- 在源 docx bodyElements 中的起始 index（含）
  end_body_index INT NOT NULL,          -- 结束 index（含）
  confidence DOUBLE PRECISION,
  diagnostics_json TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_doc_fragment_owner ON doc_fragment(owner_type, owner_id);
CREATE INDEX IF NOT EXISTS idx_doc_fragment_type ON doc_fragment(fragment_type);
CREATE INDEX IF NOT EXISTS idx_doc_fragment_title_norm ON doc_fragment(title_norm);

COMMENT ON TABLE doc_fragment IS '范本片段表：存储从招标书中抽取的投标文件格式范本';
COMMENT ON COLUMN doc_fragment.owner_type IS '所属类型：PROJECT（项目级）/ FORMAT_TEMPLATE（模板级）/ GLOBAL（全局）';
COMMENT ON COLUMN doc_fragment.owner_id IS '所属ID：项目ID或模板ID';
COMMENT ON COLUMN doc_fragment.source_file_key IS '源文件存储路径或唯一标识';
COMMENT ON COLUMN doc_fragment.fragment_type IS '范本类型：投标函、授权书、报价表等';
COMMENT ON COLUMN doc_fragment.title_norm IS '归一化后的标题，用于自动匹配';
COMMENT ON COLUMN doc_fragment.start_body_index IS '在源docx中的起始段落/表格索引';
COMMENT ON COLUMN doc_fragment.end_body_index IS '在源docx中的结束段落/表格索引';
