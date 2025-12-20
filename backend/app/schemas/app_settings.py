from typing import Literal, Optional

from pydantic import BaseModel, Field


class EmbeddingConfig(BaseModel):
    provider: Literal["http"] = "http"
    base_url: str = "http://localhost:8081"
    endpoint_path: str = "/v1/embeddings"
    api_key: Optional[str] = None
    model: str = "bge-m3"
    timeout_ms: int = Field(default=30000, ge=1000, le=120_000)
    batch_size: int = Field(default=16, ge=1, le=256)
    output_dense: bool = True
    output_sparse: bool = True
    dense_dim: Optional[int] = Field(default=None, ge=1)
    sparse_format: Literal["indices_values"] = "indices_values"


class SearchConfig(BaseModel):
    provider: Literal["cse", "html", "browser"] = "cse"
    mode: Literal["off", "smart", "force"] = "smart"
    google_cse_api_key: Optional[str] = None
    google_cse_cx: Optional[str] = None
    warn: int = 100
    limit: int = 500
    max_urls: int = 5
    results_per_query: int = 5


class RetrievalConfig(BaseModel):
    topk_dense: int = 20
    topk_sparse: int = 20
    topk_final: int = 8
    min_sources: int = 30
    ranker: Literal["rrf", "weighted"] = "rrf"
    rrf_k: int = 60
    weight_dense: float = 0.6
    weight_sparse: float = 0.4


class CrawlConfig(BaseModel):
    max_pages: int = 5
    concurrency: int = 4
    timeout_sec: int = 20
    max_retries: int = 2
    delay_min: float = Field(default=0.6, ge=0.0)
    delay_max: float = Field(default=1.8, ge=0.0)
    domain_cooldown: float = Field(default=2.5, ge=0.0)


class AppSettings(BaseModel):
    embedding_config: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    crawl: CrawlConfig = Field(default_factory=CrawlConfig)


class AppSettingsUpdate(BaseModel):
    embedding_config: Optional[EmbeddingConfig] = None
    search: Optional[SearchConfig] = None
    retrieval: Optional[RetrievalConfig] = None
    crawl: Optional[CrawlConfig] = None


class GoogleKeyUpdate(BaseModel):
    google_cse_api_key: Optional[str] = None
    google_cse_cx: Optional[str] = None


class GoogleSearchTestRequest(BaseModel):
    google_cse_api_key: Optional[str] = None
    google_cse_cx: Optional[str] = None
    query: str = "ping"


class EmbeddingConfigUpdate(BaseModel):
    provider: Optional[Literal["http"]] = None
    base_url: Optional[str] = None
    endpoint_path: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    timeout_ms: Optional[int] = Field(default=None, ge=1000, le=120_000)
    batch_size: Optional[int] = Field(default=None, ge=1, le=256)
    output_dense: Optional[bool] = None
    output_sparse: Optional[bool] = None
    dense_dim: Optional[int] = Field(default=None, ge=1)
    sparse_format: Optional[Literal["indices_values"]] = None


class SearchConfigResponse(SearchConfig):
    has_google_key: bool = False


class EmbeddingConfigResponse(EmbeddingConfig):
    has_api_key: bool = False


class AppSettingsResponse(BaseModel):
    embedding_config: Optional[EmbeddingConfigResponse] = None
    search: SearchConfigResponse
    retrieval: RetrievalConfig
    crawl: CrawlConfig

