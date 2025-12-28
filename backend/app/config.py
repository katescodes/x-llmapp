from functools import lru_cache
from typing import Optional, Literal, List

from pydantic import BaseModel, Field
import os
from pathlib import Path
import re
from dotenv import load_dotenv

# 加载 .env（可选）
load_dotenv()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_data_dir() -> str:
    env_dir = os.getenv("APP_DATA_DIR")
    if env_dir:
        return env_dir
    container_dir = Path("/app/data")
    if container_dir.exists():
        return str(container_dir)
    return str((_PROJECT_ROOT / "data").resolve())


def _split_env_list(var_name: str, default_value: str) -> list[str]:
    raw = os.getenv(var_name, default_value)
    parts = re.split(r"[,\|]", raw)
    return [part.strip() for part in parts if part.strip()]


_DATA_DIR = _resolve_data_dir()
os.makedirs(_DATA_DIR, exist_ok=True)


def _blocked_domains_default() -> List[str]:
    raw = os.getenv("CRAWLER_BLOCKED_DOMAINS", "facebook.com,webcache.googleusercontent.com")
    return [part.strip().lower() for part in raw.split(",") if part.strip()]


def _crawler_proxies_default() -> List[str]:
    raw = os.getenv("CRAWLER_PROXIES", "")
    return [part.strip() for part in raw.split(",") if part.strip()]


def _search_mode_default() -> str:
    value = os.getenv("SEARCH_MODE", "smart").lower()
    if value not in {"off", "smart", "force"}:
        return "smart"
    return value


