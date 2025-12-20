import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import llm_config
from app.services.llm_model_store import LLMModelStore, get_llm_store


@pytest.fixture
def temp_store(tmp_path):
    data_path = tmp_path / "llm_models.json"
    store = LLMModelStore(data_file=str(data_path))

    return store


@pytest.fixture
def client(temp_store):
    app = FastAPI()
    app.dependency_overrides[get_llm_store] = lambda: temp_store
    app.include_router(llm_config.router)
    return TestClient(app)


def test_create_model_with_token(client):
    payload = {
        "name": "model-with-token",
        "base_url": "https://example.com/root/",
        "model": "gpt-test",
        "api_key": "secret-token",
    }
    resp = client.post("/api/settings/llm-models", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_token"] is True
    assert data["token_hint"].startswith("sec")
    assert "api_key" not in data
    assert data["base_url"] == "https://example.com/root"
    assert data["endpoint_path"] == "/v1/chat/completions"


def test_create_model_without_token(client):
    payload = {
        "name": "model-no-token",
        "base_url": "https://example.org/api",
        "model": "gpt-no-token",
    }
    resp = client.post("/api/settings/llm-models", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_token"] is False
    assert data["token_hint"] == ""


def test_update_model_without_new_token_keeps_existing(client):
    # create initial model with token
    create_resp = client.post(
        "/api/settings/llm-models",
        json={
            "name": "model-update",
            "base_url": "https://example.net/",
            "model": "gpt-update",
            "api_key": "initial-token",
        },
    )
    model_id = create_resp.json()["id"]
    assert create_resp.json()["has_token"] is True

    # update without api_key - should keep token
    update_resp = client.put(
        f"/api/settings/llm-models/{model_id}",
        json={"name": "model-update-renamed"},
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["has_token"] is True
    assert data["name"] == "model-update-renamed"

