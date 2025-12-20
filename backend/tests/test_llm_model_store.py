import pytest

from app.schemas.llm_config import LLMModelIn, LLMModelUpdate
from app.services.llm_model_store import LLMModelStore


def make_store(tmp_path):
    return LLMModelStore(data_file=str(tmp_path / "llm_models.json"))


def sample_payload(**overrides):
    base = {
        "name": "model-a",
        "base_url": "https://api.example.com/",
        "endpoint_path": "/v1/chat/completions/",
        "model": "gpt-a",
        "api_key": "abc123xyz",
    }
    base.update(overrides)
    return LLMModelIn(**base)


def test_create_and_reload(tmp_path):
    store = make_store(tmp_path)
    stored = store.create_model(sample_payload())
    assert stored.is_default
    assert store.to_dict(stored)["has_token"] is True

    # reload from disk to ensure persistence
    store2 = make_store(tmp_path)
    reloaded = store2.list_models()
    assert len(reloaded) == 1
    assert reloaded[0].name == "model-a"
    assert reloaded[0].base_url == "https://api.example.com"


def test_update_does_not_override_token_when_missing(tmp_path):
    store = make_store(tmp_path)
    stored = store.create_model(sample_payload())

    store.update_model(
        stored.id,
        LLMModelUpdate(name="model-b", api_key=None),
    )
    updated = store.get_model(stored.id)
    assert updated is not None
    assert updated.name == "model-b"
    assert updated.api_key == "abc123xyz"


def test_set_default_and_delete(tmp_path):
    store = make_store(tmp_path)
    first = store.create_model(sample_payload(name="model-a"))
    second = store.create_model(
        sample_payload(name="model-b", base_url="https://foo.bar")
    )

    store.set_default_model(second.id)
    assert store.get_default_model().id == second.id

    # delete non-default OK
    store.delete_model(first.id)

    with pytest.raises(ValueError):
        store.delete_model(second.id)

