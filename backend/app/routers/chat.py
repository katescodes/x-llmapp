import asyncio
import contextlib
import hashlib
import json
import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, TYPE_CHECKING
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from urllib.parse import urlparse

if TYPE_CHECKING:
    from psycopg_pool import ConnectionPool

from app.config import get_settings
from ..schemas.chat import ChatRequest, ChatResponse, ChatSection, Message, Source, UsedModel
from ..schemas.intent import AnswerStyle, IntentPlan
from ..services.orchestrator import OrchestratorService
from ..services.cache import doc_cache
from ..services.dao import kb_dao
from ..services.crawler.extractor import extract_content
from ..services.crawler.fetcher import PageFetcher
from ..services.embedding.http_embedding_client import embed_texts
from ..services.embedding_provider_store import get_embedding_store
from ..services.history_store import (
    append_message as append_history_message,
    create_session as create_history_session,
    get_session as get_history_session,
    update_session_kb_ids as update_history_session_kb_ids,
    update_session_meta as update_history_session_meta,
    update_session_summary as update_history_session_summary,
)
from ..services.history_decision import generate_history_decision_answer
from ..services.intent.intent_parser import parse_intent
from ..services.llm_client import (
    generate_answer_with_llm,
    generate_answer_with_model,
    select_llm_profile,
    stream_answer_with_model,
)
from ..services.llm_model_store import get_llm_store
from ..services.llm_orchestrator import summarize_with_llm, summarize_with_llm_stream
from ..services.llm_helpers import summarize_history
from ..services.prompt_templates import BASE_SYSTEM_PROMPT, DECISION_SYSTEM_PROMPT
from ..services.logging.request_logger import (
    get_request_logger,
    is_debug_enabled,
    mask_host,
    safe_preview,
)
from ..services.google_search import filter_chinese_entries, google_search_multi
from ..services.rag_service import retrieve_context
from ..services.search_usage import usage_manager
from ..services.segmenter.chunker import chunk_document
from ..services.settings_store import load_settings
from ..services.vectorstore.milvus_lite_store import WEB_KB_ID, milvus_store
from ..services.attachment_store import get_attachment_store
from ..services.attachment_context import (
    chunk_attachment_text,
    select_relevant_chunks,
    build_attachment_context,
)
from ..utils.text_utils import is_chinese_heavy, normalize_bullets_to_ordered

router = APIRouter(prefix="/api", tags=["chat"])
settings = get_settings()
logger = logging.getLogger(__name__)

INTENT_LLM_OVERRIDES = {"temperature": 0.0, "max_tokens": 512, "top_p": 0.8}
STREAM_HEARTBEAT_INTERVAL = 15

# 上下文管理配置
HISTORY_MESSAGE_LIMIT = 10  # 传给 LLM 的最近消息数量（增加到10轮，提供更丰富的上下文）
SUMMARY_TRIGGER_THRESHOLD = 20  # 当消息数超过此值时触发摘要生成（从12增加到20，减少频繁摘要）
MAX_CONTEXT_TOKENS = 128000  # 最大上下文token数（估算值，用于防止超出模型限制）

# 网页抓取配置
WEB_FETCH_MIN = 15
WEB_FETCH_MAX = 30
WEB_MAX_PER_DOMAIN = 3


def _get_pool() -> "ConnectionPool":
    """从 postgres 模块获取连接池"""
    from app.services.db.postgres import _get_pool as get_sync_pool
    return get_sync_pool()


def _prepare_sources(retrieved_chunks: list[dict], min_sources: int = 0) -> list[Source]:
    if not retrieved_chunks:
        return []

    kb_ids = {chunk.get("kb_id") for chunk in retrieved_chunks if chunk.get("kb_id")}
    doc_ids = {chunk.get("doc_id") for chunk in retrieved_chunks if chunk.get("doc_id")}
    kb_names = kb_dao.get_kb_names([kb_id for kb_id in kb_ids if kb_id != WEB_KB_ID])
    doc_meta = kb_dao.get_documents_meta(list(doc_ids))

    seen_keys: set[str] = set()
    unique_sources: list[Source] = []
    duplicate_sources: list[Source] = []

    def _chunk_to_source(chunk: dict, score: float, source_id: int) -> Source:
        kb_id = chunk.get("kb_id")
        doc_id = chunk.get("doc_id")
        url = chunk.get("url") or f"kb://{kb_id or ''}/{doc_id or ''}"
        if kb_id == WEB_KB_ID:
            kb_name = "Web抓取"
            doc_name = chunk.get("title") or url
        else:
            kb_name = kb_names.get(kb_id, "知识库")
            doc_name = doc_meta.get(doc_id, {}).get("filename") or chunk.get("title") or url
        return Source(
            id=source_id,
            kb_id=kb_id,
            kb_name=kb_name,
            doc_id=doc_id,
            doc_name=doc_name,
            title=chunk.get("title") or doc_name,
            url=chunk.get("url"),
            score=score,
            snippet=(chunk.get("text") or "")[:400],
        )

    for chunk in retrieved_chunks:
        score = float(chunk.get("score", 0.0))
        source = _chunk_to_source(chunk, score, len(unique_sources) + 1)
        key = source.url or f"{source.kb_id}:{source.doc_id}"
        if key and key in seen_keys:
            duplicate_sources.append((chunk, score))
            continue
        if key:
            seen_keys.add(key)
        unique_sources.append(source)

    if min_sources and len(unique_sources) < min_sources and duplicate_sources:
        needed = min_sources - len(unique_sources)
        for chunk, score in duplicate_sources[:needed]:
            unique_sources.append(
                _chunk_to_source(chunk, score, len(unique_sources) + 1)
            )

    return unique_sources