class Settings(BaseModel):
    # 兼容单一 LLM 的默认配置（多 LLM 时作为 fallback）
    LOCAL_LLM_BASE_URL: str = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:8001")
    LOCAL_LLM_MODEL: str = os.getenv("LOCAL_LLM_MODEL", "local-llm")
    LOCAL_LLM_ENDPOINT_PATH: str = os.getenv("LOCAL_LLM_ENDPOINT_PATH", "/v1/chat/completions")
    LOCAL_LLM_API_KEY: str | None = os.getenv("LOCAL_LLM_API_KEY")

    # SearXNG 搜索服务地址
    SEARXNG_BASE_URL: str = os.getenv("SEARXNG_BASE_URL", "http://localhost:8080")
    SEARXNG_ENGINES_ALLOWLIST: str = os.getenv(
        "SEARXNG_ENGINES_ALLOWLIST", "wikipedia,github,arxiv"
    )
    GOOGLE_CSE_API_KEY: Optional[str] = os.getenv("GOOGLE_CSE_API_KEY")
    GOOGLE_CSE_CX: Optional[str] = os.getenv("GOOGLE_CSE_CX")
    GOOGLE_CSE_COUNTRY_FILTERS: List[str] = Field(
        default_factory=lambda: _split_env_list(
            "GOOGLE_CSE_COUNTRY_FILTERS",
            "countryUS,countryCA,countryGB,countryDE,countryFR,countryNL,countrySE,countryFI,countryDK,countryNO,countryIE,countryIT,countryES,countryPT,countryBE,countryAT,countryCH",
        )
    )
    GOOGLE_CSE_LANGUAGE_RESTRICTIONS: List[str] = Field(
        default_factory=lambda: _split_env_list("GOOGLE_CSE_LANGUAGE_RESTRICTIONS", "lang_en")
    )
    GOOGLE_CSE_HL: str = os.getenv("GOOGLE_CSE_HL", "en")
    SEARCH_MODE: Literal["off", "smart", "force"] = _search_mode_default()  # type: ignore[assignment]
    SEARCH_DAILY_WARN: int = int(os.getenv("SEARCH_DAILY_WARN", "100"))
    SEARCH_DAILY_LIMIT: int = int(os.getenv("SEARCH_DAILY_LIMIT", "500"))
    APP_DATA_DIR: str = _DATA_DIR
    SEARCH_USAGE_STORAGE: str = os.getenv(
        "SEARCH_USAGE_STORAGE", str(Path(_DATA_DIR) / "search_usage.json")
    )
    SEARCH_HTTP_TIMEOUT: float = float(os.getenv("SEARCH_HTTP_TIMEOUT", "15"))
    GOOGLE_CSE_MIN_RESULTS_PER_QUERY: int = int(os.getenv("GOOGLE_CSE_MIN_RESULTS_PER_QUERY", "30"))
    GOOGLE_CSE_MAX_RESULTS_PER_QUERY: int = int(os.getenv("GOOGLE_CSE_MAX_RESULTS_PER_QUERY", "40"))
    CRAWLER_BLOCKED_DOMAINS: List[str] = Field(default_factory=_blocked_domains_default)
    CRAWLER_DELAY_MIN: float = float(os.getenv("CRAWLER_DELAY_MIN", "0.6"))
    CRAWLER_DELAY_MAX: float = float(os.getenv("CRAWLER_DELAY_MAX", "1.8"))
    CRAWLER_DOMAIN_COOLDOWN: float = float(os.getenv("CRAWLER_DOMAIN_COOLDOWN", "2.5"))
    CRAWLER_PROXIES: List[str] = Field(default_factory=_crawler_proxies_default)
    APP_SETTINGS_PATH: str = os.getenv("APP_SETTINGS_PATH", str(Path(_DATA_DIR) / "app_settings.json"))
    # Milvus 配置（支持 Lite 和 Standalone 两种模式）
    MILVUS_LITE_PATH: str = os.getenv("MILVUS_LITE_PATH", str(Path(_DATA_DIR) / "milvus.db"))
    MILVUS_URI: Optional[str] = os.getenv("MILVUS_URI", None)  # 远程 Milvus 地址 (host:port)
    MILVUS_USE_STANDALONE: bool = os.getenv("MILVUS_USE_STANDALONE", "false").lower() == "true"
    EMBEDDING_PROVIDERS_PATH: str = os.getenv(
        "EMBEDDING_PROVIDERS_PATH", str(Path(_DATA_DIR) / "embedding_providers.json")
    )
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "localgpt")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "localgpt")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "localgpt")
    POSTGRES_DSN: Optional[str] = os.getenv("POSTGRES_DSN")
    POSTGRES_POOL_MIN: int = int(os.getenv("POSTGRES_POOL_MIN", "1"))
    POSTGRES_POOL_MAX: int = int(os.getenv("POSTGRES_POOL_MAX", "10"))

    # 是否启用 Mock 模式（对所有 LLM 生效，或者逐个 LLM 配置覆盖）
    MOCK_LLM: bool = os.getenv("MOCK_LLM", "true").lower() == "true"
    
    # 语音转文字（ASR）配置 - 使用本地 Whisper 模型
    ASR_ENABLED: bool = os.getenv("ASR_ENABLED", "true").lower() == "true"
    # Whisper 模型大小: tiny, base, small, medium, large-v2, large-v3
    # tiny: 最快但准确度低 (~1GB RAM)
    # base: 速度快，准确度中等 (~1GB RAM)
    # small: 平衡速度和准确度 (~2GB RAM)
    # medium: 高准确度 (~5GB RAM)
    # large-v3: 最高准确度但最慢 (~10GB RAM)
    ASR_MODEL: str = os.getenv("ASR_MODEL", "base")
    ASR_DEVICE: str = os.getenv("ASR_DEVICE", "cpu")  # cpu, cuda, auto
    ASR_COMPUTE_TYPE: str = os.getenv("ASR_COMPUTE_TYPE", "int8")  # int8, float16, float32
    ASR_LANGUAGE: Optional[str] = os.getenv("ASR_LANGUAGE")  # zh, en, auto
    ASR_BEAM_SIZE: int = int(os.getenv("ASR_BEAM_SIZE", "5"))
    
    # 音频预处理
    ASR_ENABLE_PREPROCESSING: bool = os.getenv("ASR_ENABLE_PREPROCESSING", "true").lower() == "true"
    ASR_NOISE_REDUCTION: bool = os.getenv("ASR_NOISE_REDUCTION", "true").lower() == "true"
    ASR_NORMALIZE_AUDIO: bool = os.getenv("ASR_NORMALIZE_AUDIO", "true").lower() == "true"
    
    # 说话人识别（Diarization）- CPU 版本默认禁用（需要 PyTorch）
    ASR_ENABLE_DIARIZATION: bool = os.getenv("ASR_ENABLE_DIARIZATION", "false").lower() == "true"
    ASR_DIARIZATION_MIN_SPEAKERS: int = int(os.getenv("ASR_DIARIZATION_MIN_SPEAKERS", "1"))
    ASR_DIARIZATION_MAX_SPEAKERS: int = int(os.getenv("ASR_DIARIZATION_MAX_SPEAKERS", "10"))
    # pyannote 需要 HuggingFace token
    ASR_HF_TOKEN: Optional[str] = os.getenv("ASR_HF_TOKEN")
    
    # 时间戳
    ASR_ENABLE_TIMESTAMPS: bool = os.getenv("ASR_ENABLE_TIMESTAMPS", "true").lower() == "true"
    ASR_WORD_TIMESTAMPS: bool = os.getenv("ASR_WORD_TIMESTAMPS", "false").lower() == "true"

    # 模板 LLM 分析配置
    TEMPLATE_LLM_ANALYSIS_ENABLED: bool = os.getenv("TEMPLATE_LLM_ANALYSIS_ENABLED", "true").lower() == "true"
    TEMPLATE_LLM_ANALYSIS_MODEL: str = os.getenv("TEMPLATE_LLM_ANALYSIS_MODEL", "gpt-oss-120b")
    TEMPLATE_LLM_ANALYSIS_MAX_BLOCKS: int = int(os.getenv("TEMPLATE_LLM_ANALYSIS_MAX_BLOCKS", "400"))
    TEMPLATE_LLM_ANALYSIS_MAX_CHARS_PER_BLOCK: int = int(os.getenv("TEMPLATE_LLM_ANALYSIS_MAX_CHARS_PER_BLOCK", "300"))
    TEMPLATE_LLM_ANALYSIS_CACHE_BY_SHA256: bool = os.getenv("TEMPLATE_LLM_ANALYSIS_CACHE_BY_SHA256", "true").lower() == "true"
    TEMPLATE_LLM_ANALYSIS_VERSION: str = os.getenv("TEMPLATE_LLM_ANALYSIS_VERSION", "v1")


