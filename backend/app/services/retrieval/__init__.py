"""
Legacy Retrieval Shim
这个模块保留用于向后兼容，实际实现已迁移到 platform/retrieval/providers/legacy/
"""
from app.platform.retrieval.providers.legacy.retriever import retrieve

__all__ = ["retrieve"]
