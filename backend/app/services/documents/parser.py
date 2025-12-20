"""
DEPRECATED: Shim for backward compatibility
Please use: from app.platform.ingest.parser import parse_document, ParsedDocument
"""
from app.platform.ingest.parser import (
    ParsedDocument,
    parse_document,
    TEXT_EXTS,
    HTML_EXTS,
    PDF_EXTS,
    DOCX_EXTS,
    AUDIO_EXTS,
)

__all__ = [
    "ParsedDocument",
    "parse_document",
    "TEXT_EXTS",
    "HTML_EXTS",
    "PDF_EXTS",
    "DOCX_EXTS",
    "AUDIO_EXTS",
]
