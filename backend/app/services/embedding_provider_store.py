from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.config import get_settings
from app.schemas.embedding_provider import (
    EmbeddingProviderIn,
    EmbeddingProviderStored,
    EmbeddingProviderUpdate,
)

settings = get_settings()


class EmbeddingProviderStore:
    def __init__(self, data_file: Optional[str] = None):
        raw_path = data_file or settings.EMBEDDING_PROVIDERS_PATH
        path = Path(raw_path)
        if not path.is_absolute():
            base_dir = Path(__file__).parent.parent.parent
            path = (base_dir / raw_path).resolve()
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._providers: Dict[str, EmbeddingProviderStored] = {}
        self._default_id: Optional[str] = None

        self._load()
        self._maybe_import_legacy()

    def _maybe_import_legacy(self) -> None:
        if self._providers:
            return
        from app.services import settings_store  # local import to avoid circular dependency

        settings = settings_store.load_settings()
        legacy = getattr(settings, "embedding_config", None)
        if not legacy or not getattr(legacy, "base_url", None):
            return
        payload = EmbeddingProviderIn(
            name="default-http-embedding",
            base_url=legacy.base_url,  # type: ignore[arg-type]
            endpoint_path=legacy.endpoint_path,
            model=legacy.model,
            api_key=legacy.api_key,
            timeout_ms=legacy.timeout_ms,
            batch_size=legacy.batch_size,
            output_dense=legacy.output_dense,
            output_sparse=legacy.output_sparse,
            dense_dim=legacy.dense_dim,
            sparse_format=legacy.sparse_format,
        )
        try:
            self.create(payload)
        except Exception:  # noqa: BLE001
            pass

    def _load(self) -> None:
        if not self._path.exists():
            self._providers = {}
            self._default_id = None
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._providers = {}
            self._default_id = None
            return
        providers = {}
        for entry in data.get("providers", []):
            provider = EmbeddingProviderStored(**entry)
            providers[provider.id] = provider
        self._providers = providers
        self._default_id = data.get("default_provider_id")

    def _save(self) -> None:
        payload = {
            "providers": [
                provider.model_dump(mode="json") for provider in self._providers.values()
            ],
            "default_provider_id": self._default_id,
        }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._path)

    def list_providers(self) -> List[EmbeddingProviderStored]:
        with self._lock:
            return [provider for provider in self._providers.values()]

    def get_provider(self, provider_id: str) -> Optional[EmbeddingProviderStored]:
        with self._lock:
            return self._providers.get(provider_id)

    def get_default(self) -> Optional[EmbeddingProviderStored]:
        with self._lock:
            if self._default_id and self._default_id in self._providers:
                return self._providers[self._default_id]
            return None

    def create(self, payload: EmbeddingProviderIn) -> EmbeddingProviderStored:
        with self._lock:
            if any(p.name == payload.name for p in self._providers.values()):
                raise ValueError(f"Embedding provider '{payload.name}' 已存在")
            provider_id = uuid.uuid4().hex
            now = datetime.utcnow()
            stored = EmbeddingProviderStored(
                id=provider_id,
                created_at=now,
                updated_at=now,
                **payload.model_dump(),
            )
            if not self._providers:
                self._default_id = provider_id
            self._providers[provider_id] = stored
            self._save()
            return stored

    def update(self, provider_id: str, payload: EmbeddingProviderUpdate) -> EmbeddingProviderStored:
        with self._lock:
            if provider_id not in self._providers:
                raise ValueError("Embedding provider 不存在")
            target = self._providers[provider_id]
            data = payload.model_dump(exclude_unset=True)
            if "name" in data:
                name = data["name"]
                if name != target.name and any(p.name == name for p in self._providers.values()):
                    raise ValueError(f"Embedding provider '{name}' 已存在")
            if "api_key" in data:
                api_key = data.pop("api_key")
                target.api_key = api_key or None
            for key, value in data.items():
                setattr(target, key, value)
            target.updated_at = datetime.utcnow()
            self._save()
            return target

    def delete(self, provider_id: str) -> None:
        with self._lock:
            if provider_id not in self._providers:
                raise ValueError("Embedding provider 不存在")
            del self._providers[provider_id]
            if self._default_id == provider_id:
                self._default_id = None
            self._save()

    def set_default(self, provider_id: str) -> EmbeddingProviderStored:
        with self._lock:
            if provider_id not in self._providers:
                raise ValueError("Embedding provider 不存在")
            self._default_id = provider_id
            self._save()
            return self._providers[provider_id]

    def get_default_with_key(self) -> Optional[Tuple[EmbeddingProviderStored, Optional[str]]]:
        provider = self.get_default()
        if provider:
            return provider, provider.api_key
        return None


_embedding_store: Optional[EmbeddingProviderStore] = None


def get_embedding_store() -> EmbeddingProviderStore:
    global _embedding_store
    if _embedding_store is None:
        _embedding_store = EmbeddingProviderStore()
    return _embedding_store

