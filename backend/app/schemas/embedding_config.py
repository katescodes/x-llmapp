from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class EmbeddingConfigResponse(BaseModel):
    base_url: str
    endpoint_path: str
    model: str
    timeout_ms: int
    batch_size: int
    output_dense: bool
    output_sparse: bool
    dense_dim: Optional[int] = None
    sparse_format: str
    has_api_key: bool = False

