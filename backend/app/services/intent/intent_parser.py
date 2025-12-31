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

SYSTEM_PROMPT = """You are an intent classifier for a knowledge retrieval system. Analyze the user's query and output a structured JSON response.

# Your Task
Classify user intent and generate an optimized retrieval plan in JSON format.

# Output Schema
```json
{
  "task_type": "kb_qa|web_search|mixed|chit_chat",
  "need_web": boolean,
  "freshness_days": 0|7|30|365,
  "anchors": [{"text": "string", "strength": "strong|medium|weak"}],
  "queries": ["query1", "query2", "query3"],
  "answer_style": {
    "language": "zh-CN|en|auto",
    "format": "paragraph|bullets",
    "focus": ["key1", "key2"]
  }
}
```

# Classification Rules

## task_type Decision Tree
1. **Simple greeting/thanks** (你好/谢谢/再见) → `chit_chat`
2. **Time-sensitive query** (今天/最新/现在 + 新闻/天气/事件) → `web_search`
3. **General knowledge without time constraint** (什么是/介绍/解释) → check context:
   - If user uploaded docs → `kb_qa`
   - If general encyclopedia → `web_search`
4. **Document-specific query** (文档中/材料里/根据) → `kb_qa`
5. **Comparison with external info** (对比/市场/行业标准) → `mixed`
6. **Default for any question** → `kb_qa` (safer to retrieve than to skip)

## need_web Logic
- `true` IF: task_type is `web_search` or `mixed` OR contains time-sensitive keywords (今天/最新/实时)
- `false` OTHERWISE (default for kb_qa and chit_chat)

## freshness_days
- 0: Default (no time constraint)
- 7: "最近/这几天"
- 30: "本月/这个月"
- 365: "今年/年度"

## anchors Extraction
Extract 0-5 key entities:
- **strong**: Numbers, amounts, IDs, specific names (投标保证金/第3章/1000万元)
- **medium**: Domain terms, concepts (质保期/验收标准)
- **weak**: General verbs/adjectives (分析/描述)
**Return [] if no obvious entities**

## queries Generation
Generate 3-5 search variations:
1. Original query (keep user's wording)
2. Synonym variation (use similar terms)
3. Keyword extraction (core terms only)
4. Domain expansion (add related terminology)
5. Optional: English translation (if applicable)

**For chit_chat**: only 1 query (original)

## answer_style
- **language**: Match user's language (zh-CN for Chinese, en for English, auto if mixed)
- **format**: 
  - `bullets` if query asks for "列表/有哪些/包括"
  - `paragraph` otherwise (default for detailed answers)
- **focus**: Extract 1-3 key topics from the query

# Examples (Few-Shot Learning)

## Example 1: Document Query
Input: "招标文件中的投标保证金是多少？"
Output:
```json
{
  "task_type": "kb_qa",
  "need_web": false,
  "freshness_days": 0,
  "anchors": [
    {"text": "招标文件", "strength": "strong"},
    {"text": "投标保证金", "strength": "strong"}
  ],
  "queries": [
    "招标文件中的投标保证金是多少",
    "投标保证金金额",
    "保证金 投标 金额",
    "bid bond amount"
  ],
  "answer_style": {
    "language": "zh-CN",
    "format": "paragraph",
    "focus": ["投标保证金", "金额"]
  }
}
```

## Example 2: Time-Sensitive Query
Input: "今天北京天气怎么样？"
Output:
```json
{
  "task_type": "web_search",
  "need_web": true,
  "freshness_days": 0,
  "anchors": [
    {"text": "北京", "strength": "strong"},
    {"text": "天气", "strength": "medium"}
  ],
  "queries": [
    "今天北京天气",
    "北京天气预报",
    "Beijing weather today"
  ],
  "answer_style": {
    "language": "zh-CN",
    "format": "paragraph",
    "focus": ["天气", "温度"]
  }
}
```

## Example 3: Simple Greeting
Input: "你好"
Output:
```json
{
  "task_type": "chit_chat",
  "need_web": false,
  "freshness_days": 0,
  "anchors": [],
  "queries": ["你好"],
  "answer_style": {
    "language": "zh-CN",
    "format": "paragraph",
    "focus": []
  }
}
```

## Example 4: Mixed Query
Input: "我们的产品与市场上的竞品相比如何？"
Output:
```json
{
  "task_type": "mixed",
  "need_web": true,
  "freshness_days": 0,
  "anchors": [
    {"text": "产品", "strength": "medium"},
    {"text": "竞品", "strength": "medium"}
  ],
  "queries": [
    "我们的产品与竞品对比",
    "产品竞争力分析",
    "产品 对比 竞品",
    "product comparison competitors"
  ],
  "answer_style": {
    "language": "zh-CN",
    "format": "bullets",
    "focus": ["产品对比", "竞争优势"]
  }
}
```

## Example 5: General Knowledge
Input: "介绍一下项目背景"
Output:
```json
{
  "task_type": "kb_qa",
  "need_web": false,
  "freshness_days": 0,
  "anchors": [
    {"text": "项目背景", "strength": "medium"}
  ],
  "queries": [
    "介绍项目背景",
    "项目背景说明",
    "项目 背景 介绍",
    "project background"
  ],
  "answer_style": {
    "language": "zh-CN",
    "format": "paragraph",
    "focus": ["项目背景", "项目概况"]
  }
}
```

# Critical Rules
1. **Default to kb_qa** when uncertain (better to retrieve than miss)
2. **Only use chit_chat** for obvious greetings/thanks with NO question intent
3. **Only use web_search** for clear time-sensitive or general knowledge needs
4. **Output ONLY valid JSON** (no markdown fences, no explanation, no extra text)
5. **Be concise**: Prefer shorter queries and fewer anchors over exhaustive lists

Now analyze the user's query and output the JSON plan."""


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
    # Build concise context (OpenAI best practice: keep prompts focused)
    recent = history[-4:] if history else []
    context_lines = []
    
    if recent:
        context_lines.append("# Recent Conversation Context")
        for msg in recent[-2:]:  # Only last 2 turns for brevity
            role_label = "User" if msg.role == "user" else "Assistant"
            preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            context_lines.append(f"{role_label}: {preview}")
        context_lines.append("")
    
    # Build focused prompt (Google best practice: clear instructions)
    context_lines.extend([
        "# Current Query",
        f"User: {user_input}",
        "",
        "# Your Task",
        "Analyze the query above and output the classification JSON following the schema and examples provided in the system prompt.",
        "Output ONLY the JSON object, nothing else."
    ])
    
    return "\n".join(context_lines)


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

