import json
import os
from datetime import datetime, timezone
from typing import Tuple, Callable
from fastapi import HTTPException
from app.config import get_settings

settings = get_settings()


class SearchUsageManager:
    def __init__(
        self,
        storage_path: str,
        default_warn: int,
        default_limit: int,
        clock: Callable[[], datetime] | None = None,
    ):
        self.storage_path = storage_path
        self.default_warn = default_warn
        self.default_limit = default_limit
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

    def _load(self) -> dict:
        if not os.path.exists(self.storage_path):
            return {}
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self, data: dict) -> None:
        tmp_path = f"{self.storage_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.storage_path)

    def _today_key(self) -> str:
        return self.clock().strftime("%Y-%m-%d")

    def register_search(self, warn: int | None = None, limit: int | None = None) -> Tuple[int, bool]:
        warn_threshold = warn or self.default_warn
        max_limit = limit or self.default_limit
        today = self._today_key()
        data = self._load()
        count = int(data.get(today, 0))
        if count >= max_limit:
            raise HTTPException(
                status_code=429,
                detail=f"今日联网搜索已达 {max_limit} 次上限，请明日再试。",
            )
        count += 1
        data[today] = count
        self._save(data)
        warn_triggered = count >= warn_threshold
        return count, warn_triggered


usage_manager = SearchUsageManager(
    storage_path=settings.SEARCH_USAGE_STORAGE,
    default_warn=settings.SEARCH_DAILY_WARN,
    default_limit=settings.SEARCH_DAILY_LIMIT,
)

