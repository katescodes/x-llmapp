from __future__ import annotations

import math
from typing import Dict, List, Optional

import httpx
import tldextract

from app.config import get_settings
from ..utils.text_utils import is_chinese_heavy

settings = get_settings()

GOOGLE_API_URL = "https://www.googleapis.com/customsearch/v1"

CR_PARAM = "countryUS|countryCA|countryGB|countryDE|countryFR|countryNL|countrySE|countryCH|countryEU"
LR_PARAM = "lang_en"
HL_PARAM = "en"

BLOCKED_SITES = [
    "site:.cn",
    "site:.hk",
    "site:.tw",
    "site:.mo",
    "site:baidu.com",
    "site:qq.com",
    "site:weibo.com",
    "site:weixin.qq.com",
]

BLOCKED_TLDS = {"cn", "hk", "tw", "mo", "ru"}
BLOCKED_DOMAINS = {
    "baidu.com",
    "qq.com",
    "weibo.com",
    "weixin.qq.com",
}
ALLOWED_SUFFIXES = {
    "com",
    "org",
    "net",
    "gov",
    "edu",
    "us",
    "ca",
    "uk",
    "co.uk",
    "de",
    "fr",
    "nl",
    "se",
    "ch",
    "eu",
    "ie",
    "it",
    "es",
    "pt",
    "be",
    "at",
    "dk",
    "no",
    "fi",
    "pl",
    "cz",
    "sk",
    "hu",
    "gr",
    "ro",
    "bg",
    "lt",
    "lv",
    "ee",
    "au",
    "nz",
    "biz",
    "info",
    "co",
    "io",
    "ai",
    "me",
}


def _build_query(user_query: str) -> str:
    block = " ".join(f"-{entry}" for entry in BLOCKED_SITES)
    return f"{user_query.strip()} {block}".strip()


def _is_url_allowed(url: str) -> bool:
    if not url:
        return False
    ext = tldextract.extract(url)
    suffix = (ext.suffix or "").lower()
    domain = f"{ext.domain}.{suffix}" if suffix else ext.domain
    if suffix in BLOCKED_TLDS:
        return False
    if domain in BLOCKED_DOMAINS:
        return False
    if suffix and suffix not in ALLOWED_SUFFIXES:
        return False
    return True


async def google_search_multi(
    query: str,
    *,
    want: int = 15,
    api_key: Optional[str] = None,
    cx: Optional[str] = None,
    timeout: float = 30.0,
    freshness_days: Optional[int] = None,
) -> List[Dict]:
    """Call Google Custom Search API with pagination &严格过滤（英文/欧美站点为主）."""

    effective_want = max(1, min(want, 50))
    merged: List[Dict] = []

    key = api_key or settings.GOOGLE_CSE_API_KEY or getattr(settings, "GOOGLE_API_KEY", None)
    cx_id = cx or settings.GOOGLE_CSE_CX or getattr(settings, "GOOGLE_CX_ID", None)
    if not key or not cx_id:
        raise RuntimeError("Google CSE key/cx 未配置。")

    async with httpx.AsyncClient(timeout=timeout) as client:
        page = 0
        max_per_page = 10

        while len(merged) < effective_want:
            page += 1
            start = (page - 1) * max_per_page + 1
            params = {
                "key": key,
                "cx": cx_id,
                "q": _build_query(query),
                "start": start,
                "num": max_per_page,
                "cr": CR_PARAM,
                "lr": LR_PARAM,
                "hl": HL_PARAM,
                "safe": "active",
            }
            if freshness_days and freshness_days > 0:
                params["dateRestrict"] = f"d{freshness_days}"

            resp = await client.get(GOOGLE_API_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            raw_items = data.get("items", []) or []

            if not raw_items:
                break

            for item in raw_items:
                link = item.get("link")
                if not link or not _is_url_allowed(link):
                    continue
                snippet = item.get("snippet") or ""
                # 在 snippet 层面先过滤掉明显中文结果，再计数
                if snippet and is_chinese_heavy(snippet, threshold=0.05):
                    continue
                merged.append(item)
                if len(merged) >= effective_want:
                    break

            if page > math.ceil(effective_want / max_per_page) + 2:
                break

    return merged[:effective_want]


def filter_chinese_entries(entries: List[Dict]) -> List[Dict]:
    """Filter entries where snippet looks Chinese heavy."""
    filtered: List[Dict] = []
    for item in entries:
        snippet = item.get("snippet") or ""
        if snippet and is_chinese_heavy(snippet):
            continue
        filtered.append(item)
    return filtered

