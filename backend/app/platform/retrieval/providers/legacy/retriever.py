from __future__ import annotations

import logging
import time
from typing import List, Optional

from app.schemas.intent import Anchor
from app.services.dao import kb_dao
from app.services.embedding.http_embedding_client import embed_texts
from app.services.embedding_provider_store import EmbeddingProviderStored
from app.platform.retrieval.providers.legacy.pg_lexical import search_lexical
from app.platform.retrieval.providers.legacy.rrf import rrf_fuse
from app.services.vectorstore.milvus_lite_store import milvus_store
from app.services.logging.request_logger import (
    get_request_logger,
    is_debug_enabled,
    safe_preview,
)

logger = logging.getLogger(__name__)


async def retrieve(
    query: str,
    kb_ids: Optional[List[str]],
    kb_categories: Optional[List[str]],
    anchors: List[Anchor],
    embedding_provider: EmbeddingProviderStored,
    dense_topk: int = 40,
    lexical_topk: int = 40,
    final_topk: int = 12,
    query_vector: Optional[List[float]] = None,
    request_id: str | None = None,
) -> tuple[List[dict], dict]:
    req_logger = get_request_logger(logger, request_id)
    start_total = time.perf_counter()
    req_logger.info(
        "Retrieval start query_preview=%s kb_ids=%s dense_topk=%s lexical_topk=%s",
        safe_preview(query, 80),
        kb_ids,
        dense_topk,
        lexical_topk,
    )
    if query_vector is None:
        vectors = await embed_texts([query], provider=embedding_provider)
        if not vectors or not vectors[0].get("dense"):
            raise RuntimeError("Embedding 服务未返回有效的 dense 向量")
        query_dense = vectors[0]["dense"]
    else:
        query_dense = query_vector

    dense_hits: List[dict] = []
    lexical_hits: List[dict] = []

    try:
        dense_hits = milvus_store.search_dense(
            query_dense,
            limit=dense_topk,
            kb_ids=kb_ids,
            kb_categories=kb_categories,
            request_id=request_id,
        )
    except Exception as exc:  # noqa: BLE001
        req_logger.error("Milvus dense 检索失败: %s", exc)

    try:
        lexical_hits = search_lexical(
            query,
            kb_ids,
            kb_categories,
            anchors,
            topk=lexical_topk,
            request_id=request_id,
        )
    except Exception as exc:  # noqa: BLE001
        req_logger.error("Postgres lexical 检索失败: %s", exc)

    fused = rrf_fuse(dense_hits, lexical_hits, topn=final_topk)
    if not fused:
        req_logger.warning("Retrieval no evidence dense=%s lexical=%s", len(dense_hits), len(lexical_hits))
        return [], {
            "dense_candidates": len(dense_hits),
            "lexical_candidates": len(lexical_hits),
            "fused": 0,
        }

    chunk_ids = [hit["chunk_id"] for hit in fused]
    chunk_map = kb_dao.get_chunks_by_ids(chunk_ids)

    results: List[dict] = []
    for hit in fused:
        chunk = chunk_map.get(hit["chunk_id"])
        if not chunk:
            continue
        results.append(
            {
                "chunk_id": hit["chunk_id"],
                "kb_id": chunk.get("kb_id"),
                "doc_id": chunk.get("doc_id"),
                "title": chunk.get("title"),
                "url": chunk.get("url"),
                "text": chunk.get("content"),
                "position": chunk.get("position"),
                "score": hit["score"],
                "hit_dense": hit["hit_dense"],
                "hit_lexical": hit["hit_lexical"],
                "kb_category": chunk.get("kb_category") or "general_doc",
            }
        )
    stats = {
        "dense_candidates": len(dense_hits),
        "lexical_candidates": len(lexical_hits),
        "fused": len(results),
    }
    elapsed_ms = (time.perf_counter() - start_total) * 1000
    req_logger.info(
        "Retrieval done dense=%s lexical=%s fused=%s elapsed=%.1fms",
        len(dense_hits),
        len(lexical_hits),
        len(results),
        elapsed_ms,
    )
    if is_debug_enabled():
        sample = [
            f"{hit['chunk_id']} score={hit['score']:.4f}"
            for hit in fused[:5]
        ]
        req_logger.debug("Retrieval fused_top5=%s", sample)
    return results, stats

