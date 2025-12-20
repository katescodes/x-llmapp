from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple, TypedDict
from urllib.parse import urljoin

import httpx

from app.schemas.embedding_provider import EmbeddingProviderStored, EmbeddingProviderUpdate
from app.services.embedding_provider_store import get_embedding_store

logger = logging.getLogger(__name__)

_EMB_PROBED = False
_SPARSE_WARNED = False
_SPARSE_CANDIDATE_KEYS: Tuple[str, ...] = (
    "sparse",
    "sparse_embedding",
    "sparse_vector",
    "lexical",
    "lexical_weights",
    "token_weights",
    "weights",
)
_EMBED_FIELD_KEYS: Tuple[str, ...] = ("embedding", "embeddings", "vector")


class SparseVector(TypedDict):
    indices: List[int]
    values: List[float]


class EmbeddingResult(TypedDict):
    dense: List[float]
    sparse: Optional[SparseVector]


def _chunk(texts: List[str], size: int) -> List[List[str]]:
    return [texts[i : i + size] for i in range(0, len(texts), size)]


def _normalize_sparse(raw: Any) -> Optional[SparseVector]:
    if raw in (None, False):
        return None

    pairs: List[tuple[Any, Any]] = []

    if isinstance(raw, dict):
        if "indices" in raw or "values" in raw:
            indices = raw.get("indices") or []
            values = raw.get("values") or []
            pairs = list(zip(indices, values))
        else:
            pairs = list(raw.items())
    elif isinstance(raw, list):
        pairs = raw
    else:
        return None

    indices: List[int] = []
    values: List[float] = []
    for pair in pairs:
        if isinstance(pair, dict):
            idx = pair.get("index")
            if idx is None:
                idx = pair.get("idx")
            val = pair.get("value")
        else:
            if len(pair) < 2:
                continue
            idx, val = pair[0], pair[1]
        try:
            idx = int(idx)
            val = float(val)
        except (TypeError, ValueError):
            continue
        if abs(val) < 1e-12:
            continue
        indices.append(idx)
        values.append(val)

    if not indices or not values or len(indices) != len(values):
        return None
    return {"indices": indices, "values": values}


def _parse_results(
    payload: Dict[str, Any], expect_sparse: bool
) -> tuple[List[EmbeddingResult], Optional[int], bool]:
    dense_dim = payload.get("dense_dim")
    sparse_missing = False
    if "results" in payload:
        items = payload.get("results") or []
        parsed: List[EmbeddingResult] = []
        for item in items:
            dense = item.get("dense")
            if dense is None:
                raise ValueError("Embedding 服务未返回 dense 向量")
            parsed.append(
                {
                    "dense": [float(x) for x in dense],
                    "sparse": _normalize_sparse(item.get("sparse")),
                }
            )
        if expect_sparse and not any(result.get("sparse") for result in parsed):
            sparse_missing = True
        return parsed, dense_dim, sparse_missing

    if isinstance(payload.get("data"), list):
        parsed = []
        for entry in payload["data"]:
            embedding = entry.get("embedding")
            if embedding is None:
                raise ValueError("Embedding 服务未返回 dense 向量")
            vector = [float(x) for x in embedding]
            parsed.append({"dense": vector, "sparse": None})
            if dense_dim is None:
                dense_dim = len(vector)
        if expect_sparse:
            sparse_missing = True
        return parsed, dense_dim, sparse_missing

    raise ValueError("Embedding API 响应格式无法解析，缺少 results/data 字段")


