"""
Legacy Retriever Shim
实际实现已迁移到 app.platform.retrieval.providers.legacy.retriever
"""
from app.platform.retrieval.providers.legacy.retriever import retrieve

__all__ = ["retrieve"]
