"""
Services Tender Shim - 向后兼容层
实际实现已迁移到 app.works.tender.snippet

从 Step 5 开始，snippet 相关功能已迁移到 works/tender/snippet/
此目录仅为向后兼容保留
"""
from app.works.tender.snippet.snippet_extract import (
    extract_snippets,
    extract_snippets_for_fragment
)
from app.works.tender.snippet.snippet_llm import generate_snippet_content
from app.works.tender.snippet.snippet_locator import locate_snippets_in_asset
from app.works.tender.snippet.doc_blocks import (
    extract_doc_blocks,
    parse_structure_from_blocks
)

__all__ = [
    "extract_snippets",
    "extract_snippets_for_fragment",
    "generate_snippet_content",
    "locate_snippets_in_asset",
    "extract_doc_blocks",
    "parse_structure_from_blocks",
]

