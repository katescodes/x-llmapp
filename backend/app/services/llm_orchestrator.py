import logging
from typing import Dict, List, Optional

from fastapi import HTTPException

from ..schemas.chat import Message, Source
from ..services.logging.request_logger import (
    get_request_logger,
    mask_host,
    safe_preview,
)
from .prompt_templates import BASE_SYSTEM_PROMPT, DECISION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def build_context(
    sources: List[Source],
    max_chars: int = 6000,
    extra_context: Optional[str] = None,
    attachment_context: Optional[str] = None,
) -> str:
    parts: List[str] = []
    total = 0
    
    # 1. 优先添加附件上下文
    if attachment_context:
        parts.append("[用户上传的附件内容]")
        parts.append(attachment_context)
        total += len(attachment_context) + 50
    
    # 2. 添加检索到的源
    for src in sources:
        snippet = (src.snippet or "").replace("\n", " ")[:400]
        entry = (
            f"[{src.id}] 知识库: {src.kb_name or 'Web'} / 文档: {src.doc_name or src.title or '未命名'}\n"
            f"链接: {src.url or '(无链接)'}\n"
            f"内容: {snippet}"
        )
        parts.append(entry)
        total += len(entry)
        if total >= max_chars:
            break
    
    context_text = "\n\n".join(parts)
    
    # 3. 添加额外上下文
    if extra_context:
        extra_block = extra_context.strip()
        if extra_block:
            if context_text:
                context_text = f"{context_text}\n\n[补充资料]\n{extra_block}"
            else:
                context_text = extra_block
    return context_text


def _system_prompt_for_mode(mode: str) -> str:
    if mode == "decision":
        base = DECISION_SYSTEM_PROMPT.strip()
    else:
        base = BASE_SYSTEM_PROMPT.strip()
    return (
        f"{base}\n\n"
        "你会收到 search_context（可能为空），需要在回答中引用其中的资料。"
        "引用资料时在句末使用 [编号]，编号来自 search_context 中的标记。"
        "若 search_context 为空，请明确说明并基于已有常识回答。"
    )


async def summarize_with_llm(
    call_llm,
    user_question: str,
    answer_style,
    sources: List[Source],
    history: List[Message],
    *,
    request_id: Optional[str] = None,
    model_base_url: Optional[str] = None,
    mode: str = "normal",
    extra_context: Optional[str] = None,
    attachment_context: Optional[str] = None,
) -> str:
    req_logger = get_request_logger(logger, request_id)
    context_block = build_context(sources, extra_context=extra_context, attachment_context=attachment_context)
    focus_text = ", ".join(answer_style.focus) if answer_style.focus else "facts"
    summarizer_system = _system_prompt_for_mode(mode)
    context_text = context_block or "(无搜索结果，基于已有知识回答)"
    available_refs = ", ".join(f"[{src.id}]" for src in sources) or "无引用"
    
    # 如果有附件，在提示中说明
    attachment_hint = ""
    if attachment_context:
        attachment_hint = "\n注意：用户上传了附件，附件内容已包含在 search_context 中，请优先基于附件内容回答。"
    
    summarizer_user = (
        f"用户问题:\n{user_question}\n\n"
        f"search_context:\n{context_text}\n\n"
        f"可以使用的引用编号：{available_refs}\n"
        f"回答要求:\n- 语言: {answer_style.language}\n- 输出形式: {answer_style.format}\n"
        f"- 重点: {focus_text}\n"
        f"请基于 search_context 给出有条理的回答。{attachment_hint}"
    )
    prompt_chars = len(summarizer_system) + len(summarizer_user)
    req_logger.info(
        "LLM summarize start model=%s chunks=%s prompt_chars=%s has_attachment=%s",
        mask_host(model_base_url),
        len(sources),
        prompt_chars,
        bool(attachment_context),
    )
    try:
        answer = await call_llm(summarizer_system, summarizer_user, history)
    except HTTPException as exc:
        req_logger.error(
            "LLM summarize HTTP error status=%s detail=%s",
            exc.status_code,
            safe_preview(exc.detail, 500),
        )
        raise
    except Exception as exc:  # noqa: BLE001
        req_logger.error("LLM summarize failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=f"LLM 调用失败: {exc}") from exc
    req_logger.info(
        "LLM summarize done model=%s answer_chars=%s",
        mask_host(model_base_url),
        len(answer or ""),
    )
    return answer


async def summarize_with_llm_stream(
    call_llm_stream,
    user_question: str,
    answer_style,
    sources: List[Source],
    history: List[Message],
    *,
    on_chunk,
    request_id: Optional[str] = None,
    model_base_url: Optional[str] = None,
    mode: str = "normal",
    extra_context: Optional[str] = None,
    attachment_context: Optional[str] = None,
) -> str:
    req_logger = get_request_logger(logger, request_id)
    context_block = build_context(sources, extra_context=extra_context, attachment_context=attachment_context)
    focus_text = ", ".join(answer_style.focus) if answer_style.focus else "facts"
    summarizer_system = _system_prompt_for_mode(mode)
    context_text = context_block or "(无搜索结果，基于已有知识回答)"
    available_refs = ", ".join(f"[{src.id}]" for src in sources) or "无引用"
    
    # 如果有附件，在提示中说明
    attachment_hint = ""
    if attachment_context:
        attachment_hint = "\n注意：用户上传了附件，附件内容已包含在 search_context 中，请优先基于附件内容回答。"
    
    summarizer_user = (
        f"用户问题:\n{user_question}\n\n"
        f"search_context:\n{context_text}\n\n"
        f"可以使用的引用编号：{available_refs}\n"
        f"回答要求:\n- 语言: {answer_style.language}\n- 输出形式: {answer_style.format}\n"
        f"- 重点: {focus_text}\n"
        f"请基于 search_context 给出有条理的回答。{attachment_hint}"
    )
    prompt_chars = len(summarizer_system) + len(summarizer_user)
    req_logger.info(
        "LLM summarize(stream) start model=%s chunks=%s prompt_chars=%s has_attachment=%s",
        mask_host(model_base_url),
        len(sources),
        prompt_chars,
        bool(attachment_context),
    )
    try:
        answer = await call_llm_stream(
            summarizer_system,
            summarizer_user,
            history,
            on_chunk,
        )
    except HTTPException as exc:
        req_logger.error(
            "LLM summarize(stream) HTTP error status=%s detail=%s",
            exc.status_code,
            safe_preview(exc.detail, 500),
        )
        raise
    except Exception as exc:  # noqa: BLE001
        req_logger.error("LLM summarize(stream) failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=f"LLM 调用失败: {exc}") from exc
    req_logger.info(
        "LLM summarize(stream) done model=%s answer_chars=%s",
        mask_host(model_base_url),
        len(answer or ""),
    )
    return answer