async def embed_texts(
    texts: List[str], provider: Optional[EmbeddingProviderStored] = None
) -> List[EmbeddingResult]:
    if not texts:
        return []

    store = get_embedding_store()
    cfg = provider or store.get_default()
    if cfg is None:
        raise RuntimeError("未配置默认 Embedding 服务，请先在参数设置里添加")
    if not cfg.base_url:
        raise RuntimeError("Embedding base_url 未配置")
    endpoint = (cfg.endpoint_path or "/v1/embeddings").lstrip("/")
    base = str(cfg.base_url).rstrip("/")
    url = urljoin(base + "/", endpoint)

    batch_size = max(1, cfg.batch_size or 1)
    headers = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"

    timeout = max(cfg.timeout_ms or 1000, 1000) / 1000
    batches = _chunk(texts, batch_size)
    use_hybrid_payload = cfg.output_sparse
    results: List[EmbeddingResult] = []
    detected_dim: Optional[int] = None
    sparse_missing_overall = False

    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        for batch in batches:
            payload: Dict[str, Any] = {
                "model": cfg.model,
                "input": batch,
            }
            if use_hybrid_payload:
                payload.update(
                    {
                        "texts": batch,
                        "output_dense": cfg.output_dense,
                        "output_sparse": cfg.output_sparse,
                        "sparse_format": cfg.sparse_format,
                    }
                )
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            _maybe_probe_response(data)
            parsed, dense_dim, sparse_missing = _parse_results(data, cfg.output_sparse)
            if len(parsed) != len(batch):
                raise ValueError(
                    f"Embedding 返回数量不匹配，期望 {len(batch)} 条，实际 {len(parsed)} 条"
                )
            results.extend(parsed)
            if dense_dim is None:
                for item in parsed:
                    if item.get("dense") is not None:
                        dense_dim = len(item["dense"])  # type: ignore[index]
                        break
            if dense_dim:
                detected_dim = dense_dim
            sparse_missing_overall = sparse_missing_overall or sparse_missing

    if detected_dim:
        try:
            if cfg.dense_dim != int(detected_dim):
                store.update(cfg.id, EmbeddingProviderUpdate(dense_dim=int(detected_dim)))
        except Exception as exc:  # noqa: BLE001
            logger.warning("写入 dense_dim 失败: %s", exc)

    global _SPARSE_WARNED  # noqa: PLW0603
    if cfg.output_sparse and sparse_missing_overall and not _SPARSE_WARNED:
        logger.warning("Embedding 服务未返回 sparse 向量，已退化为 dense-only")
        _SPARSE_WARNED = True

    return results


def _maybe_probe_response(payload: Dict[str, Any]) -> None:
    global _EMB_PROBED  # noqa: PLW0603
    if _EMB_PROBED:
        return
    _EMB_PROBED = True
    try:
        log_parts: List[str] = []
        top_keys = sorted(payload.keys())
        log_parts.append(f"top_keys={top_keys}")

        data_first = payload["data"][0] if isinstance(payload.get("data"), list) and payload["data"] else None
        if isinstance(data_first, dict):
            log_parts.append(f"data0_keys={sorted(data_first.keys())}")

        results_first = (
            payload["results"][0]
            if isinstance(payload.get("results"), list) and payload["results"]
            else None
        )
        if isinstance(results_first, dict):
            log_parts.append(f"results0_keys={sorted(results_first.keys())}")

        containers: Sequence[Tuple[str, Optional[Dict[str, Any]]]] = (
            ("payload", payload),
            ("data[0]", data_first if isinstance(data_first, dict) else None),
            ("results[0]", results_first if isinstance(results_first, dict) else None),
        )

        embed_info = _describe_embedding_fields(containers)
        if embed_info:
            log_parts.append(f"embed_fields={embed_info}")

        sparse_info = _describe_sparse_fields(containers)
        if sparse_info:
            log_parts.append(f"sparse_keys_found={sparse_info}")

        meta_info = _describe_meta(payload)
        if meta_info:
            log_parts.append(f"meta={meta_info}")

        logger.info("Embedding probe: %s", "; ".join(log_parts))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Embedding probe failed: %s", exc)


def _describe_embedding_fields(
    containers: Sequence[Tuple[str, Optional[Dict[str, Any]]]]
) -> List[str]:
    details: List[str] = []
    for label, container in containers:
        if not isinstance(container, dict):
            continue
        for key in _EMBED_FIELD_KEYS:
            if key in container:
                val = container[key]
                length = _safe_len(val)
                details.append(f"{label}.{key} type={type(val).__name__} len={length}")
    return details


def _describe_sparse_fields(
    containers: Sequence[Tuple[str, Optional[Dict[str, Any]]]]
) -> List[str]:
    found: List[str] = []
    for label, container in containers:
        if not isinstance(container, dict):
            continue
        for key in _SPARSE_CANDIDATE_KEYS:
            if key not in container:
                continue
            val = container[key]
            if isinstance(val, dict):
                keys = sorted(list(val.keys()))[:10]
                found.append(f"{label}.{key}=dict(keys={keys})")
            elif isinstance(val, list):
                found.append(f"{label}.{key}=list(len={len(val)})")
            else:
                found.append(f"{label}.{key} type={type(val).__name__}")
    return found


def _describe_meta(payload: Dict[str, Any]) -> List[str]:
    meta: List[str] = []
    for key in ("model", "provider", "version", "usage"):
        if key not in payload:
            continue
        val = payload[key]
        if isinstance(val, dict):
            meta.append(f"{key}.keys={sorted(list(val.keys()))}")
        else:
            meta.append(f"{key}={type(val).__name__}")
    return meta


def _safe_len(value: Any) -> Any:
    try:
        return len(value)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001
        return "n/a"

