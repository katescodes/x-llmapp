import json
import os
from pathlib import Path
from typing import Tuple

from ..schemas.app_settings import (
    AppSettings,
    AppSettingsResponse,
    AppSettingsUpdate,
    EmbeddingConfig,
    GoogleKeyUpdate,
)
from app.schemas.embedding_config import EmbeddingConfigResponse
from app.services.embedding_provider_store import get_embedding_store
from app.config import get_settings

settings = get_settings()
os.makedirs(os.path.dirname(settings.APP_SETTINGS_PATH), exist_ok=True)
DEFAULT_APP_SETTINGS = (
    Path(__file__).resolve().parent.parent / "config_defaults/app_settings.json"
)


def _load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _atomic_write(path: str, data: dict) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def _migrate_raw_settings(raw: dict) -> tuple[dict, bool]:
    changed = False
    if "embedding_config" not in raw:
        bge_cfg = raw.pop("bge_m3", None) or {}
        default_embed = EmbeddingConfig().model_dump()
        if bge_cfg:
            default_embed["model"] = bge_cfg.get("model_name") or default_embed["model"]
            batch_size = bge_cfg.get("batch_size")
            if batch_size:
                default_embed["batch_size"] = max(1, int(batch_size))
            dense_dim = bge_cfg.get("dense_dim")
            if dense_dim:
                default_embed["dense_dim"] = dense_dim
        raw["embedding_config"] = default_embed
        changed = True
    if "search" in raw and "has_google_key" in raw["search"]:
        raw["search"].pop("has_google_key", None)
        changed = True
    return raw, changed


def load_settings() -> AppSettings:
    raw = _load_json(settings.APP_SETTINGS_PATH)
    if not raw and DEFAULT_APP_SETTINGS.exists():
        default_raw = _load_json(str(DEFAULT_APP_SETTINGS))
        if default_raw:
            _atomic_write(settings.APP_SETTINGS_PATH, default_raw)
            return AppSettings.model_validate(default_raw)
    if not raw:
        defaults = AppSettings()
        _atomic_write(settings.APP_SETTINGS_PATH, defaults.model_dump())
        return defaults
    raw, migrated = _migrate_raw_settings(raw)
    app_settings = AppSettings.model_validate(raw)
    if migrated:
        save_settings(app_settings)
    return app_settings


def save_settings(app_settings: AppSettings) -> None:
    data = app_settings.model_dump()
    _atomic_write(settings.APP_SETTINGS_PATH, data)


def apply_update(current: AppSettings, update: AppSettingsUpdate) -> AppSettings:
    data = current.model_dump()
    patch = update.model_dump(exclude_unset=True)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            merged = data[key].copy()
            merged.update(value)
            data[key] = merged
        else:
            data[key] = value
    return AppSettings.model_validate(data)


def update_google_key(current: AppSettings, payload: GoogleKeyUpdate) -> AppSettings:
    data = current.model_dump()
    search_cfg = data.get("search", {})
    patch = payload.model_dump(exclude_unset=True)
    search_cfg.update(patch)
    data["search"] = search_cfg
    return AppSettings.model_validate(data)


def sanitize_settings(app_settings: AppSettings) -> Tuple[AppSettings, bool]:
    has_search_key = bool(app_settings.search.google_cse_api_key)
    data = app_settings.model_dump()
    data["search"]["google_cse_api_key"] = None
    sanitized = AppSettings.model_validate(data)
    return sanitized, has_search_key


def serialize_settings_response(app_settings: AppSettings) -> AppSettingsResponse:
    sanitized, has_search_key = sanitize_settings(app_settings)
    data = sanitized.model_dump()
    data["search"]["has_google_key"] = has_search_key
    embedding_store = get_embedding_store()
    default_provider = embedding_store.get_default()
    if default_provider:
        data["embedding_config"] = EmbeddingConfigResponse(
            base_url=str(default_provider.base_url),
            endpoint_path=default_provider.endpoint_path,
            model=default_provider.model,
            timeout_ms=default_provider.timeout_ms,
            batch_size=default_provider.batch_size,
            output_dense=default_provider.output_dense,
            output_sparse=default_provider.output_sparse,
            dense_dim=default_provider.dense_dim,
            sparse_format=default_provider.sparse_format,
            has_api_key=bool(default_provider.api_key),
        ).model_dump()
    else:
        data["embedding_config"] = None
    return AppSettingsResponse.model_validate(data)

