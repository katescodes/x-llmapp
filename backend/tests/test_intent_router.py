import pytest

from app.schemas.chat import Message
from app.services.intent.intent_parser import (
    parse_intent,
    sanitize_extract_json,
)


def test_sanitize_plain_json():
    raw = '{"a":1,"b":2}'
    assert sanitize_extract_json(raw) == raw


def test_sanitize_code_fence():
    raw = "```json\n{\n  \"foo\": \"bar\"\n}\n```"
    assert sanitize_extract_json(raw) == '{\n  "foo": "bar"\n}'


def test_sanitize_with_text():
    raw = "LLM output:\nHere you go:\n{\n \"x\":42\n }\nThanks!"
    assert sanitize_extract_json(raw) == '{\n "x":42\n }'


@pytest.mark.asyncio
async def test_intent_parser_fallback_on_bad_json():
    async def fake_call(system_prompt: str, user_prompt: str) -> str:
        return "not json"

    plan, fallback = await parse_intent(fake_call, "测试 fallback", [], "force_kb")
    assert plan.queries == ["测试 fallback"]
    assert plan.task_type == "kb_qa"
    assert fallback is True


@pytest.mark.asyncio
async def test_intent_parser_valid_response_with_objects():
    async def fake_call(system_prompt: str, user_prompt: str) -> str:
        return """
        {
          "task_type": "mixed",
          "need_web": true,
          "freshness_days": 7,
          "anchors": [{"text": "A-1234", "type": "id", "strength": "strong"}],
          "queries": [{"text": "test query 1"}, {"text": "test query 2"}],
          "answer_style": {"language": "zh-CN", "format": "paragraph", "focus": ["facts"]}
        }
        """

    history = [Message(role="user", content="你好?")]
    plan, fallback = await parse_intent(fake_call, "测试", history, "auto")
    assert plan.queries == ["test query 1", "test query 2"]
    assert plan.anchors[0].text == "A-1234"
    assert plan.answer_style.format == "paragraph"
    assert fallback is False


@pytest.mark.asyncio
async def test_intent_parser_recovers_from_code_fence():
    async def fake_call(system_prompt: str, user_prompt: str) -> str:
        return """```json
        {
          "task_type": "kb_qa",
          "need_web": false,
          "freshness_days": 0,
          "anchors": [],
          "queries": ["留在本地"],
          "answer_style": {"language": "zh-CN", "format": "bullets", "focus": ["summary"]}
        }
        ```"""

    plan, fallback = await parse_intent(fake_call, "本地信息", [], "force_web")
    assert plan.queries == ["留在本地"]
    assert plan.answer_style.format == "bullets"
    assert fallback is False


@pytest.mark.asyncio
async def test_intent_parser_maps_task_type_aliases():
    async def fake_call(system_prompt: str, user_prompt: str) -> str:
        return """
        {
          "task_type": "information_retrieval",
          "need_web": true,
          "queries": [{"text": "你好"}],
          "anchors": []
        }
        """

    plan, fallback = await parse_intent(fake_call, "你好", [], "auto")
    assert plan.task_type == "web_search"
    assert plan.queries == ["你好"]
    assert fallback is False