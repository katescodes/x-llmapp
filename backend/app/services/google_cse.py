import logging
import math
from typing import Dict, Any, Optional, List

import httpx
from fastapi import HTTPException

from app.services.logging.request_logger import (
    get_request_logger,
    is_debug_enabled,
    safe_preview,
)

GOOGLE_CSE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"
logger = logging.getLogger(__name__)


async def search_google_cse(
    query: str,
    *,
    api_key: str,
    cx: str,
    num: int = 5,
    start: int = 1,
    freshness_days: Optional[int] = None,
    timeout: float = 15.0,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    req_logger = get_request_logger(logger, request_id)
    effective_num = max(1, min(num, 10))
    if effective_num != num:
        logger.info("Google CSE num truncated from %s to %s (API limit 10)", num, effective_num)

    max_start = max(1, 100 - effective_num + 1)
    effective_start = max(1, min(start, max_start))

    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": effective_num,
        "safe": "active",
        "start": effective_start,
    }
    if freshness_days and freshness_days > 0:
        params["dateRestrict"] = f"d{freshness_days}"

    req_logger.info(
        "Google CSE start query=%s num=%s start=%s timeout=%.1fs",
        safe_preview(query, 120),
        effective_num,
        effective_start,
        timeout,
    )

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(GOOGLE_CSE_ENDPOINT, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response else "unknown"
            preview = (exc.response.text if exc.response else "")[:500]
            req_logger.error("Google CSE HTTP %s preview=%s", status, safe_preview(preview, 500))
            raise HTTPException(
                status_code=502,
                detail=f"Google CSE 请求失败 (HTTP {status}): {preview or '请检查 API key/cx'}",
            ) from exc
        except httpx.HTTPError as exc:
            req_logger.error("Google CSE 请求异常: %s", exc)
            raise HTTPException(status_code=502, detail="Google CSE 请求异常") from exc

    data = response.json()
    items = [
        {
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "snippet": item.get("snippet", ""),
        }
        for item in data.get("items", [])
    ]

    top_urls = [item.get("link") for item in data.get("items", [])[:5] if item.get("link")]
    req_logger.info(
        "Google CSE done query=%s results=%s urls=%s",
        safe_preview(query, 120),
        len(items),
        top_urls,
    )
    if is_debug_enabled():
        req_logger.debug("Google CSE raw keys=%s", sorted(data.keys()))

    return {
        "query": query,
        "items": items,
        "searchInformation": data.get("searchInformation"),
        "raw": data,
    }


async def search_google_cse_multi(
    query: str,
    *,
    api_key: str,
    cx: str,
    min_results: int = 30,
    max_results: int = 40,
    page_size: int = 10,
    freshness_days: Optional[int] = None,
    timeout: float = 15.0,
    request_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    req_logger = get_request_logger(logger, request_id)
    page_size = max(1, min(page_size, 10))
    max_results = max(min_results, max_results)
    max_pages = min(10, max(1, math.ceil(100 / page_size)))

    results: List[Dict[str, Any]] = []
    seen_links: set[str] = set()
    start = 1
    pages_used = 0

    req_logger.info(
        "Google CSE multi start query=%s min=%s max=%s page_size=%s",
        safe_preview(query, 120),
        min_results,
        max_results,
        page_size,
    )

    for page in range(max_pages):
        pages_used = page + 1
        if len(results) >= max_results:
            break
        try:
            resp = await search_google_cse(
                query,
                api_key=api_key,
                cx=cx,
                num=page_size,
                start=start,
                freshness_days=freshness_days,
                timeout=timeout,
                request_id=request_id,
            )
        except HTTPException as exc:
            req_logger.warning(
                "Google CSE multi page=%s failed status=%s detail=%s",
                page + 1,
                exc.status_code,
                safe_preview(exc.detail, 200),
            )
            break
        except Exception as exc:  # noqa: BLE001
            req_logger.warning("Google CSE multi page=%s error=%s", page + 1, exc)
            break

        items = resp.get("items") or []
        for item in items:
            link = item.get("link")
            if link and link in seen_links:
                continue
            if link:
                seen_links.add(link)
            results.append(item)
            if len(results) >= max_results:
                break

        if len(items) < page_size:
            break

        start += page_size

        total_results = resp.get("searchInformation", {}).get("totalResults")
        try:
            if total_results is not None and int(total_results) <= len(results):
                break
        except (ValueError, TypeError):
            pass

    req_logger.info(
        "Google CSE multi done query=%s aggregated=%s pages=%s",
        safe_preview(query, 120),
        len(results),
        pages_used,
    )
    return results

