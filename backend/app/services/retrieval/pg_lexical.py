"""
PG Lexical Search Shim
实际实现已迁移到 app.platform.retrieval.providers.legacy.pg_lexical
"""
from app.platform.retrieval.providers.legacy.pg_lexical import search_lexical

__all__ = ["search_lexical"]
