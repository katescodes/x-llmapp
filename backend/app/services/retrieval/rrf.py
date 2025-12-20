from __future__ import annotations

from typing import Dict, List


def rrf_fuse(
    dense_hits: List[Dict],
    lexical_hits: List[Dict],
    k: int = 60,
    w_dense: float = 1.0,
    w_lexical: float = 1.0,
    topn: int = 20,
) -> List[Dict]:
    scores: Dict[str, float] = {}
    sources: Dict[str, Dict[str, int]] = {}

    for rank, hit in enumerate(dense_hits):
        cid = hit["chunk_id"]
        rank_score = w_dense / (k + rank + 1)
        scores[cid] = scores.get(cid, 0.0) + rank_score
        meta = sources.setdefault(cid, {})
        meta["dense_rank"] = rank

    for rank, hit in enumerate(lexical_hits):
        cid = hit["chunk_id"]
        rank_score = w_lexical / (k + rank + 1)
        scores[cid] = scores.get(cid, 0.0) + rank_score
        meta = sources.setdefault(cid, {})
        meta["lexical_rank"] = rank

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:topn]
    fused = []
    for cid, score in ranked:
        meta = sources.get(cid, {})
        fused.append(
            {
                "chunk_id": cid,
                "score": score,
                "hit_dense": "dense_rank" in meta,
                "hit_lexical": "lexical_rank" in meta,
                "dense_rank": meta.get("dense_rank"),
                "lexical_rank": meta.get("lexical_rank"),
            }
        )
    return fused

