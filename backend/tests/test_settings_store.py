from app.schemas.app_settings import AppSettings, AppSettingsUpdate
from app.services.settings_store import apply_update


def test_apply_update_preserves_google_keys_on_partial_search_update():
    current = AppSettings()
    current.search.google_cse_api_key = "key123"
    current.search.google_cse_cx = "cx999"

    update_payload = {"search": {"mode": "force", "max_urls": 9}}
    update = AppSettingsUpdate.model_validate(update_payload)

    updated = apply_update(current, update)

    assert updated.search.google_cse_api_key == "key123"
    assert updated.search.google_cse_cx == "cx999"
    assert updated.search.mode == "force"
    assert updated.search.max_urls == 9

