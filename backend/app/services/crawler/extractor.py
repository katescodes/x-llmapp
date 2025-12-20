import hashlib
import logging
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup
from trafilatura import extract as trafilatura_extract

from app.services.logging.request_logger import (
    get_request_logger,
    is_debug_enabled,
    safe_preview,
)

logger = logging.getLogger(__name__)


@dataclass
class ExtractedDocument:
    url: str
    title: str
    text: str
    content_hash: str


def _fallback_extract(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    return text


def extract_content(
    html: str,
    url: str,
    default_title: str = "",
    request_id: str | None = None,
) -> Optional[ExtractedDocument]:
    req_logger = get_request_logger(logger, request_id)
    raw_bytes = len(html.encode("utf-8", errors="ignore"))
    text = trafilatura_extract(html, url=url, include_links=False, include_tables=False)
    if not text:
        text = _fallback_extract(html)
    if not text.strip():
        req_logger.warning("Extractor empty result url=%s raw_bytes=%s", url, raw_bytes)
        return None

    soup = BeautifulSoup(html, "lxml")
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else default_title or url

    content_hash = hashlib.sha1(text.encode("utf-8")).hexdigest()
    extracted_chars = len(text)
    req_logger.info(
        "Extractor success url=%s raw_bytes=%s extracted_chars=%s",
        url,
        raw_bytes,
        extracted_chars,
    )
    if is_debug_enabled():
        req_logger.debug("Extractor preview=%s", safe_preview(text, 200))
    if extracted_chars < 300:
        req_logger.warning(
            "Extractor short text url=%s chars=%s preview=%s",
            url,
            extracted_chars,
            safe_preview(text, 120),
        )
    return ExtractedDocument(url=url, title=title, text=text, content_hash=content_hash)

