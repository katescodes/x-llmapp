from __future__ import annotations

import logging
import re
import time
from typing import Dict, List, Optional, Tuple

from psycopg import errors
from psycopg.rows import dict_row

from app.schemas.intent import Anchor
from app.services.db.postgres import get_conn
from app.services.logging.request_logger import (
    get_request_logger,
    is_debug_enabled,
    safe_preview,
)

logger = logging.getLogger(__name__)

NUMERIC_PATTERN = re.compile(r"\d{4,}")
DATE_PATTERN = re.compile(r"\d{4}[-/年]\d{1,2}([-/月]\d{1,2})?")
QUOTED_PATTERN = re.compile(r"[\"“”‘’']([^\"“”‘’']{2,64})[\"“”‘’']")


def _anchor_phrases(anchors: List[Anchor], limit: int) -> List[str]:
    strong = [a.text.strip() for a in anchors if a.strength == "strong" and a.text.strip()]
    medium = [a.text.strip() for a in anchors if a.strength == "medium" and a.text.strip()]
    weak = [a.text.strip() for a in anchors if a.strength == "weak" and a.text.strip()]
    phrases = strong + medium + weak
    seen = []
    for text in phrases:
        if text not in seen:
            seen.append(text)
        if len(seen) >= limit:
            break
    return seen


def _extract_query_phrases(query: str, limit: int) -> List[str]:
    phrases: List[str] = []
    for pattern in (QUOTED_PATTERN, DATE_PATTERN, NUMERIC_PATTERN):
        for match in pattern.findall(query):
            value = match if isinstance(match, str) else "".join(match)
            value = value.strip()
            if value and value not in phrases:
                phrases.append(value)
            if len(phrases) >= limit:
                return phrases
    if not phrases:
        phrases.append(query[:60])
    return phrases[:limit]


def _build_trgm_phrases(query: str, anchors: List[Anchor], limit: int = 5) -> List[str]:
    phrases = _anchor_phrases(anchors, limit)
    if len(phrases) < limit:
        phrases.extend(_extract_query_phrases(query, limit - len(phrases)))
    cleaned = []
    seen = set()
    for text in phrases:
        key = text.strip()
        if key and key not in seen:
            cleaned.append(key)
            seen.add(key)
    return cleaned[:limit]


def _kb_filter_clause(
    kb_ids: Optional[List[str]],
    kb_categories: Optional[List[str]],
) -> Tuple[str, Tuple]:
    clauses: List[str] = []
    params: List[List[str]] = []
    if kb_ids:
        clean_ids = sorted({kb for kb in kb_ids if kb})
        if clean_ids:
            clauses.append("kb_id = ANY(%s)")
            params.append(clean_ids)
    if kb_categories:
        clean_cats = sorted({cat for cat in kb_categories if cat})
        if clean_cats:
            clauses.append("kb_category = ANY(%s)")
            params.append(clean_cats)
    if not clauses:
        return "", tuple()
    return "AND " + " AND ".join(clauses), tuple(params)


def _search_tsv(
    query: str,
    kb_ids: Optional[List[str]],
    kb_categories: Optional[List[str]],
    topk: int,
) -> List[Dict]:
    if not query.strip():
        return []
    clause, params = _kb_filter_clause(kb_ids, kb_categories)
    sql = f"""
    WITH q AS (
        SELECT websearch_to_tsquery('simple', %s) AS query
    )
    SELECT chunk_id, ts_rank_cd(tsv, q.query) AS score
    FROM kb_chunks, q
    WHERE q.query @@ tsv
    {clause}
    ORDER BY score DESC
    LIMIT %s
    """
    args = (query,) + params + (topk,)
    try:
        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, args)
                rows = cur.fetchall()
    except errors.SyntaxError:
        logger.info("websearch_to_tsquery failed, fallback to plainto_tsquery")
        sql = sql.replace("websearch_to_tsquery", "plainto_tsquery")
        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, args)
                rows = cur.fetchall()
    return [
        {"chunk_id": row["chunk_id"], "score": float(row["score"]), "source": "tsv"}
        for row in rows
    ]


def _search_trgm(
    query: str,
    anchors: List[Anchor],
    kb_ids: Optional[List[str]],
    kb_categories: Optional[List[str]],
    topk: int,
) -> List[Dict]:
    phrases = _build_trgm_phrases(query, anchors)
    clause, params = _kb_filter_clause(kb_ids, kb_categories)
    sql = f"""
    SELECT chunk_id,
           greatest(similarity(content, %s), similarity(coalesce(title,''), %s)) AS score
    FROM kb_chunks
    WHERE (content %% %s OR coalesce(title,'') %% %s)
    {clause}
    ORDER BY score DESC
    LIMIT %s
    """
    hits: Dict[str, float] = {}
    with get_conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            for phrase in phrases:
                args = (phrase, phrase, phrase, phrase) + params + (topk,)
                cur.execute(sql, args)
                for row in cur.fetchall():
                    chunk_id = row["chunk_id"]
                    score = float(row["score"])
                    hits[chunk_id] = max(hits.get(chunk_id, 0.0), score)
    ranked = sorted(hits.items(), key=lambda item: item[1], reverse=True)[:topk]
    return [{"chunk_id": cid, "score": score, "source": "trgm"} for cid, score in ranked]


def search_lexical(
    query: str,
    kb_ids: Optional[List[str]],
    kb_categories: Optional[List[str]],
    anchors: List[Anchor],
    topk: int = 40,
    request_id: str | None = None,
) -> List[Dict]:
    req_logger = get_request_logger(logger, request_id)
    start = time.perf_counter()
    req_logger.info(
        "Lexical search start query_preview=%s kb_ids=%s topk=%s",
        safe_preview(query, 80),
        kb_ids,
        topk,
    )
    try:
        tsv_hits = _search_tsv(query, kb_ids, kb_categories, topk)
    except Exception as exc:  # noqa: BLE001
        req_logger.error("TSV lexical search failed: %s", exc)
        tsv_hits = []
    try:
        trgm_hits = _search_trgm(query, anchors, kb_ids, kb_categories, max(5, topk // 2))
    except Exception as exc:  # noqa: BLE001
        req_logger.error("Trigram lexical search failed: %s", exc)
        trgm_hits = []

    combined: Dict[str, Dict] = {}
    for hit in tsv_hits:
        combined[hit["chunk_id"]] = {**hit, "source": ["tsv"]}
    for hit in trgm_hits:
        entry = combined.setdefault(
            hit["chunk_id"], {"chunk_id": hit["chunk_id"], "score": 0.0, "source": []}
        )
        entry["score"] = max(entry["score"], hit["score"])
        entry["source"].append("trgm")

    ranked = sorted(combined.values(), key=lambda item: item["score"], reverse=True)
    elapsed_ms = (time.perf_counter() - start) * 1000
    req_logger.info(
        "Lexical search done tsv=%s trgm=%s total=%s elapsed=%.1fms",
        len(tsv_hits),
        len(trgm_hits),
        len(ranked),
        elapsed_ms,
    )
    if is_debug_enabled():
        sample = [f"{item['chunk_id']}:{item['score']:.4f}" for item in ranked[:5]]
        req_logger.debug("Lexical top samples=%s", sample)

    return ranked[:topk]