def _resolve_dense_dim(vectors: list[dict], fallback: int | None) -> int:
    for vec in vectors:
        dense = vec.get("dense")
        if isinstance(dense, list) and dense:
            return len(dense)
    if fallback:
        return fallback
    raise HTTPException(status_code=503, detail="Embedding dense 维度未知，请先在设置中配置 dense_dim")


def _records_to_messages(records: list[dict], limit: int) -> list[Message]:
    if not records:
        return []
    trimmed = records[-limit:] if limit else list(records)
    prepared: list[Message] = []
    for item in trimmed:
        role = item.get("role")
        content = item.get("content")
        if not role or content is None:
            continue
        if role not in ("user", "assistant", "system"):
            continue
        prepared.append(Message(role=role, content=str(content)))
    return prepared


def _estimate_tokens(text: str) -> int:
    """
    估算文本的 token 数量
    - 中文字符: 约 1.5 字/token
    - 英文和其他字符: 约 4 字符/token（简化处理）
    """
    if not text:
        return 0
    
    try:
        # 统计中文字符
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        # 其他字符（包括英文、数字、标点等）
        other_chars = len(text) - chinese_chars
        
        # 估算公式（保守估计）
        tokens = int(chinese_chars / 1.5 + other_chars / 4)
        return max(tokens, 1)
    except Exception:
        # 如果出错，返回保守估计
        return len(text) // 2


def _truncate_context_by_tokens(
    messages: list[Message],
    max_tokens: int
) -> list[Message]:
    """
    根据 token 限制裁剪上下文，从最新消息开始保留
    保证不超过 max_tokens 限制
    """
    if not messages:
        return []
    
    try:
        result: list[Message] = []
        total_tokens = 0
        
        # 从最新消息开始，逆序遍历
        for msg in reversed(messages):
            msg_tokens = _estimate_tokens(msg.content)
            
            # 如果加上当前消息会超限，停止添加
            if total_tokens + msg_tokens > max_tokens:
                logger.debug(
                    "Context truncated: would exceed %d tokens (current: %d, msg: %d)",
                    max_tokens,
                    total_tokens,
                    msg_tokens
                )
                break
            
            result.insert(0, msg)  # 插入到开头保持顺序
            total_tokens += msg_tokens
        
        # 如果一条消息都放不下，至少保留最后一条的部分内容
        if not result and messages:
            last_msg = messages[-1]
            # 截断到合适长度
            truncated_content = last_msg.content[:int(max_tokens * 2)]  # 粗略估算
            result = [Message(role=last_msg.role, content=truncated_content)]
            logger.warning("Single message too long, truncated to fit context")
        
        return result
    except Exception as exc:
        # 如果出错，返回原始消息列表（不裁剪）
        logger.error("Error in _truncate_context_by_tokens: %s", exc, exc_info=True)
        return messages


def _build_default_intent_plan(message: str) -> IntentPlan:
    return IntentPlan(
        task_type="kb_qa",
        need_web=False,
        freshness_days=0,
        anchors=[],
        queries=[message],
        answer_style=AnswerStyle(language="auto", format="paragraph", focus=[]),
    )


def _fallback_answer_from_sources(
    error_detail: str | None,
    sources: list[Source],
) -> str:
    reason = safe_preview(error_detail or "LLM 调用异常", 120)
    if sources:
        lines = [
            f"- [{src.id}] {(src.kb_name or '知识库')} / {(src.doc_name or src.title or '未命名')}"
            for src in sources[:6]
        ]
        joined = "\n".join(lines)
        return (
            f"抱歉，生成答案的 LLM 暂时不可用（{reason}）。\n"
            f"你可以先参考检索到的资料：\n{joined}"
        )
    return (
        f"抱歉，生成答案的 LLM 暂时不可用（{reason}），"
        "且本轮没有可用的参考资料。请稍后重试。"
    )


def _format_sse_event(event_type: str, payload: dict) -> bytes:
    data = json.dumps(payload, ensure_ascii=False)
    return f"event: {event_type}\ndata: {data}\n\n".encode("utf-8")


