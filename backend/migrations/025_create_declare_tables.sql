-- 025: 创建 declare（申报书）应用表
-- 用途：申报通知管理、企业信息、技术资料、自动填充申报书

-- ============================================================
-- 1) declare_projects：申报项目主表
-- ============================================================
CREATE TABLE IF NOT EXISTS declare_projects (
    project_id TEXT PRIMARY KEY,
    kb_id TEXT NOT NULL,  -- 关联知识库（IngestV2）
    name TEXT NOT NULL,
    description TEXT,
    owner_id TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_declare_projects_owner ON declare_projects(owner_id);
CREATE INDEX IF NOT EXISTS idx_declare_projects_kb ON declare_projects(kb_id);

-- ============================================================
-- 2) declare_assets：项目资产（文件）
-- ============================================================
CREATE TABLE IF NOT EXISTS declare_assets (
    asset_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES declare_projects(project_id) ON DELETE CASCADE,
    kind TEXT NOT NULL,  -- notice|company|tech|other
    filename TEXT NOT NULL,
    storage_path TEXT,
    file_size BIGINT,
    mime_type TEXT,
    
    -- 新入库字段（对接 IngestV2）
    document_id TEXT,  -- docstore documents.document_id
    doc_version_id TEXT,  -- docstore doc_versions.version_id
    
    meta_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_declare_assets_project ON declare_assets(project_id);
CREATE INDEX IF NOT EXISTS idx_declare_assets_kind ON declare_assets(project_id, kind);
CREATE INDEX IF NOT EXISTS idx_declare_assets_document ON declare_assets(document_id);

-- ============================================================
-- 3) declare_runs：任务执行记录
-- ============================================================
CREATE TABLE IF NOT EXISTS declare_runs (
    run_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES declare_projects(project_id) ON DELETE CASCADE,
    task_type TEXT NOT NULL,  -- requirements|directory|sections|document
    status TEXT DEFAULT 'pending',  -- pending|running|success|failed
    progress FLOAT DEFAULT 0.0,
    message TEXT,
    result_json JSONB DEFAULT '{}'::jsonb,
    
    -- 平台 Job 关联（状态源规则：GOAL-2）
    platform_job_id TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_declare_runs_project ON declare_runs(project_id);
CREATE INDEX IF NOT EXISTS idx_declare_runs_task_type ON declare_runs(project_id, task_type);
CREATE INDEX IF NOT EXISTS idx_declare_runs_platform_job ON declare_runs(platform_job_id);

-- ============================================================
-- 4) declare_requirements：申报要求/条件/材料/时间
-- ============================================================
CREATE TABLE IF NOT EXISTS declare_requirements (
    project_id TEXT PRIMARY KEY REFERENCES declare_projects(project_id) ON DELETE CASCADE,
    data_json JSONB NOT NULL DEFAULT '{}'::jsonb,  -- 结构化数据（eligibility/materials/deadlines）
    evidence_chunk_ids TEXT[] DEFAULT '{}',
    retrieval_trace JSONB DEFAULT '{}'::jsonb,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_declare_requirements_updated ON declare_requirements(updated_at DESC);

-- ============================================================
-- 5) declare_directory_versions：目录版本表（避免 delete+insert 空窗）
-- ============================================================
CREATE TABLE IF NOT EXISTS declare_directory_versions (
    version_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES declare_projects(project_id) ON DELETE CASCADE,
    source TEXT DEFAULT 'notice',  -- notice|manual
    run_id TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_declare_directory_versions_project ON declare_directory_versions(project_id, is_active);

-- ============================================================
-- 6) declare_directory_nodes：目录节点（版本化）
-- ============================================================
CREATE TABLE IF NOT EXISTS declare_directory_nodes (
    id TEXT PRIMARY KEY,
    version_id TEXT NOT NULL REFERENCES declare_directory_versions(version_id) ON DELETE CASCADE,
    project_id TEXT NOT NULL REFERENCES declare_projects(project_id) ON DELETE CASCADE,
    parent_id TEXT,
    order_no INT NOT NULL DEFAULT 0,
    numbering TEXT,  -- "一、" "（一）" "1." 等
    level INT NOT NULL DEFAULT 1,
    title TEXT NOT NULL,
    is_required BOOLEAN DEFAULT TRUE,
    source TEXT DEFAULT 'notice',
    evidence_chunk_ids_json JSONB DEFAULT '[]'::jsonb,
    meta_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_declare_directory_nodes_version ON declare_directory_nodes(version_id);
CREATE INDEX IF NOT EXISTS idx_declare_directory_nodes_project ON declare_directory_nodes(project_id);
CREATE INDEX IF NOT EXISTS idx_declare_directory_nodes_parent ON declare_directory_nodes(parent_id);

-- ============================================================
-- 7) declare_sections_versions：章节填充版本表
-- ============================================================
CREATE TABLE IF NOT EXISTS declare_sections_versions (
    version_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES declare_projects(project_id) ON DELETE CASCADE,
    run_id TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_declare_sections_versions_project ON declare_sections_versions(project_id, is_active);

-- ============================================================
-- 8) declare_sections：章节填充内容（版本化，按 node_id）
-- ============================================================
CREATE TABLE IF NOT EXISTS declare_sections (
    section_id TEXT PRIMARY KEY,
    version_id TEXT NOT NULL REFERENCES declare_sections_versions(version_id) ON DELETE CASCADE,
    project_id TEXT NOT NULL REFERENCES declare_projects(project_id) ON DELETE CASCADE,
    node_id TEXT NOT NULL,  -- 关联 declare_directory_nodes.id
    node_title TEXT,
    content_md TEXT,  -- 自动填充的 Markdown 内容
    content_html TEXT,  -- 可选：渲染后的 HTML
    evidence_chunk_ids TEXT[] DEFAULT '{}',
    retrieval_trace JSONB DEFAULT '{}'::jsonb,
    meta_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_declare_sections_version ON declare_sections(version_id);
CREATE INDEX IF NOT EXISTS idx_declare_sections_project ON declare_sections(project_id);
CREATE INDEX IF NOT EXISTS idx_declare_sections_node ON declare_sections(node_id);

-- ============================================================
-- 9) declare_documents：导出文档记录
-- ============================================================
CREATE TABLE IF NOT EXISTS declare_documents (
    document_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES declare_projects(project_id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    file_size BIGINT,
    format TEXT DEFAULT 'docx',  -- docx|pdf
    version_id TEXT,  -- 关联 declare_sections_versions.version_id
    meta_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_declare_documents_project ON declare_documents(project_id, created_at DESC);

-- ============================================================
-- 完成标记
-- ============================================================
-- Migration 025: declare tables created successfully

