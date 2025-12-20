from __future__ import annotations

from typing import List, Optional

from ..schemas.chat import Message
from ..services.llm_client import generate_answer_with_llm, select_llm_profile

SUMMARY_SYSTEM_PROMPT = "你是一个对话摘要助手，需要将长对话压缩成简洁要点。"


async def summarize_history(messages: List[Message], llm_key: Optional[str] = None) -> str:
    """
    Summarize historical messages into ~200 Chinese characters.
    """
    if not messages:
        return ""

    history_text = "\n".join(f"{msg.role}: {msg.content}" for msg in messages if msg.content)
    if not history_text:
        return ""

    user_prompt = (
        "下面是用户与助手的历史对话，请用不超过 200 字的中文总结：\n"
        "1）本次会话主要讨论的主题；\n"
        "2）已确认的结论或假设；\n"
        "3）尚未解决或待补充的信息。\n\n"
        f"对话内容：\n{history_text}\n\n"
        "请输出纯文本摘要："
    )

    profile = select_llm_profile(llm_key)
    summary = await generate_answer_with_llm(
        system_prompt=SUMMARY_SYSTEM_PROMPT,
        user_message=user_prompt,
        history=[],
        profile=profile,
        overrides={"temperature": 0.2, "max_tokens": 256},
    )
    return summary.strip()

