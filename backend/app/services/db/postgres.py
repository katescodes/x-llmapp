from __future__ import annotations

from contextlib import contextmanager
import logging
import os
import time
from typing import Optional

from psycopg import Connection, connect
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import get_settings

settings = get_settings()

_pool: Optional[ConnectionPool] = None

logger = logging.getLogger(__name__)


def _build_conninfo() -> str:
    if settings.POSTGRES_DSN:
        return settings.POSTGRES_DSN
    return (
        f"dbname={settings.POSTGRES_DB} "
        f"user={settings.POSTGRES_USER} "
        f"password={settings.POSTGRES_PASSWORD} "
        f"host={settings.POSTGRES_HOST} "
        f"port={settings.POSTGRES_PORT}"
    )


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=_build_conninfo(),
            min_size=settings.POSTGRES_POOL_MIN,
            max_size=settings.POSTGRES_POOL_MAX,
            kwargs={"row_factory": dict_row},  # 使用dict row factory支持字典访问
        )
        _pool.wait()
    return _pool


@contextmanager
def get_conn() -> Connection:
    pool = _get_pool()
    with pool.connection() as conn:
        yield conn


def init_db() -> None:
    retries = int(os.getenv("POSTGRES_INIT_RETRIES", "20"))
    delay = float(os.getenv("POSTGRES_INIT_DELAY", "1"))
    last_exc: Optional[Exception] = None
    ready = False
    for attempt in range(retries):
        try:
            with connect(_build_conninfo()) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            ready = True
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning("Postgres 未就绪（%s），%ss 后重试 [%s/%s]", exc, delay, attempt + 1, retries)
            time.sleep(delay)
    if not ready:
        if last_exc:
            raise RuntimeError("Postgres 初始化失败") from last_exc
        raise RuntimeError("Postgres 初始化失败") from last_exc
    _run_ddl()


def _run_ddl() -> None:
    pool = _get_pool()
    ddl = """
    CREATE EXTENSION IF NOT EXISTS pg_trgm;

    CREATE TABLE IF NOT EXISTS chat_sessions (
        id TEXT PRIMARY KEY,
        title TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        default_kb_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
        search_mode TEXT NOT NULL,
        model_id TEXT,
        meta_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        summary TEXT
    );
    ALTER TABLE chat_sessions
        ADD COLUMN IF NOT EXISTS summary TEXT;

    CREATE TABLE IF NOT EXISTS chat_messages (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
    );
    CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);

    CREATE TABLE IF NOT EXISTS kb_categories (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        display_name TEXT NOT NULL,
        color TEXT NOT NULL DEFAULT '#6b7280',
        icon TEXT NOT NULL DEFAULT '📁',
        description TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    -- 插入默认分类
    INSERT INTO kb_categories (id, name, display_name, color, icon, description)
    VALUES 
        ('cat_knowledge', 'knowledge', '知识库', '#10b981', '📚', '通用知识和技术文档'),
        ('cat_policy', 'policy', '政策制度', '#8b5cf6', '📘', '规章制度、规范、流程'),
        ('cat_experience', 'experience', '经验库', '#3b82f6', '💡', '实践经验、最佳实践'),
        ('cat_history', 'history', '历史案例', '#f59e0b', '📋', '历史项目、案例记录')
    ON CONFLICT (id) DO NOTHING;

    CREATE TABLE IF NOT EXISTS knowledge_bases (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        category_id TEXT REFERENCES kb_categories(id) ON DELETE SET NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    
    -- 添加 category_id 列（如果不存在）
    ALTER TABLE knowledge_bases 
        ADD COLUMN IF NOT EXISTS category_id TEXT REFERENCES kb_categories(id) ON DELETE SET NULL;

    CREATE TABLE IF NOT EXISTS kb_documents (
        id TEXT PRIMARY KEY,
        kb_id TEXT NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
        filename TEXT NOT NULL,
        source TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        meta_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        kb_category TEXT NOT NULL DEFAULT 'general_doc'
    );
    CREATE INDEX IF NOT EXISTS idx_kb_documents_kb ON kb_documents(kb_id);
    CREATE INDEX IF NOT EXISTS idx_kb_documents_hash ON kb_documents(content_hash);
    ALTER TABLE kb_documents
        ADD COLUMN IF NOT EXISTS kb_category TEXT NOT NULL DEFAULT 'general_doc';
    CREATE INDEX IF NOT EXISTS idx_kb_documents_category ON kb_documents(kb_category);

    CREATE TABLE IF NOT EXISTS kb_chunks (
        chunk_id TEXT PRIMARY KEY,
        kb_id TEXT NOT NULL,
        doc_id TEXT NOT NULL,
        title TEXT,
        url TEXT,
        position INT,
        content TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        tsv TSVECTOR,
        kb_category TEXT NOT NULL DEFAULT 'general_doc'
    );
    CREATE INDEX IF NOT EXISTS idx_chunks_kb_doc ON kb_chunks(kb_id, doc_id);
    CREATE INDEX IF NOT EXISTS idx_chunks_tsv ON kb_chunks USING GIN (tsv);
    CREATE INDEX IF NOT EXISTS idx_chunks_content_trgm ON kb_chunks USING GIN (content gin_trgm_ops);
    CREATE INDEX IF NOT EXISTS idx_chunks_title_trgm ON kb_chunks USING GIN (coalesce(title, '') gin_trgm_ops);
    ALTER TABLE kb_chunks
        ADD COLUMN IF NOT EXISTS kb_category TEXT NOT NULL DEFAULT 'general_doc';
    CREATE INDEX IF NOT EXISTS idx_chunks_kb_category ON kb_chunks(kb_category);

    CREATE TABLE IF NOT EXISTS doc_cache (
        url TEXT PRIMARY KEY,
        content_hash TEXT NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    -- ==================== Tender App: fragments（范本片段） ====================
    -- 说明：历史环境可能已跑过部分 migrations，但缺少后续新增表；
    -- 这里用 IF NOT EXISTS 做兜底，保证 auto_fill_samples / 导出链路可用。
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
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()

