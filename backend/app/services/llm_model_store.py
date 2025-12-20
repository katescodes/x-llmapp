import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import ValidationError

from ..schemas.llm_config import LLMModelIn, LLMModelStored, LLMModelUpdate
from ..utils.llm_endpoints import normalize_base_url, normalize_endpoint_path
from app.config import get_settings

logger = logging.getLogger(__name__)
DEFAULT_LLM_MODELS = (
    Path(__file__).resolve().parent.parent / "config_defaults/llm_models.json"
)
_settings = get_settings()
DEFAULT_DATA_FILE = Path(_settings.APP_DATA_DIR) / "llm_models.json"


def _mask_secret(value: Optional[str]) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:3]}{'*' * (len(value) - 6)}{value[-3:]}"


class LLMModelStore:
    def __init__(self, data_file: Optional[str] = None):
        env_path = os.getenv("LLM_STORE_PATH")
        raw = data_file or env_path or str(DEFAULT_DATA_FILE)
        path = Path(raw)
        if not path.is_absolute():
            base_dir = Path(__file__).parent.parent.parent
            path = (base_dir / raw).resolve()

        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._models: Dict[str, LLMModelStored] = {}
        self._default_id: Optional[str] = None
        self._bootstrap_enabled = data_file is None and env_path is None

        self._load()
        logger.info(
            "LLMModelStore loaded path=%s models=%d default=%s",
            self._path,
            len(self._models),
            self._default_id,
        )

    # ---------- persistence ----------

    def _load(self) -> None:
        if not self._path.exists():
            if self._bootstrap_enabled:
                self._bootstrap_from_defaults()
            return

        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            logger.warning("LLMModelStore: data file corrupted, resetting.")
            self._models = {}
            self._default_id = None
            return

        self._models = {}
        for item in data.get("models", []):
            model = LLMModelStored(**item)
            self._normalize_model(model)
            self._models[model.id] = model
        self._default_id = data.get("default_model_id")

    def _save(self) -> None:
        payload = {
            "models": [m.model_dump(mode="json") for m in self._models.values()],
            "default_model_id": self._default_id,
        }
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        tmp.replace(self._path)

    @staticmethod
    def _normalize_model(model: LLMModelStored) -> None:
        model.base_url = normalize_base_url(model.base_url)
        model.endpoint_path = normalize_endpoint_path(model.endpoint_path)

    def _bootstrap_from_defaults(self) -> None:
        self._models = {}
        self._default_id = None
        if not DEFAULT_LLM_MODELS.exists():
            return
        try:
            with open(DEFAULT_LLM_MODELS, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            logger.warning("LLMModelStore: default models invalid, skipping bootstrap.")
            return

        entries = data.get("models", [])
        for entry in entries:
            try:
                llm_in = LLMModelIn(**entry)
            except ValidationError as exc:
                logger.warning("LLMModelStore: invalid default entry %s", exc)
                continue
            stored = LLMModelStored(**llm_in.model_dump())
            self._normalize_model(stored)
            self._models[stored.id] = stored

        if not self._models:
            return

        default_name = data.get("default_name")
        if default_name:
            for model in self._models.values():
                if model.name == default_name:
                    model.is_default = True
                    self._default_id = model.id
                    break

        if not self._default_id:
            first = next(iter(self._models.values()))
            first.is_default = True
            self._default_id = first.id

        self._save()

    # ---------- CRUD ----------

    def list_models(self) -> List[LLMModelStored]:
        with self._lock:
            return [model for model in self._models.values()]

    def get_model(self, model_id: str) -> Optional[LLMModelStored]:
        """
        获取模型配置（兼容多种传参方式）
        - 支持内部 ID（uuid）
        - 兼容按 name 查询（如 "oss120B"）
        - 兼容按 model 字段查询（如 "gpt-oss-120b"）
        """
        with self._lock:
            # 1) 直接按内部 id 查
            m = self._models.get(model_id)
            if m:
                return m

            # 2) 兼容：按 name 或 model 字段查
            candidates: List[LLMModelStored] = []
            for mm in self._models.values():
                if mm.name == model_id or mm.model == model_id:
                    candidates.append(mm)

            if not candidates:
                return None

            # 3) 多个候选时优先默认模型
            for mm in candidates:
                if mm.is_default:
                    return mm

            # 4) 否则返回第一个（保持确定性：按 id 排序）
            candidates.sort(key=lambda x: x.id)
            return candidates[0]

    def get_model_with_token(self, model_id: str) -> Optional[Tuple[LLMModelStored, Optional[str]]]:
        with self._lock:
            model = self._models.get(model_id)
            if not model:
                return None
            return model, model.api_key

    def create_model(self, data: LLMModelIn) -> LLMModelStored:
        with self._lock:
            if any(m.name == data.name for m in self._models.values()):
                raise ValueError(f"模型名称 '{data.name}' 已存在")

            stored = LLMModelStored(**data.model_dump())
            self._normalize_model(stored)
            if not self._models:
                stored.is_default = True
                self._default_id = stored.id

            self._models[stored.id] = stored
            self._save()
            return stored

    def update_model(self, model_id: str, data: LLMModelUpdate) -> LLMModelStored:
        with self._lock:
            if model_id not in self._models:
                raise ValueError("模型不存在")

            target = self._models[model_id]

            if data.name and data.name != target.name:
                if any(m.name == data.name for m in self._models.values()):
                    raise ValueError(f"模型名称 '{data.name}' 已存在")

            payload = data.model_dump(exclude_unset=True)
            if "api_key" in payload:
                api_key = payload.pop("api_key")
                if api_key is not None and api_key != "":
                    target.api_key = api_key
                # None/空串 => 不修改

            for key, value in payload.items():
                setattr(target, key, value)

            self._normalize_model(target)
            target.updated_at = datetime.utcnow()
            self._save()
            return target

    def delete_model(self, model_id: str) -> None:
        with self._lock:
            if model_id not in self._models:
                raise ValueError("模型不存在")

            if self._default_id == model_id:
                # 默认模型不能直接删除
                raise ValueError("不能删除默认模型，请先切换默认")

            del self._models[model_id]
            self._save()

    def set_default_model(self, model_id: str) -> LLMModelStored:
        with self._lock:
            if model_id not in self._models:
                raise ValueError("模型不存在")
            self._default_id = model_id
            for m in self._models.values():
                m.is_default = m.id == model_id
            self._save()
            return self._models[model_id]

    def get_default_model(self) -> Optional[LLMModelStored]:
        with self._lock:
            if self._default_id and self._default_id in self._models:
                return self._models[self._default_id]
            fallback = next(iter(self._models.values()), None)
            if fallback:
                self._default_id = fallback.id
                fallback.is_default = True
                self._save()
            return fallback

    # ---------- serialization helpers ----------

    def to_dict(self, model: LLMModelStored) -> Dict[str, object]:
        base = model.model_dump()
        base.pop("api_key", None)
        base["has_token"] = bool(model.api_key)
        base["token_hint"] = _mask_secret(model.api_key)
        base["is_default"] = model.id == (self._default_id or "")
        return base

_llm_store: Optional[LLMModelStore] = None


def get_llm_store() -> LLMModelStore:
    global _llm_store
    if _llm_store is None:
        _llm_store = LLMModelStore()
    return _llm_store
