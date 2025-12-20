from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.services.google_search import google_search_multi
from ..schemas.app_settings import (
    AppSettingsResponse,
    AppSettingsUpdate,
    GoogleKeyUpdate,
    GoogleSearchTestRequest,
)
from ..services.settings_store import (
    apply_update,
    load_settings,
    save_settings,
    serialize_settings_response,
    update_google_key,
)

router = APIRouter(prefix="/api/settings", tags=["app-settings"])


@router.get("/app", response_model=AppSettingsResponse)
def get_app_settings():
    settings = load_settings()
    return serialize_settings_response(settings)


@router.put("/app", response_model=AppSettingsResponse)
def update_app_settings(payload: AppSettingsUpdate):
    current = load_settings()
    updated = apply_update(current, payload)
    save_settings(updated)
    return serialize_settings_response(updated)


@router.put("/search/google-key", response_model=dict)
def update_google_credentials(payload: GoogleKeyUpdate):
    if not payload.google_cse_api_key and not payload.google_cse_cx:
        raise HTTPException(status_code=400, detail="需要提供 api_key 或 cx")
    current = load_settings()
    updated = update_google_key(current, payload)
    save_settings(updated)
    return {"has_google_key": bool(updated.search.google_cse_api_key)}


@router.post("/search/test", response_model=dict)
async def test_google_search(payload: GoogleSearchTestRequest):
    current = load_settings()
    settings = get_settings()
    api_key = (
        payload.google_cse_api_key
        or current.search.google_cse_api_key
        or settings.GOOGLE_CSE_API_KEY
    )
    cx = (
        payload.google_cse_cx
        or current.search.google_cse_cx
        or settings.GOOGLE_CSE_CX
    )
    if not api_key or not cx:
        raise HTTPException(status_code=400, detail="未配置 Google CSE API Key 或 CX")
    try:
        await google_search_multi(
            payload.query or "ping",
            want=1,
            api_key=api_key,
            cx=cx,
            timeout=settings.SEARCH_HTTP_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Google 搜索失败: {exc}") from exc
    return {"ok": True}