async def _chat_endpoint_impl(
    req: ChatRequest,
    request_id: str,
    stream_tokens: Optional[Callable[[str], Awaitable[None]]] = None,
) -> ChatResponse:
    req_logger = get_request_logger(logger, request_id)
    app_settings = load_settings()
    search_cfg = app_settings.search
    retrieval_cfg = app_settings.retrieval
    blocked_domains = {d.lower() for d in settings.CRAWLER_BLOCKED_DOMAINS}

    def _is_blocked(url: str) -> bool:
        if not url:
            return False
        host = urlparse(url).netloc.lower()
        return any(host == dom or host.endswith(f".{dom}") for dom in blocked_domains)

    raw_selected_ids = (
        req.selected_kb_ids
        if req.selected_kb_ids is not None
        else req.kb_ids
    )
    kb_override_provided = raw_selected_ids is not None
    explicit_kb_ids = [kb for kb in (raw_selected_ids or []) if kb]
    
    # 🔧 联网搜索决策逻辑重构：
    # 1. 如果用户明确勾选了联网搜索（req.enable_web === true），则启用
    # 2. 如果用户选择了知识库，默认禁用联网搜索（除非明确勾选）
    # 3. 如果没有选择知识库，根据配置决定是否联网搜索
    fallback_mode = req.search_mode or app_settings.search.mode
    
    if req.enable_web is True:
        # 用户明确勾选了联网搜索
        enable_web = True
        req_logger.info("[联网决策] 用户明确勾选联网搜索，启用")
    elif explicit_kb_ids:
        # 用户选择了知识库，默认禁用联网搜索
        enable_web = False
        req_logger.info(f"[联网决策] 用户选择了知识库 {len(explicit_kb_ids)} 个，默认禁用联网搜索")
    elif req.enable_web is False:
        # 用户明确取消联网搜索
        enable_web = False
        req_logger.info("[联网决策] 用户明确取消联网搜索，禁用")
    else:
        # 根据配置决定
        enable_web = fallback_mode == "force"
        req_logger.info(f"[联网决策] 根据配置决定: fallback_mode={fallback_mode}, enable_web={enable_web}")
    
    enable_web = bool(enable_web)
    search_mode = "force" if enable_web else "off"

    store = get_llm_store()
    model_result = None
    if req.llm_key:
        model_result = store.get_model_with_token(req.llm_key)
    else:
        default_model = store.get_default_model()
        if default_model:
            model_result = (default_model, default_model.api_key)

    history_session = None
    session_id = req.session_id
    if session_id:
        history_session = get_history_session(session_id)
        if not history_session:
            session_id = None

    if not session_id:
        title = req.message[:40] or "新会话"
        initial_kbs = explicit_kb_ids if kb_override_provided else []
        session_id = create_history_session(title, initial_kbs, search_mode, req.llm_key)
        history_session = get_history_session(session_id)

    if history_session is None:
        history_session = get_history_session(session_id)

    if kb_override_provided:
        effective_kb_ids = explicit_kb_ids
        update_history_session_kb_ids(session_id, effective_kb_ids)
    else:
        effective_kb_ids = (history_session or {}).get("default_kb_ids", []) or []

    # 知识问答增强：当选择了知识库时，自动在用户问题后追加提示语
    enhanced_message = req.message
    if effective_kb_ids:
        # 检查用户问题是否已经包含详尽度相关的关键词
        detail_keywords = ["详尽", "详细", "全面", "完整", "深入", "展开"]
        has_detail_request = any(keyword in req.message for keyword in detail_keywords)
        
        # 如果用户没有明确要求详尽回答，则自动追加提示语
        if not has_detail_request:
            enhanced_message = f"{req.message}\n\n请尽可能详尽、全面回答。"
            req_logger.info(f"[知识问答增强] 已为用户问题追加详尽度提示语")

    append_history_message(
        session_id,
        "user",
        req.message,  # 仍然保存原始用户消息到历史记录
        {
            "selected_kb_ids": effective_kb_ids,
            "enable_web": enable_web,
        },
    )

    history_session = get_history_session(session_id)
    if not history_session:
        raise HTTPException(status_code=500, detail="会话记录异常，无法载入历史。")

    session_messages = history_session.get("messages", []) or []
    session_summary = history_session.get("summary")

    # 智能生成摘要：当消息数量超过阈值且没有摘要时触发
    if (
        len(session_messages) > SUMMARY_TRIGGER_THRESHOLD
        and not session_summary
        and len(session_messages) > HISTORY_MESSAGE_LIMIT
    ):
        older_records = session_messages[:-HISTORY_MESSAGE_LIMIT]
        summary_input = _records_to_messages(older_records, 0)
        if summary_input:
            try:
                req_logger.info(
                    "Generating session summary: %d old messages (total: %d)",
                    len(older_records),
                    len(session_messages)
                )
                generated_summary = await summarize_history(summary_input, req.llm_key)
            except Exception as exc:  # noqa: BLE001
                req_logger.warning(
                    "Summarize history failed session=%s reason=%s",
                    session_id,
                    safe_preview(str(exc), 200),
                )
            else:
                cleaned_summary = generated_summary.strip()
                if cleaned_summary:
                    update_history_session_summary(session_id, cleaned_summary)
                    session_summary = cleaned_summary
                    req_logger.info(
                        "Session summary generated: %d chars",
                        len(cleaned_summary)
                    )

    # 构建上下文：优先使用摘要+最近消息的方式
    previous_records = session_messages[:-1] if session_messages else []
    
    # 策略1: 如果有摘要且历史较长，使用摘要+最近消息
    if session_summary and len(previous_records) > HISTORY_MESSAGE_LIMIT:
        recent_messages = _records_to_messages(
            previous_records[-HISTORY_MESSAGE_LIMIT:],
            HISTORY_MESSAGE_LIMIT
        )
        summary_message = Message(
            role="system",
            content=f"[本次对话的历史摘要]\n{session_summary}\n\n以下是最近的详细对话历史："
        )
        history_for_llm = [summary_message] + recent_messages
        req_logger.info(
            "Context built with summary: 1 summary + %d recent messages",
            len(recent_messages)
        )
    else:
        # 策略2: 直接使用最近的消息
        history_for_llm = _records_to_messages(previous_records, HISTORY_MESSAGE_LIMIT)
        req_logger.info(
            "Context built without summary: %d recent messages (total: %d)",
            len(history_for_llm),
            len(previous_records)
        )
    
    # Token 限制检查和裁剪
    try:
        total_tokens_before = sum(_estimate_tokens(m.content) for m in history_for_llm)
        if total_tokens_before > MAX_CONTEXT_TOKENS:
            req_logger.warning(
                "Context exceeds token limit: %d > %d, truncating",
                total_tokens_before,
                MAX_CONTEXT_TOKENS
            )
            history_for_llm = _truncate_context_by_tokens(history_for_llm, MAX_CONTEXT_TOKENS)
        
        total_tokens_after = sum(_estimate_tokens(m.content) for m in history_for_llm)
        req_logger.info(
            "Context prepared: session=%s total_msgs=%d context_msgs=%d "
            "has_summary=%s estimated_tokens=%d",
            session_id[:8] if session_id else "new",
            len(session_messages),
            len(history_for_llm),
            bool(session_summary),
            total_tokens_after
        )
    except Exception as exc:
        req_logger.error("Error in token calculation, skipping truncation: %s", exc)
        # 如果Token计算出错，使用原始的history_for_llm

    history_turns = len(history_for_llm)  # 修复：使用 history_for_llm 而不是 conversation_history
    response_llm_key = ""
    response_llm_name = ""

    call_chat_llm_stream: Optional[
        Callable[[str, str, List[Message], Callable[[str], Awaitable[None]]], Awaitable[str]]
    ] = None

    if model_result:
        stored_model, llm_api_key = model_result
        model_host = mask_host(stored_model.base_url)

        async def call_chat_llm(system_prompt: str, user_prompt: str, history):
            return await generate_answer_with_model(
                system_prompt=system_prompt,
                user_message=user_prompt,
                history=history,
                model=stored_model,
                api_key=llm_api_key,
            )

        async def call_chat_llm_stream_impl(
            system_prompt: str,
            user_prompt: str,
            history,
            on_chunk: Callable[[str], Awaitable[None]],
        ):
            return await stream_answer_with_model(
                system_prompt=system_prompt,
                user_message=user_prompt,
                history=history,
                model=stored_model,
                api_key=llm_api_key,
                on_token=on_chunk,
            )

        async def call_plan_llm(system_prompt: str, user_prompt: str):
            return await generate_answer_with_model(
                system_prompt=system_prompt,
                user_message=user_prompt,
                history=[],
                model=stored_model,
                api_key=llm_api_key,
                overrides=INTENT_LLM_OVERRIDES,
            )

        response_llm_key = stored_model.id
        response_llm_name = stored_model.name
        call_chat_llm_stream = call_chat_llm_stream_impl
    else:
        profile = select_llm_profile(req.llm_key)
        model_host = mask_host(profile.base_url)

        async def call_chat_llm(system_prompt: str, user_prompt: str, history):
            return await generate_answer_with_llm(
                system_prompt=system_prompt,
                user_message=user_prompt,
                history=history,
                profile=profile,
            )

        async def call_plan_llm(system_prompt: str, user_prompt: str):
            return await generate_answer_with_llm(
                system_prompt=system_prompt,
                user_message=user_prompt,
                history=[],
                profile=profile,
                overrides=INTENT_LLM_OVERRIDES,
            )

        async def call_chat_llm_stream_impl(
            system_prompt: str,
            user_prompt: str,
            history,
            on_chunk: Callable[[str], Awaitable[None]],
        ):
            answer = await generate_answer_with_llm(
                system_prompt=system_prompt,
                user_message=user_prompt,
                history=history,
                profile=profile,
            )
            if answer:
                await on_chunk(answer)
            return answer

        response_llm_key = profile.key
        response_llm_name = profile.display_name
        call_chat_llm_stream = call_chat_llm_stream_impl

    used_model = UsedModel(
        id=response_llm_key or None,
        name=response_llm_name or None,
    )

    req_logger.info(
        "Chat request mode=%s enable_web=%s req.selected_kb_ids=%s effective_kb_ids=%s user_len=%s history_turns=%s",
        req.mode,
        enable_web,
        req.selected_kb_ids,
        effective_kb_ids,
        len(req.message or ""),
        history_turns,
    )
    
    # 可观测性：编排器请求参数
    req_logger.info(
        "[orchestrator] req enable=%s mode=%s detail=%s",
        req.enable_orchestrator,
        req.mode,
        getattr(req, "detail_level", None)
    )

    intent_start = time.perf_counter()
    try:
        intent_plan, intent_fallback = await parse_intent(
            call_plan_llm,
            req.message,
            history_for_llm,
            req.mode,
            request_id=request_id,
        )
    except Exception as exc:  # noqa: BLE001
        intent_plan = _build_default_intent_plan(req.message)
        intent_fallback = True
        req_logger.warning(
            "Intent parser exception fallback used: %s",
            safe_preview(str(exc), 200),
        )
        if is_debug_enabled():
            req_logger.debug("Intent parser exception detail", exc_info=True)
    
    # 🔧 强制知识库问答：当用户选择了知识库时，强制使用 kb_qa 模式
    if effective_kb_ids:
        modified_fields = []
        
        # 1. 强制 task_type 为 kb_qa
        if intent_plan.task_type != "kb_qa":
            original_task_type = intent_plan.task_type
            intent_plan.task_type = "kb_qa"
            modified_fields.append(f"task_type: {original_task_type} -> kb_qa")
        
        # 2. 如果没有明确勾选联网搜索，强制 need_web 为 false
        if not enable_web and intent_plan.need_web:
            intent_plan.need_web = False
            modified_fields.append(f"need_web: true -> false")
        
        if modified_fields:
            req_logger.info(
                f"[知识库强制] 用户选择了 {len(effective_kb_ids)} 个知识库，修正意图: {', '.join(modified_fields)}"
            )
    
    intent_elapsed = (time.perf_counter() - intent_start) * 1000
    req_logger.info(
        "Intent plan resolved fallback=%s task_type=%s need_web=%s queries=%s anchors=%s elapsed=%.1fms",
        intent_fallback,
        intent_plan.task_type,
        intent_plan.need_web,
        intent_plan.queries[:3],
        [anchor.text for anchor in intent_plan.anchors[:3]],
        intent_elapsed,
    )

    # 不再根据意图自动启用联网搜索，完全尊重用户的明确选择
    # if not enable_web and intent_plan.need_web:
    #     enable_web = True
    #     search_mode = "force"
    #     req_logger.info("Enable web search because intent plan indicates need_web=true")

    search_queries: list[str] = []
    usage_warning: str | None = None
    usage_count: int | None = None
    fetched_urls: list[str] = []

    if enable_web:
        if search_cfg.provider != "cse":
            raise HTTPException(status_code=503, detail="当前仅支持 Google CSE 搜索提供者。")
        search_api_key = search_cfg.google_cse_api_key or settings.GOOGLE_CSE_API_KEY
        cx = search_cfg.google_cse_cx or settings.GOOGLE_CSE_CX
        if not search_api_key or not cx:
            req_logger.warning("Google CSE 未配置 api_key/cx，无法执行联网搜索")
            raise HTTPException(status_code=503, detail="Google CSE API 未配置，请先在设置中填写。")

        max_urls_cfg = search_cfg.max_urls or 0
        target_fetch = max(WEB_FETCH_MIN, max_urls_cfg)
        target_fetch = min(target_fetch, WEB_FETCH_MAX)
        queries = intent_plan.queries or [req.message]
        seen_links: set[str] = set()
        domain_counts: dict[str, int] = {}
        req_logger.info(
            "Web search start queries=%s freshness_days=%s max_urls=%s",
            [safe_preview(q, 80) for q in queries[:3]],
            intent_plan.freshness_days,
            target_fetch,
        )

        freshness_filter = intent_plan.freshness_days or None

        for query in queries[:3]:
            search_queries.append(query)
            usage_count, warn = usage_manager.register_search(
                warn=search_cfg.warn,
                limit=search_cfg.limit,
            )
            if warn:
                usage_warning = (
                    f"今日联网搜索已达到 {usage_count} 次，接近上限 {search_cfg.limit}。"
                )
            want = max(
                WEB_FETCH_MIN,
                settings.GOOGLE_CSE_MIN_RESULTS_PER_QUERY,
                search_cfg.results_per_query or 0,
            )
            want = min(want, WEB_FETCH_MAX)
            try:
                items = await google_search_multi(
                    query=query,
                    want=want,
                    api_key=search_api_key,
                    cx=cx,
                    timeout=settings.SEARCH_HTTP_TIMEOUT,
                    freshness_days=freshness_filter,
                )
            except Exception as exc:  # noqa: BLE001
                req_logger.warning(
                    "Google search failed query=%s reason=%s",
                    safe_preview(query, 80),
                    safe_preview(str(exc), 200),
                )
                raise HTTPException(status_code=502, detail="Google 搜索失败，请检查 CSE 配置。") from exc
            items = filter_chinese_entries(items)
            for item in items:
                link = item.get("link")
                if not link or link in seen_links:
                    continue
                host = urlparse(link).netloc.lower()
                if _is_blocked(link):
                    req_logger.info("Skip blocked domain link=%s", link)
                    continue
                # 对单一域名做简单限流，避免结果几乎全部来自一个网站
                used = domain_counts.get(host, 0)
                if used >= WEB_MAX_PER_DOMAIN:
                    req_logger.info("Skip link=%s due to per-domain cap host=%s", link, host)
                    continue
                domain_counts[host] = used + 1
                seen_links.add(link)
                fetched_urls.append(link)
                if len(fetched_urls) >= target_fetch:
                    break
            if len(fetched_urls) >= target_fetch:
                break
        req_logger.info("Web search done fetched_urls=%s", len(fetched_urls))

    embedding_provider = None
    final_target = max(retrieval_cfg.topk_final, retrieval_cfg.min_sources)
    dense_limit = max(retrieval_cfg.topk_dense, final_target)
    lexical_limit = max(retrieval_cfg.topk_sparse, final_target)

    need_embedding = bool(enable_web or effective_kb_ids or req.mode == "history_decision")
    if need_embedding:
        embedding_store = get_embedding_store()
        embedding_provider = embedding_store.get_default()
        if embedding_provider is None:
            raise HTTPException(status_code=503, detail="未配置默认 Embedding 服务，请先在设置中添加")

    fetcher: PageFetcher | None = None
    if enable_web:
        crawl_cfg = app_settings.crawl
        fetcher = PageFetcher(
            timeout=crawl_cfg.timeout_sec,
            concurrency=crawl_cfg.concurrency,
            request_id=request_id,
            max_retries=crawl_cfg.max_retries,
            delay_range=(crawl_cfg.delay_min, crawl_cfg.delay_max),
            domain_cooldown=crawl_cfg.domain_cooldown,
            proxies=settings.CRAWLER_PROXIES,
        )

    if enable_web and fetched_urls and fetcher and embedding_provider:
        fetch_results = await fetcher.fetch(fetched_urls)
        for result in fetch_results:
            if result.error or not result.html:
                continue
            final_url = result.final_url or result.url
            if not final_url:
                continue
            doc = extract_content(result.html, final_url, default_title=final_url, request_id=request_id)
            if not doc:
                continue
            if is_chinese_heavy(doc.text or ""):
                req_logger.info("Skip Chinese-heavy page url=%s", final_url)
                continue
            if doc_cache.should_skip(final_url, doc.content_hash):
                continue
            doc_chunks = chunk_document(final_url, doc.title, doc.text, request_id=request_id)
            if not doc_chunks:
                continue
            chunk_texts = [chunk.text for chunk in doc_chunks]
            vectors = await embed_texts(chunk_texts, provider=embedding_provider)
            if not vectors or len(vectors) != len(doc_chunks):
                continue
            dense_dim = _resolve_dense_dim(vectors, embedding_provider.dense_dim)
            doc_id = f"web::{hashlib.sha1(final_url.encode('utf-8')).hexdigest()}"
            pg_start = time.perf_counter()
            for chunk in doc_chunks:
                kb_dao.upsert_chunk(
                    chunk_id=chunk.chunk_id,
                    kb_id=WEB_KB_ID,
                    doc_id=doc_id,
                    title=chunk.title,
                    url=chunk.url,
                    position=chunk.position,
                    content=chunk.text,
                    kb_category="web_snapshot",
                )
            pg_elapsed = (time.perf_counter() - pg_start) * 1000
            req_logger.info(
                "Postgres upsert kb=%s doc=%s chunks=%s elapsed=%.1fms",
                WEB_KB_ID,
                doc_id,
                len(doc_chunks),
                pg_elapsed,
            )
            if is_debug_enabled():
                count = kb_dao.count_chunks_by_doc(doc_id)
                req_logger.debug("Postgres doc chunk count doc=%s count=%s", doc_id, count)
            try:
                milvus_store.upsert_chunks(
                    [
                        {
                            "chunk_id": chunk.chunk_id,
                            "kb_id": WEB_KB_ID,
                            "doc_id": doc_id,
                            "kb_category": "web_snapshot",
                            "dense": vec.get("dense"),
                        }
                        for chunk, vec in zip(doc_chunks, vectors)
                    ],
                    dense_dim=dense_dim,
                    request_id=request_id,
                )
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            doc_cache.upsert(final_url, doc.content_hash)
            req_logger.info(
                "Crawler pipeline stored doc_id=%s url=%s chunks=%s",
                doc_id,
                final_url,
                len(doc_chunks),
            )

    retrieval_targets: List[str] = []
    if effective_kb_ids:
        retrieval_targets.extend(effective_kb_ids)
    if enable_web:
        retrieval_targets.append(WEB_KB_ID)
    if retrieval_targets:
        seen_ids: set[str] = set()
        ordered: List[str] = []
        for kid in retrieval_targets:
            if kid and kid not in seen_ids:
                seen_ids.add(kid)
                ordered.append(kid)
        retrieval_targets = ordered
    
    req_logger.info(
        "Retrieval targets: %s (from effective_kb_ids=%s, enable_web=%s)",
        retrieval_targets,
        effective_kb_ids,
        enable_web,
    )

    embedding_usage: dict = {"need_web": enable_web, "used_dense": False}
    retrieved_chunks: list[dict] = []
    retrieval_stats = {"dense_candidates": 0, "lexical_candidates": 0, "fused": 0}

    # 使用统一检索接口（支持项目知识库 + 独立知识库）
    if retrieval_targets and req.mode != "history_decision":
        if embedding_provider is None:
            raise HTTPException(status_code=503, detail="未配置默认 Embedding 服务，请先在设置中添加")
        
        embedding_usage.update(
            {
                "provider_id": embedding_provider.id,
                "model": embedding_provider.model,
                "expected_dense": embedding_provider.output_dense,
                "used_dense": True,
            }
        )
        
        try:
            # 使用 RetrievalFacade.retrieve_from_kb 统一接口
            from app.platform.retrieval.facade import RetrievalFacade
            
            pool = _get_pool()
            retrieval_facade = RetrievalFacade(pool)
            
            req_logger.info(
                f"Knowledge base retrieval: kb_ids={effective_kb_ids}, query={req.message[:50]}..."
            )
            
            # 调用新的统一接口（自动处理项目知识库 + 独立知识库）
            chunks_results = await retrieval_facade.retrieve_from_kb(
                query=req.message,
                kb_ids=effective_kb_ids,
                kb_categories=None,  # 不限制分类
                embedding_provider=embedding_provider,
                top_k=final_target,
                dense_limit=dense_limit,
                lexical_limit=lexical_limit,
            )
            
            # 转换为旧格式以兼容后续代码
            retrieved_chunks = []
            for chunk in chunks_results:
                retrieved_chunks.append({
                    "chunk_id": chunk.chunk_id,
                    "kb_id": chunk.meta.get("kb_id"),
                    "doc_id": chunk.meta.get("doc_id"),
                    "title": chunk.meta.get("title", ""),
                    "url": chunk.meta.get("url"),
                    "text": chunk.text,
                    "position": chunk.meta.get("position"),
                    "score": chunk.score,
                    "hit_dense": True,
                    "hit_lexical": True,
                    "kb_category": chunk.meta.get("kb_category", "general_doc"),
                })
            
            retrieval_stats = {
                "dense_candidates": len(chunks_results),
                "lexical_candidates": len(chunks_results),
                "fused": len(retrieved_chunks),
            }
            
            req_logger.info(
                f"Knowledge base retrieval done: {len(retrieved_chunks)} chunks from kb_ids={effective_kb_ids}"
            )
                
        except Exception as exc:
            req_logger.error(f"Knowledge base retrieval failed: {exc}", exc_info=True)
            raise HTTPException(status_code=502, detail=f"检索失败: {str(exc)}") from exc
        
        embedding_usage["retrieval"] = retrieval_stats
    
    used_search = enable_web
    req_logger.info(
        "Retrieval summary kb_ids=%s chunks=%s used_search=%s chunks_sample=%s",
        retrieval_targets,
        len(retrieved_chunks),
        used_search,
        [{"kb_id": c.get("kb_id"), "doc_id": c.get("doc_id")[:16] if c.get("doc_id") else None, "score": round(c.get("score", 0), 3)} for c in retrieved_chunks[:5]],
    )

    sources: list[Source] = []
    if req.mode != "history_decision":
        sources = (
            _prepare_sources(retrieved_chunks, min_sources=retrieval_cfg.min_sources)
            if retrieved_chunks
            else []
        )

    answer = ""
    orchestrator_sections: Optional[List[ChatSection]] = None
    orchestrator_followups: Optional[List[str]] = None
    # 初始化 orchestrator_meta（确保始终有值，用于可观测性）
    effective_detail_level = req.detail_level or "normal"
    orchestrator_meta: dict = {
        "enabled": bool(req.enable_orchestrator),
        "used": False,  # 稍后如果实际使用了会改为 True
        "mode": req.mode,
        "detail_level": effective_detail_level,
        "modules": [],
    }
    
    # 处理附件上下文
    attachment_context = ""
    if req.attachment_ids:
        req_logger.info(f"Processing attachments: ids={req.attachment_ids}")
        attachment_store = get_attachment_store()
        attachments = attachment_store.get_many(req.attachment_ids)
        
        if attachments:
            all_chunks = []
            for att in attachments:
                # 分块
                chunks = chunk_attachment_text(
                    att.extracted_text,
                    att.original_name,
                    chunk_size=4000,
                    overlap=200,
                )
                all_chunks.extend(chunks)
            
            # 选择相关块
            if all_chunks:
                selected_chunks = select_relevant_chunks(
                    all_chunks,
                    req.message,
                    top_k=8,
                )
                
                # 构建上下文
                attachment_context = build_attachment_context(
                    selected_chunks,
                    max_chars=60000,
                )
                
                req_logger.info(
                    f"Attachment context built: attachments={len(attachments)} "
                    f"total_chunks={len(all_chunks)} selected_chunks={len(selected_chunks)} "
                    f"context_chars={len(attachment_context)}"
                )
    
    # ==================== 编排器集成 ====================
    # 编排器默认启用（除非明确设置为 False）
    use_orchestrator = req.enable_orchestrator if req.enable_orchestrator is not None else True
    
    if use_orchestrator:
        req_logger.info("Using orchestrator for answer generation")
        
        # 初始化编排器
        orchestrator = OrchestratorService(
            call_llm=call_chat_llm,
            call_llm_stream=call_chat_llm_stream,
        )
        
        try:
            # 步骤1: 需求抽取
            req_logger.info("Orchestrator: Extracting requirements")
            requirements = await orchestrator.extract_requirements(
                user_message=enhanced_message,
                history=history_for_llm,
                ui_detail_level=req.detail_level or "normal",
            )
            
            # 更新 orchestrator_meta（编排器成功使用）
            orchestrator_meta.update({
                "used": True,  # 标记编排器实际被使用
                "intent": requirements.intent,
                "detail_level": requirements.detail_level,
                "blueprint_modules": requirements.blueprint_modules,
                "modules": requirements.blueprint_modules,  # 别名，便于前端使用
                "assumptions": requirements.assumptions,
            })
            effective_detail_level = requirements.detail_level
            
            # 保存澄清问题到 followups
            orchestrator_followups = requirements.clarification_questions
            
            req_logger.info(
                f"Requirements extracted: intent={requirements.intent}, "
                f"detail_level={requirements.detail_level}, "
                f"modules={requirements.blueprint_modules}"
            )
            
            # 步骤2: 生成模块化答案
            req_logger.info("Orchestrator: Generating modular answer")
            
            # 准备上下文
            context_parts = []
            if attachment_context:
                context_parts.append(f"[附件内容]\n{attachment_context}")
            
            if retrieved_chunks:
                chunks_text = "\n\n".join([
                    f"[{i+1}] {chunk.get('title', '')}\n{chunk.get('text', '')[:500]}"
                    for i, chunk in enumerate(retrieved_chunks[:5])
                ])
                context_parts.append(f"[检索结果]\n{chunks_text}")
            
            combined_context = "\n\n".join(context_parts)
            
            # 生成答案
            raw_answer = await orchestrator.generate_modular_answer(
                user_message=enhanced_message,
                requirements=requirements,
                context=combined_context,
                history=history_for_llm,
                sources=sources,
                on_token=stream_tokens,
            )
            
            answer = raw_answer
            
            # 步骤3: 解析 sections
            req_logger.info("Orchestrator: Parsing sections from answer")
            orchestrator_sections = orchestrator.parse_sections_from_answer(
                answer=raw_answer,
                blueprint_modules=requirements.blueprint_modules,
            )
            
            req_logger.info(f"Orchestrator: Generated {len(orchestrator_sections)} sections")
            req_logger.info(
                "[orchestrator] SUCCESS: sections=%d followups=%d meta_used=%s",
                len(orchestrator_sections) if orchestrator_sections else 0,
                len(orchestrator_followups) if orchestrator_followups else 0,
                orchestrator_meta.get("used", False)
            )
            
        except Exception as exc:
            req_logger.error(f"Orchestrator failed, fallback to normal mode: {exc}", exc_info=True)
            use_orchestrator = False
            orchestrator_meta["used"] = False  # 明确标记未使用
            orchestrator_meta["error"] = str(exc)[:200]  # 记录错误（截断）
            # 继续使用原有流程
    
    # ==================== 原有流程 ====================
    if not use_orchestrator:
        if req.mode == "history_decision":
            if embedding_provider is None:
                raise HTTPException(status_code=503, detail="历史案例模式需要可用的 Embedding 服务")
            decision_kb_ids = retrieval_targets or None
            decision_result = await generate_history_decision_answer(
                raw_question=enhanced_message,
                history_messages=history_for_llm,
                call_answer_llm=call_chat_llm,
                call_profile_llm=call_plan_llm,
                embedding_provider=embedding_provider,
                kb_ids=decision_kb_ids,
                dense_topk=dense_limit,
                lexical_topk=lexical_limit,
                final_topk=final_target,
                request_id=request_id,
            )
            sources = (
                _prepare_sources(decision_result.combined_chunks, min_sources=retrieval_cfg.min_sources)
                if decision_result.combined_chunks
                else []
            )
            embedding_usage["used_dense"] = True
            embedding_usage["history_decision"] = {
                "case_count": decision_result.case_count,
                "total_sources": len(decision_result.combined_chunks),
                "case_profile": decision_result.case_profile.model_dump(),
            }
            search_queries = decision_result.search_queries
            answer = decision_result.answer or ""
            if stream_tokens and answer:
                await stream_tokens(answer)
        else:
            extra_decision_context = ""
            if req.mode == "decision":
                try:
                    extra_decision_context = await retrieve_context(req.message) or ""
                except Exception as exc:  # noqa: BLE001
                    req_logger.warning(
                        "Decision mode retrieve_context failed: %s",
                        safe_preview(str(exc), 200),
                    )
                    extra_decision_context = ""
            style = intent_plan.answer_style
            if stream_tokens:

                async def _fallback_stream_call(system_prompt, user_prompt, history, on_chunk):
                    result = await call_chat_llm(system_prompt, user_prompt, history)
                    if result:
                        await on_chunk(result)
                    return result

                stream_call = call_chat_llm_stream or _fallback_stream_call
                try:
                    answer = await summarize_with_llm_stream(
                        stream_call,
                        enhanced_message,
                        style,
                        sources,
                        history_for_llm,
                        on_chunk=stream_tokens,
                        request_id=request_id,
                        model_base_url=model_host,
                        mode=req.mode,
                        extra_context=extra_decision_context,
                        attachment_context=attachment_context,
                    )
                except HTTPException as exc:
                    req_logger.warning(
                        "Summarizer(stream) fallback status=%s detail=%s",
                        exc.status_code,
                        safe_preview(exc.detail, 200),
                    )
                    answer = _fallback_answer_from_sources(exc.detail, sources)
                    await stream_tokens(answer)
                except Exception as exc:  # noqa: BLE001
                    req_logger.error("Summarizer(stream) unexpected error: %s", exc, exc_info=True)
                    answer = _fallback_answer_from_sources(str(exc), sources)
                    await stream_tokens(answer)
            else:
                try:
                    answer = await summarize_with_llm(
                        call_chat_llm,
                        enhanced_message,
                        style,
                        sources,
                        history_for_llm,
                        request_id=request_id,
                        model_base_url=model_host,
                        mode=req.mode,
                        extra_context=extra_decision_context,
                        attachment_context=attachment_context,
                    )
                except HTTPException as exc:
                    req_logger.warning(
                        "Summarizer fallback triggered status=%s detail=%s",
                        exc.status_code,
                        safe_preview(exc.detail, 200),
                    )
                    answer = _fallback_answer_from_sources(exc.detail, sources)
                except Exception as exc:  # noqa: BLE001
                    req_logger.error("Summarizer unexpected error: %s", exc, exc_info=True)
                    answer = _fallback_answer_from_sources(str(exc), sources)

    answer = answer or ""
    normalized_answer = normalize_bullets_to_ordered(answer)

    append_history_message(
        session_id,
        "assistant",
        normalized_answer,
        {
            "sources": [src.model_dump() for src in sources],
            "used_search": used_search,
            "search_queries": search_queries,
            "embedding_usage": embedding_usage,
            "intent_plan": intent_plan.model_dump(),
            "used_model": used_model.model_dump(),
        },
    )

    update_history_session_meta(
        session_id,
        {
            "last_model": used_model.model_dump(),
            "last_enable_web": enable_web,
            "last_kb_ids": effective_kb_ids,
        },
    )
    
    # 最终日志：确认编排器输出（用于 Network 验证）
    req_logger.info(
        "[orchestrator] FINAL RESPONSE: sections=%s followups=%s meta_used=%s meta_modules=%s",
        len(orchestrator_sections) if orchestrator_sections else 0,
        len(orchestrator_followups) if orchestrator_followups else 0,
        orchestrator_meta.get("used", False),
        orchestrator_meta.get("modules", [])
    )

    # 🔧 Solution A: Convert sections to dict to avoid Pydantic type mismatch
    # (handles case where ChatSection instances might be from different module imports)
    sections_payload = None
    if orchestrator_sections:
        sections_payload = [
            s.model_dump() if hasattr(s, "model_dump") else dict(s) 
            for s in orchestrator_sections
        ]

    return ChatResponse(
        answer=normalized_answer,
        sources=sources,
        llm_key=response_llm_key,
        llm_name=response_llm_name,
        session_id=session_id,
        search_mode=search_mode,
        used_search=used_search,
        search_queries=search_queries,
        search_usage_count=usage_count,
        search_usage_warning=usage_warning,
        used_model=used_model,
        # 编排器输出 (converted to dict for schema compatibility)
        sections=sections_payload,
        followups=orchestrator_followups,
        orchestrator_meta=orchestrator_meta,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest) -> ChatResponse:
    request_id = uuid4().hex
    return await _chat_endpoint_impl(req, request_id)


