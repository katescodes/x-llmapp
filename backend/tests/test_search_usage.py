import json
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import HTTPException
from backend.app.services.search_usage import SearchUsageManager


def test_search_usage_increment_warn_limit(tmp_path):
    storage = tmp_path / "usage.json"
    clock = lambda: datetime(2025, 1, 1, tzinfo=timezone.utc)
    manager = SearchUsageManager(
        storage_path=str(storage),
        default_warn=2,
        default_limit=3,
        clock=clock,
    )

    count, warn = manager.register_search()
    assert count == 1 and warn is False
    count, warn = manager.register_search()
    assert count == 2 and warn is True
    count, warn = manager.register_search()
    assert count == 3 and warn is True
    with pytest.raises(HTTPException) as exc:
        manager.register_search()
    assert exc.value.status_code == 429


def test_search_usage_cross_day(tmp_path):
    storage = tmp_path / "usage.json"
    first_day = datetime(2025, 1, 1, tzinfo=timezone.utc)
    second_day = first_day + timedelta(days=1)

    manager_day1 = SearchUsageManager(
        storage_path=str(storage),
        default_warn=10,
        default_limit=20,
        clock=lambda: first_day,
    )
    manager_day1.register_search()
    with open(storage, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data[first_day.strftime("%Y-%m-%d")] == 1

    manager_day2 = SearchUsageManager(
        storage_path=str(storage),
        default_warn=10,
        default_limit=20,
        clock=lambda: second_day,
    )
    count, warn = manager_day2.register_search()
    assert count == 1 and warn is False
    with open(storage, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data[second_day.strftime("%Y-%m-%d")] == 1

