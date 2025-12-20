"""
DEPRECATED: Shim for backward compatibility
Please use: from app.platform.vectorstore.milvus_docseg_store import MilvusDocSegStore, milvus_docseg_store
"""
from app.platform.vectorstore.milvus_docseg_store import (
    COLLECTION_NAME,
    MilvusDocSegStore,
    milvus_docseg_store,
)

__all__ = [
    "COLLECTION_NAME",
    "MilvusDocSegStore",
    "milvus_docseg_store",
]
