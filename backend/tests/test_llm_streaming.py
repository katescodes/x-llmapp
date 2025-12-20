import pytest

from app.schemas.intent import AnswerStyle
from app.services.llm_orchestrator import summarize_with_llm_stream


@pytest.mark.asyncio
async def test_summarize_with_llm_stream_emits_chunks():
    chunks: list[str] = []

    async def fake_call(system_prompt, user_prompt, history, on_chunk):
        await on_chunk("hello ")
        await on_chunk("world")
        return "hello world"

    async def on_chunk(text: str):
        chunks.append(text)

    style = AnswerStyle(language="auto", format="paragraph", focus=[])
    answer = await summarize_with_llm_stream(
        fake_call,
        "question",
        style,
        [],
        [],
        on_chunk=on_chunk,
    )
    assert answer == "hello world"
    assert "".join(chunks) == "hello world"

