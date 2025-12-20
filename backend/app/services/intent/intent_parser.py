from __future__ import annotations

import json
import logging
from typing import Awaitable, Callable, List

from pydantic import ValidationError

from app.schemas.chat import Message
from app.schemas.intent import Anchor, IntentPlan
from app.services.logging.request_logger import (
    get_request_logger,
    safe_preview,
)

logger = logging.getLogger(__name__)

VALID_TASK_TYPES = {"web_search", "kb_qa", "mixed", "chit_chat"}
TASK_TYPE_ALIASES = {
    "information_retrieval": "web_search",
    "search": "web_search",
    "web": "web_search",
    "browse": "web_search",
    "rag": "mixed",
}

SYSTEM_PROMPT = """你是一个检索规划器。将用户问题改写为结构化 JSON，对应 IntentPlan（task_type / need_web / freshness_days / anchors / queries / answer_style）。
- anchors 代表可能需要精确对齐的片段，用于加权检索，但不是硬过滤；允许为空。
- anchors.strength: strong 表示必须重点匹配（例如明确编号、金额、引用原文），medium/weak 为次要信息。
- queries 需要 3~6 条，覆盖中文/英文/同义改写，至少 1 条包含 strong anchors（用引号包裹原文）。
- 如果是闲聊或无需检索，task_type=chit_chat，need_web=false，queries 只包含用户原话。
- freshness_days 取值 0/7/30/365。
- answer_style 包含 language（zh-CN/en/auto）、format（paragraph/bullets）、focus（数组）字段。
- 只输出 JSON，不要额外文本或 Markdown。"""


def _detect_need_web_from_raw(raw: str) -> bool:
    """
    当 LLM 返回的 JSON 语法有问题时，尽量从原始文本中恢复 need_web=true 的信号。
    极简实现：用字符串匹配 '"need_web": true'，忽略大小写和空格。
    """
    if not raw:
        return False
    lowered = raw.lower()
    return '"need_web"' in lowered and ": true" in lowered


def sanitize_extract_json(raw: str) -> str:
    if not raw:
        raise ValueError("Intent parser returned empty response")
    text = raw.strip()
    if not text:
        raise ValueError("Intent parser returned blank response")

    if "```" in text:
        text = text.replace("```json", "```")
        segments = [seg.strip() for seg in text.split("```") if seg.strip()]
        for seg in segments:
            if seg.startswith("{"):
                text = seg
                break

    start = text.find("{")
    if start == -1:
        raise ValueError("Intent parser response missing '{'")

    depth = 0
    end = -1
    for idx in range(start, len(text)):
        char = text[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = idx
                break
    if end == -1:
        raise ValueError("Intent parser response has unbalanced braces")

    return text[start : end + 1]


def _build_intent_prompt(user_input: str, history: List[Message], mode: str) -> str:
    recent = history[-6:]
    formatted_history = []
    for item in recent[-3:]:
        formatted_history.append(f"{item.role}: {item.content}")
    history_block = "\n".join(formatted_history) if formatted_history else "(none)"
    return (
        f"对话模式: {mode}\n"
        f"最近对话（最多3轮）:\n{history_block}\n\n"
        f"用户问题:\n{user_input}\n\n"
        "请输出 IntentPlan JSON。"
    )


def _fallback_plan(message: str) -> IntentPlan:
    return IntentPlan(
        task_type="kb_qa",
        need_web=False,
        freshness_days=0,
        anchors=[],
        queries=[message],
    )


async def parse_intent(
    call_llm: Callable[[str, str], Awaitable[str]],
    message: str,
    history: List[Message],
    mode: str = "auto",
    request_id: str | None = None,
) -> tuple[IntentPlan, bool]:
    req_logger = get_request_logger(logger, request_id)
    user_prompt = _build_intent_prompt(message, history, mode)
    raw_response = ""
    try:
        raw_response = await call_llm(SYSTEM_PROMPT, user_prompt)
        cleaned = sanitize_extract_json(raw_response)
        data = json.loads(cleaned)
        queries = data.get("queries", [])
        normalized_queries: List[str] = []
        if isinstance(queries, list):
            for item in queries:
                if isinstance(item, dict):
                    text = item.get("text")
                    if text:
                        normalized_queries.append(text)
                elif isinstance(item, str):
                    text = item.strip()
                    if text:
                        normalized_queries.append(text)
        if not normalized_queries:
            normalized_queries = [message]
        data["queries"] = normalized_queries
        anchors = data.get("anchors")
        if anchors is None:
            data["anchors"] = []
        task_type_value = data.get("task_type")
        if isinstance(task_type_value, str):
            key = task_type_value.strip().lower()
            if key in TASK_TYPE_ALIASES:
                data["task_type"] = TASK_TYPE_ALIASES[key]
            elif key in VALID_TASK_TYPES:
                data["task_type"] = key
            else:
                data.pop("task_type", None)
        plan = IntentPlan.model_validate(data)
        if not plan.queries:
            plan.queries = [message]
        return plan, False
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        snippet = (raw_response or "")[:200]
        req_logger.warning("Intent parser parse failed: %s raw=%s", exc, safe_preview(snippet, 200))
        plan = _fallback_plan(message)
        # 如果原始响应里明确包含 need_web=true，则在 fallback 计划上保留这一信号
        if _detect_need_web_from_raw(raw_response):
            plan.need_web = True
            req_logger.info("Intent parser fallback will still use need_web=true based on raw response")
        return plan, True
    except Exception as exc:  # noqa: BLE001
        snippet = (raw_response or "")[:200]
        req_logger.warning("Intent parser failed: %s raw=%s", exc, safe_preview(snippet, 200))
        plan = _fallback_plan(message)
        if _detect_need_web_from_raw(raw_response):
            plan.need_web = True
            req_logger.info("Intent parser hard-fail but raw response indicates need_web=true, enabling web")
        return plan, True

