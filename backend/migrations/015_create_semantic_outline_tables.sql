-- 语义目录生成功能相关表
-- 支持从评分/要求推导多级目录 + 证据链

-- ==================== 要求项表 ====================
-- 存储从招标文档中抽取的结构化要求
CREATE TABLE IF NOT EXISTS tender_requirement_items (
    req_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    outline_id TEXT NOT NULL,  -- 关联到 tender_semantic_outlines
    
    -- 要求基本信息
    req_type TEXT NOT NULL,  -- TECH_SCORE, BIZ_SCORE, QUALIFICATION, TECH_SPEC, DELIVERY_ACCEPTANCE, SERVICE_WARRANTY, DOC_FORMAT
    title TEXT NOT NULL,     -- LLM生成的短标题
    content TEXT NOT NULL,   -- 要求原文（尽量短）
    params_json JSONB,       -- 结构化参数（KV）
    score_hint TEXT,         -- 分值/评分描述
    must_level TEXT,         -- MUST, SHOULD, OPTIONAL, UNKNOWN
    
    -- 证据链
    source_chunk_ids TEXT[] NOT NULL,  -- 来源chunk IDs
    confidence DOUBLE PRECISION,       -- 0~1
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_requirement_items_project ON tender_requirement_items(project_id);
CREATE INDEX IF NOT EXISTS idx_requirement_items_outline ON tender_requirement_items(outline_id);
CREATE INDEX IF NOT EXISTS idx_requirement_items_type ON tender_requirement_items(req_type);

-- ==================== 语义目录表 ====================
-- 存储每次生成的语义目录结果
CREATE TABLE IF NOT EXISTS tender_semantic_outlines (
    outline_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    
    -- 生成参数
    mode TEXT NOT NULL,      -- FAST, FULL
    max_depth INT NOT NULL,  -- 最大层级
    
    -- 生成结果
    status TEXT NOT NULL,    -- SUCCESS, LOW_COVERAGE, FAILED
    coverage_rate DOUBLE PRECISION,  -- 覆盖率 0~1
    
    -- 诊断信息
    diagnostics_json JSONB,  -- 包含各类req数量、耗时、覆盖率详情等
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_semantic_outlines_project ON tender_semantic_outlines(project_id);
CREATE INDEX IF NOT EXISTS idx_semantic_outlines_created ON tender_semantic_outlines(created_at DESC);

-- ==================== 语义目录节点表 ====================
-- 存储多级目录树节点
CREATE TABLE IF NOT EXISTS tender_semantic_outline_nodes (
    node_id TEXT PRIMARY KEY,
    outline_id TEXT NOT NULL,  -- 关联到 tender_semantic_outlines
    project_id TEXT NOT NULL,
    
    -- 树结构
    parent_id TEXT,           -- 父节点ID，NULL表示根节点
    level INT NOT NULL,       -- 层级 1~5
    order_no INT NOT NULL,    -- 同级排序序号
    numbering TEXT,           -- 编号如 1.2.3
    
    -- 节点内容
    title TEXT NOT NULL,
    summary TEXT,             -- 一句话说明（<=40字）
    tags TEXT[],              -- 标签如 ["对应评分项", "技术参数"]
    
    -- 证据链
    evidence_chunk_ids TEXT[],  -- 证据chunk IDs（汇总）
    covered_req_ids TEXT[],     -- 覆盖的要求项IDs
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    FOREIGN KEY (outline_id) REFERENCES tender_semantic_outlines(outline_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_semantic_nodes_outline ON tender_semantic_outline_nodes(outline_id);
CREATE INDEX IF NOT EXISTS idx_semantic_nodes_project ON tender_semantic_outline_nodes(project_id);
CREATE INDEX IF NOT EXISTS idx_semantic_nodes_parent ON tender_semantic_outline_nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_semantic_nodes_level ON tender_semantic_outline_nodes(level);