@router.post("/chat/stream")
async def chat_stream_endpoint(req: ChatRequest):
    request_id = uuid4().hex
    queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
    done_event = asyncio.Event()

    async def send_delta(text: str) -> None:
        if text:
            await queue.put(_format_sse_event("delta", {"text": text}))

    async def runner():
        try:
            response = await _chat_endpoint_impl(
                req,
                request_id,
                stream_tokens=send_delta,
            )
            await queue.put(_format_sse_event("result", response.model_dump()))
        except HTTPException as exc:
            await queue.put(
                _format_sse_event(
                    "error",
                    {"status": exc.status_code, "detail": exc.detail},
                )
            )
        except Exception as exc:  # noqa: BLE001
            await queue.put(
                _format_sse_event(
                    "error",
                    {"status": 500, "detail": str(exc)},
                )
            )
        finally:
            done_event.set()
            await queue.put(None)

    asyncio.create_task(runner())

    async def heartbeat_sender():
        try:
            await queue.put(b":open\n\n")
            while not done_event.is_set():
                await asyncio.sleep(STREAM_HEARTBEAT_INTERVAL)
                if done_event.is_set():
                    break
                await queue.put(b":heartbeat\n\n")
        except asyncio.CancelledError:
            pass

    heartbeat_task = asyncio.create_task(heartbeat_sender())

    async def event_generator():
        try:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                yield chunk
        finally:
            done_event.set()
            if heartbeat_task and not heartbeat_task.done():
                heartbeat_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await heartbeat_task

    return StreamingResponse(event_generator(), media_type="text/event-stream")