class FeatureFlags(BaseModel):
    """
    Feature Flags 配置 - 用于控制新功能的启用/禁用
    所有 flags 默认为 False（关闭），确保不影响现有功能
    """
    # 平台任务调度能力
    PLATFORM_JOBS_ENABLED: bool = os.getenv("PLATFORM_JOBS_ENABLED", "false").lower() == "true"
    
    # 证据片段标注能力
    EVIDENCE_SPANS_ENABLED: bool = os.getenv("EVIDENCE_SPANS_ENABLED", "false").lower() == "true"
    
    # 文档存储双写模式
    DOCSTORE_DUALWRITE: bool = os.getenv("DOCSTORE_DUALWRITE", "false").lower() == "true"
    
    # 评审案例双写模式
    REVIEWCASE_DUALWRITE: bool = os.getenv("REVIEWCASE_DUALWRITE", "false").lower() == "true"
    
    # 规则集解析能力
    RULESET_PARSE_ENABLED: bool = os.getenv("RULESET_PARSE_ENABLED", "false").lower() == "true"
    
    # 规则评估引擎
    RULES_EVALUATOR_ENABLED: bool = os.getenv("RULES_EVALUATOR_ENABLED", "false").lower() == "true"
    
    # 异步文档摄入
    ASYNC_INGEST_ENABLED: bool = os.getenv("ASYNC_INGEST_ENABLED", "false").lower() == "true"


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_feature_flags() -> FeatureFlags:
    """获取 Feature Flags 配置（单例缓存）"""
    return FeatureFlags()
