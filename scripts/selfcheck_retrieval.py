#!/usr/bin/env python
"""
Minimal self-check ensuring Postgres lexical search + Milvus dense search + RRF work together.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT / "backend"))

from app.services.db.postgres import get_conn, init_db  # noqa:E402
from app.schemas.intent import Anchor  # noqa:E402
from app.services.dao import kb_dao  # noqa:E402
from app.services.retrieval.pg_lexical import search_lexical  # noqa:E402
from app.services.retrieval.rrf import rrf_fuse  # noqa:E402
from app.services.vectorstore.milvus_lite_store import milvus_store  # noqa:E402


def main() -> int:
    init_db()
    kb_id = "selfcheck_kb"
    doc_id = "selfcheck_doc"
    chunk_id = "selfcheck_chunk"
    content = "订单编号 ZX-9911 金额 1200 元，客户名称 测试公司。"
    title = "自检记录 ZX-9911"

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO knowledge_bases(id, name, description)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, description=EXCLUDED.description
                """,
                (kb_id, "Selfcheck KB", "用于自检的知识库"),
            )
            cur.execute(
                """
                INSERT INTO kb_documents(id, kb_id, filename, source, content_hash, status)
                VALUES (%s, %s, %s, %s, %s, 'ready')
                ON CONFLICT (id) DO UPDATE SET filename=EXCLUDED.filename, updated_at=now()
                """,
                (doc_id, kb_id, "selfcheck.txt", "upload", "hash-selfcheck"),
            )
        conn.commit()

    kb_dao.upsert_chunk(
        chunk_id=chunk_id,
        kb_id=kb_id,
        doc_id=doc_id,
        title=title,
        url="kb://selfcheck",
        position=0,
        content=content,
    )

    vector = [0.1, 0.2, 0.3, 0.4]
    milvus_store.upsert_chunks(
        [{"chunk_id": chunk_id, "kb_id": kb_id, "doc_id": doc_id, "dense": vector}],
        dense_dim=len(vector),
    )

    anchors = [Anchor(text="ZX-9911", type="id", strength="strong")]
    lex_hits = search_lexical("查询订单 ZX-9911 金额", [kb_id], anchors, topk=5)
    if not lex_hits or lex_hits[0]["chunk_id"] != chunk_id:
        print("Lexical retrieval failed")
        return 1

    dense_hits = milvus_store.search_dense(vector, limit=5, kb_ids=[kb_id])
    if not dense_hits or dense_hits[0]["chunk_id"] != chunk_id:
        print("Dense retrieval failed")
        return 1

    fused = rrf_fuse(dense_hits, lex_hits, topn=1)
    if not fused or fused[0]["chunk_id"] != chunk_id:
        print("RRF fusion failed")
        return 1

    print("Retrieval self-check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

