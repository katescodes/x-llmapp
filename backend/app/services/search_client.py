from typing import List, Dict, Any
import logging
import socket
from urllib.parse import urlparse
import httpx
from fastapi import HTTPException
from app.config import get_settings
from ..schemas.search import SearchResult, SearchResults

settings = get_settings()
logger = logging.getLogger(__name__)

SEARX_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Connection": "keep-alive",
    "X-Real-IP": "127.0.0.1",
    "X-Forwarded-For": "127.0.0.1",
}

_searx_client: httpx.AsyncClient | None = None
_dns_checked = False


def _get_searx_client() -> httpx.AsyncClient:
    global _searx_client
    if _searx_client is None:
        _ensure_searx_dns()
        _searx_client = httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers=SEARX_HEADERS,
        )
    return _searx_client


async def _request_search_json(query: str) -> Dict[str, Any]:
    base_url = settings.SEARXNG_BASE_URL.rstrip("/")
    url = f"{base_url}/search"
    params = {
        "q": query,
        "format": "json",
        "language": "zh-CN",
        "safesearch": 1,
    }
    allowlist = (settings.SEARXNG_ENGINES_ALLOWLIST or "").strip()
    if allowlist:
        params["engines"] = allowlist

    logger.info(
        "SearXNG request: q=%s format=%s engines=%s accept-language=%s",
        query,
        params["format"],
        params.get("engines", "<default>"),
        SEARX_HEADERS.get("Accept-Language"),
    )

    client = _get_searx_client()
    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        preview = _response_preview(exc.response)
        headers_snapshot = dict(exc.response.headers) if exc.response else {}
        logger.error(
            "SearXNG HTTP %s url=%s preview=%s headers=%s",
            exc.response.status_code if exc.response else "unknown",
            str(exc.request.url) if exc.request else url,
            preview,
            headers_snapshot,
        )
        detail = {
            "message": "SearXNG upstream error",
            "searxng_status": exc.response.status_code if exc.response else None,
            "searxng_body_preview": preview,
            "searxng_url": str(exc.request.url) if exc.request else url,
        }
        raise HTTPException(status_code=502, detail=detail) from exc
    except httpx.HTTPError as exc:
        logger.error("SearXNG request failed: %s", exc)
        detail = {
            "message": "SearXNG network error",
            "error": str(exc),
            "searxng_url": url,
        }
        raise HTTPException(status_code=502, detail=detail) from exc


def _response_preview(response: httpx.Response | None) -> str:
    if not response:
        return ""
    text = response.text or ""
    return text[:400]


def _ensure_searx_dns() -> None:
    global _dns_checked
    if _dns_checked:
        return
    _dns_checked = True
    parsed = urlparse(settings.SEARXNG_BASE_URL)
    host = parsed.hostname
    port = parsed.port or (80 if parsed.scheme == "http" else 443)
    if not host:
        logger.warning("SearXNG DNS check skipped: invalid base url %s", settings.SEARXNG_BASE_URL)
        return
    try:
        socket.getaddrinfo(host, port)
        logger.info("SearXNG DNS check ok host=%s port=%s", host, port)
    except OSError as exc:
        logger.error("SearXNG DNS lookup failed host=%s port=%s error=%s", host, port, exc)


async def search_web(query: str, limit: int = 5) -> SearchResults:
    """
    使用 SearXNG 作为代理搜索引擎，不直接调用官方 Google API。
    """
    data = await _request_search_json(query)
    results: List[SearchResult] = []
    for idx, item in enumerate(data.get("results", [])):
        if idx >= limit:
            break
        results.append(
            SearchResult(
                title=item.get("title") or item.get("url", "Untitled"),
                url=item.get("url", ""),
                snippet=(item.get("content") or item.get("snippet") or "")[:400],
            )
        )

    return SearchResults(query=query, results=results)


async def test_search_connection() -> Dict[str, Any]:
    """
    调用一次 SearXNG，返回诊断信息，供自检接口和前端触发。
    """
    try:
        data = await _request_search_json("test")
        return {
            "ok": True,
            "result_count": len(data.get("results", [])),
        }
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {"error": exc.detail}
        detail["ok"] = False
        return detail
