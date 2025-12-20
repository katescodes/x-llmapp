import asyncio
import logging
import random
import time
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urlparse

import httpx

from app.services.logging.request_logger import (
    get_request_logger,
    safe_preview,
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17 Mobile/15E148 Safari/604.1",
]
DEFAULT_REFERERS = [
    "https://www.google.com/",
    "https://news.google.com/",
    "https://www.bing.com/",
]
logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    url: str
    final_url: str
    status: int
    content_type: str | None
    html: str | None
    error: str | None = None


class PageFetcher:
    def __init__(
        self,
        timeout: float = 20.0,
        concurrency: int = 4,
        request_id: Optional[str] = None,
        max_retries: int = 2,
        delay_range: tuple[float, float] = (0.6, 1.8),
        domain_cooldown: float = 2.5,
        proxies: Optional[List[str]] = None,
    ):
        # 为了整体延迟可控，将单次超时限制在 5~15 秒之间
        self.base_timeout = max(5.0, min(timeout, 15.0))
        self.semaphore = asyncio.Semaphore(concurrency)
        self.logger = get_request_logger(logger, request_id)
        self.max_retries = max(0, max_retries)
        lo, hi = delay_range
        if hi < lo:
            hi = lo
        self.delay_min = max(0.0, lo)
        self.delay_max = max(0.0, hi)
        self.domain_cooldown = max(0.0, domain_cooldown)
        self._domain_slots: dict[str, float] = {}
        self.proxies = [p for p in (proxies or []) if p]

    async def _reserve_domain_slot(self, domain: str) -> None:
        if not domain or self.domain_cooldown <= 0:
            return
        while True:
            now = time.monotonic()
            ready = self._domain_slots.get(domain, 0.0)
            wait = ready - now
            if wait <= 0:
                self._domain_slots[domain] = now + self.domain_cooldown
                return
            await asyncio.sleep(min(wait, 1.0))

    async def _sleep_jitter(self) -> None:
        if self.delay_max <= 0:
            return
        upper = max(self.delay_min, self.delay_max)
        lower = min(self.delay_min, upper)
        await asyncio.sleep(random.uniform(lower, upper))

    def _random_ip(self) -> str:
        return ".".join(str(random.randint(11, 223)) for _ in range(4))

    def _build_headers(self, ua: str, url: str) -> dict:
        headers = {
            "User-Agent": ua,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "X-Forwarded-For": self._random_ip(),
        }
        referer = random.choice(DEFAULT_REFERERS)
        headers["Referer"] = referer
        return headers

    async def _fetch_single(self, shared_client: Optional[httpx.AsyncClient], url: str) -> FetchResult:
        async with self.semaphore:
            attempt = 0
            last_error = None
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            while attempt <= self.max_retries:
                ua = USER_AGENTS[attempt % len(USER_AGENTS)]
                timeout = max(self.base_timeout * (0.6**attempt), 4.0)
                await self._reserve_domain_slot(domain)
                await self._sleep_jitter()
                headers = self._build_headers(ua, url)
                proxy = random.choice(self.proxies) if self.proxies else None
                start = time.perf_counter()
                self.logger.info(
                    "Crawler fetch start url=%s attempt=%s timeout=%.1fs ua=%s proxy=%s",
                    url,
                    attempt + 1,
                    timeout,
                    ua,
                    proxy or "-",
                )
                try:
                    if proxy:
                        async with httpx.AsyncClient(follow_redirects=True, proxies=proxy, trust_env=False) as client:
                            resp = await client.get(url, timeout=timeout, headers=headers)
                    elif shared_client is not None:
                        resp = await shared_client.get(url, timeout=timeout, headers=headers)
                    else:
                        async with httpx.AsyncClient(follow_redirects=True) as client:
                            resp = await client.get(url, timeout=timeout, headers=headers)
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    content_type = resp.headers.get("content-type")
                    download_bytes = len(resp.content or b"")
                    self.logger.info(
                        "Crawler fetch done url=%s status=%s final_url=%s ctype=%s bytes=%s elapsed=%.1fms",
                        url,
                        resp.status_code,
                        str(resp.url),
                        content_type,
                        download_bytes,
                        elapsed_ms,
                    )
                    if resp.status_code == 403 and attempt < self.max_retries:
                        preview = safe_preview(resp.text, 200)
                        self.logger.warning(
                            "Crawler HTTP 403 url=%s attempt=%s preview=%s，随机等待后重试",
                            str(resp.url),
                            attempt + 1,
                            preview,
                        )
                        attempt += 1
                        continue
                    if resp.status_code >= 400:
                        preview = safe_preview(resp.text, 300)
                        self.logger.warning(
                            "Crawler HTTP %s url=%s preview=%s",
                            resp.status_code,
                            str(resp.url),
                            preview,
                        )
                    if "text/html" not in (content_type or ""):
                        return FetchResult(
                            url=url,
                            final_url=str(resp.url),
                            status=resp.status_code,
                            content_type=content_type,
                            html=None,
                            error="非 HTML 内容",
                        )
                    return FetchResult(
                        url=url,
                        final_url=str(resp.url),
                        status=resp.status_code,
                        content_type=content_type,
                        html=resp.text,
                    )
                except httpx.HTTPError as exc:
                    last_error = str(exc)
                    self.logger.error("Crawler network error url=%s error=%r", url, exc)
                    if attempt >= self.max_retries:
                        return FetchResult(
                            url=url,
                            final_url=url,
                            status=0,
                            content_type=None,
                            html=None,
                            error=str(exc),
                        )
                    attempt += 1
            # 重试后仍失败
            return FetchResult(
                url=url,
                final_url=url,
                status=403,
                content_type=None,
                html=None,
                error=last_error or "HTTP 403",
            )

    async def fetch(self, urls: List[str]) -> List[FetchResult]:
        shared_client = None
        if not self.proxies:
            shared_client = httpx.AsyncClient(follow_redirects=True)
        try:
            tasks = [self._fetch_single(shared_client, url) for url in urls]
            return await asyncio.gather(*tasks)
        finally:
            if shared_client is not None:
                await shared_client.aclose()

