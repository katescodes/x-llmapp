from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class EmbeddingProviderIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    base_url: HttpUrl
    endpoint_path: str = "/v1/embeddings"
    model: str
    api_key: Optional[str] = None
    timeout_ms: int = Field(default=30000, ge=1000, le=120_000)
    batch_size: int = Field(default=16, ge=1, le=256)
    output_dense: bool = True
    output_sparse: bool = True
    dense_dim: Optional[int] = Field(default=None, ge=1)
    sparse_format: str = "indices_values"


class EmbeddingProviderUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    base_url: Optional[HttpUrl] = None
    endpoint_path: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    timeout_ms: Optional[int] = Field(default=None, ge=1000, le=120_000)
    batch_size: Optional[int] = Field(default=None, ge=1, le=256)
    output_dense: Optional[bool] = None
    output_sparse: Optional[bool] = None
    dense_dim: Optional[int] = Field(default=None, ge=1)
    sparse_format: Optional[str] = None


class EmbeddingProviderStored(EmbeddingProviderIn):
    id: str
    created_at: datetime
    updated_at: datetime

