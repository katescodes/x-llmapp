import hashlib
import logging
from dataclasses import dataclass
from statistics import mean
from typing import List, Optional

from app.services.logging.request_logger import get_request_logger, is_debug_enabled

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    chunk_id: str
    url: str
    title: str
    text: str
    position: int


def chunk_document(
    url: str,
    title: str,
    text: str,
    target_chars: int = 1800,
    overlap_chars: int = 200,
    request_id: Optional[str] = None,
) -> List[Chunk]:
    req_logger = get_request_logger(logger, request_id)
    if not text.strip():
        req_logger.warning("Chunker received empty text url=%s", url)
        return []
    chunks: List[Chunk] = []
    start = 0
    position = 0
    length = len(text)
    while start < length:
        end = min(start + target_chars, length)
        chunk_text = text[start:end].strip()
        if chunk_text:
            seed = f"{url}-{position}-{chunk_text[:200]}"
            chunk_id = hashlib.sha1(seed.encode("utf-8")).hexdigest()
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    url=url,
                    title=title,
                    text=chunk_text,
                    position=position,
                )
            )
        if end == length:
            break
        start = end - overlap_chars
        if start < 0:
            start = 0
        position += 1

    if chunks:
        sizes = [len(c.text) for c in chunks]
        req_logger.info(
            "Chunker done url=%s num_chunks=%s avg=%s min=%s max=%s",
            url,
            len(chunks),
            int(mean(sizes)),
            min(sizes),
            max(sizes),
        )
        if is_debug_enabled():
            preview = [f"{c.chunk_id}:{len(c.text)}" for c in chunks[:2]]
            req_logger.debug("Chunker sample=%s", preview)
    else:
        req_logger.warning("Chunker produced no chunks url=%s", url)
    return chunks

