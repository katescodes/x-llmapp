from __future__ import annotations

import logging
import os
from typing import Any, Optional
from urllib.parse import urlparse

_DEBUG_TRACE = os.getenv("DEBUG_TRACE", "").lower() in {"1", "true", "yes", "on"}


class RequestLogger(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        request_id = self.extra.get("request_id")
        prefix = f"[req={request_id}] " if request_id else ""
        return prefix + msg, kwargs


def get_request_logger(base_logger: logging.Logger, request_id: Optional[str]) -> RequestLogger:
    return RequestLogger(base_logger, {"request_id": request_id or "-"})


def safe_preview(value: Any, limit: int = 200) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ").replace("\r", " ")
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def mask_host(url: Optional[str]) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    host = parsed.netloc or parsed.path.split("/")[0]
    if not host:
        return url
    prefix = f"{parsed.scheme}://" if parsed.scheme else ""
    return prefix + host


def mask_url(url: Optional[str]) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    masked = ""
    if parsed.scheme:
        masked += parsed.scheme + "://"
    if parsed.netloc:
        masked += parsed.netloc
    if parsed.path:
        masked += parsed.path
    return masked or url


def is_debug_enabled() -> bool:
    return _DEBUG_TRACE

