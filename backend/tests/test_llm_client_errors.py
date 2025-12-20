from __future__ import annotations

import pytest
import httpx
from fastapi import HTTPException

from app.schemas.chat import Message
from app.schemas.llm_config import LLMModelStored
from app.services.llm_client import (
    LLMProfile,
    generate_answer_with_llm,
    generate_answer_with_model,
)


class _RaisingClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        raise httpx.ReadTimeout("boom")


@pytest.mark.asyncio
async def test_generate_answer_with_model_timeout(monkeypatch):
    monkeypatch.setattr("app.services.llm_client.httpx.AsyncClient", _RaisingClient)
    model = LLMModelStored(
        name="test",
        base_url="http://llm.local",
        endpoint_path="/v1/chat/completions",
        model="dummy",
    )
    with pytest.raises(HTTPException) as excinfo:
        await generate_answer_with_model(
            system_prompt="test",
            user_message="hello",
            history=[Message(role="user", content="hi")],
            model=model,
            api_key=None,
        )
    assert excinfo.value.status_code == 502
    assert "超时" in str(excinfo.value.detail)


@pytest.mark.asyncio
async def test_generate_answer_with_llm_timeout(monkeypatch):
    monkeypatch.setattr("app.services.llm_client.httpx.AsyncClient", _RaisingClient)
    profile = LLMProfile(
        key="p1",
        display_name="Profile1",
        base_url="http://llm.local",
        model="dummy",
        endpoint_path="/v1/chat/completions",
        api_key=None,
        mock=False,
    )
    with pytest.raises(HTTPException) as excinfo:
        await generate_answer_with_llm(
            system_prompt="sys",
            user_message="hello",
            history=[],
            profile=profile,
        )
    assert excinfo.value.status_code == 502
    assert "超时" in str(excinfo.value.detail)

