from __future__ import annotations

import json
from dataclasses import dataclass
import logging
from typing import Awaitable, Callable, List, Optional, Sequence, Tuple

from pydantic import BaseModel, Field, ValidationError

from app.schemas.case import CaseRecord
from app.schemas.chat import Message
from app.services.case_utils import case_to_rag_text
from app.services.dao import kb_dao
from app.services.embedding_provider_store import EmbeddingProviderStored
from app.services.logging.request_logger import get_request_logger, safe_preview
logger = logging.getLogger(__name__)
from app.services.prompt_templates import HISTORY_DECISION_SYSTEM_PROMPT
from app.platform.retrieval.providers.legacy.retriever import retrieve

LLMCall = Callable[[str, str, Sequence[Message]], Awaitable[str]]


class CaseProfile(BaseModel):
    problem_summary: str
    context: str
    constraints: List[str] = Field(default_factory=list)
    search_queries: List[str] = Field(default_factory=list)


@dataclass
class HistoryDecisionResult:
    answer: str
    combined_chunks: List[dict]
    case_profile: CaseProfile
    search_queries: List[str]
    case_count: int


async def parse_to_case_profile(
    raw_question: str,
    llm_call: LLMCall,
    request_id: Optional[str] = None,
) -> CaseProfile:
    req_logger = get_request_logger(logger, request_id)
    system_prompt = "你是一个案例理解助手，只负责把用户描述的新情况整理成匹配历史案例用的结构。"
    user_prompt = f"""
请根据【用户原始问题】整理出一个 JSON 对象，字段如下：
- "problem_summary"：用 1 句话概括这次要解决的关键问题。
- "context"：用 2~4 句话总结当前的背景（行业/项目类型/角色/关键条件）。
- "constraints"：列出用户明确提到的约束条件（时间、预算、合规、资源等），没有就给空数组。
- "search_queries"：列出 3~6 个短语，用来在“历史案例库”中检索相似案例。

严格输出 JSON，不要任何说明性文字。
用户原始问题：
{raw_question}
""".strip()
    try:
        result = await llm_call(system_prompt, user_prompt, [])
    except Exception as exc:  # noqa: BLE001
        req_logger.warning("Case profile LLM failed: %s", safe_preview(str(exc), 200))
        return CaseProfile(
            problem_summary=raw_question[:80],
            context=raw_question[:200],
            constraints=[],
            search_queries=[],
        )
    try:
        data = json.loads(result)
        return CaseProfile(**data)
    except (json.JSONDecodeError, ValidationError) as exc:  # noqa: BLE001
        req_logger.warning(
            "Case profile parse failed payload=%s reason=%s",
            safe_preview(result, 200),
            safe_preview(str(exc), 200),
        )
        return CaseProfile(
            problem_summary=raw_question[:80],
            context=raw_question[:200],
            constraints=[],
            search_queries=[],
        )


def _dedupe_queries(profile: CaseProfile, raw_question: str) -> List[str]:
    raw_queries = [profile.problem_summary, profile.context, *profile.search_queries, raw_question]
    cleaned: List[str] = []
    for text in raw_queries:
        value = (text or "").strip()
        if not value:
            continue
        if value not in cleaned:
            cleaned.append(value)
    return cleaned[:6]


async def _retrieve_case_chunks(
    queries: List[str],
    kb_ids: Optional[List[str]],
    embedding_provider: EmbeddingProviderStored,
    dense_topk: int,
    lexical_topk: int,
    final_topk: int,
    request_id: Optional[str],
) -> List[dict]:
    aggregated: dict[str, dict] = {}
    for query in queries:
        hits, _ = await retrieve(
            query=query,
            kb_ids=kb_ids,
            kb_categories=["history_case"],
            anchors=[],
            embedding_provider=embedding_provider,
            dense_topk=dense_topk,
            lexical_topk=lexical_topk,
            final_topk=final_topk,
            request_id=request_id,
        )
        for hit in hits:
            doc_id = hit.get("doc_id")
            if not doc_id:
                continue
            score = float(hit.get("score") or 0.0)
            stored = aggregated.get(doc_id)
            if stored is None or score > stored.get("score", 0.0):
                aggregated[doc_id] = {**hit, "score": score}
    return sorted(aggregated.values(), key=lambda item: item.get("score", 0.0), reverse=True)


def _build_case_records(
    chunks: List[dict],
    profile: CaseProfile,
) -> Tuple[List[CaseRecord], List[dict]]:
    if not chunks:
        return [], []
    doc_ids = [chunk["doc_id"] for chunk in chunks if chunk.get("doc_id")]
    meta_map = kb_dao.get_documents_meta(doc_ids)
    grouped: dict[str, List[dict]] = {}
    for chunk in chunks:
        doc_id = chunk.get("doc_id")
        if not doc_id:
            continue
        grouped.setdefault(doc_id, []).append(chunk)

    records: List[CaseRecord] = []
    case_chunks: List[dict] = []

    for doc_id, doc_chunks in grouped.items():
        doc_meta = meta_map.get(doc_id, {})
        meta_payload = (doc_meta.get("meta") or {}) if isinstance(doc_meta, dict) else {}
        raw_case = meta_payload.get("case_record")
        record: CaseRecord
        if isinstance(raw_case, dict):
            try:
                record = CaseRecord(**raw_case)
            except ValidationError:
                record = CaseRecord(
                    id=doc_id,
                    title=raw_case.get("title") or doc_meta.get("filename") or "历史案例",
                    situation=raw_case.get("situation") or "",
                    problem=raw_case.get("problem") or profile.problem_summary,
                    action=raw_case.get("action") or "",
                    result=raw_case.get("result") or "",
                    lessons=raw_case.get("lessons") or "",
                    tags=raw_case.get("tags") or [],
                )
        else:
            snippet = " ".join((chunk.get("text") or "")[:400] for chunk in doc_chunks).strip()
            record = CaseRecord(
                id=doc_id,
                title=doc_meta.get("filename") or doc_chunks[0].get("title") or "历史案例",
                situation=meta_payload.get("situation") or snippet[:200],
                problem=meta_payload.get("problem") or profile.problem_summary,
                action=meta_payload.get("action") or "",
                result=meta_payload.get("result") or "",
                lessons=meta_payload.get("lessons") or snippet,
                tags=meta_payload.get("tags") or [],
            )

        records.append(record)
        case_chunks.append(
            {
                "chunk_id": f"case::{doc_id}",
                "kb_id": doc_meta.get("kb_id") or doc_chunks[0].get("kb_id"),
                "doc_id": doc_id,
                "title": record.title,
                "url": doc_chunks[0].get("url"),
                "text": case_to_rag_text(record),
                "score": doc_chunks[0].get("score", 0.0),
                "kb_category": "history_case",
            }
        )
    return records, case_chunks


async def _retrieve_support_chunks(
    raw_question: str,
    kb_ids: Optional[List[str]],
    skip_doc_ids: set[str],
    embedding_provider: EmbeddingProviderStored,
    dense_topk: int,
    lexical_topk: int,
    final_topk: int,
    request_id: Optional[str],
) -> List[dict]:
    hits, _ = await retrieve(
        query=raw_question,
        kb_ids=kb_ids,
        kb_categories=None,
        anchors=[],
        embedding_provider=embedding_provider,
        dense_topk=dense_topk,
        lexical_topk=lexical_topk,
        final_topk=final_topk,
        request_id=request_id,
    )
    support: dict[str, dict] = {}
    for hit in hits:
        doc_id = hit.get("doc_id") or hit.get("chunk_id")
        if not doc_id or doc_id in skip_doc_ids:
            continue
        if hit.get("kb_category") == "history_case":
            continue
        score = float(hit.get("score") or 0.0)
        stored = support.get(doc_id)
        if stored is None or score > stored.get("score", 0.0):
            support[doc_id] = {**hit, "score": score}
    ranked = sorted(support.values(), key=lambda item: item.get("score", 0.0), reverse=True)
    return ranked[:final_topk]


def _build_prompt_blocks(
    profile: CaseProfile,
    case_records: List[CaseRecord],
    case_count: int,
    support_chunks: List[dict],
) -> Tuple[str, str]:
    if case_records:
        case_lines = [
            f"[案例{idx}] {case_to_rag_text(record)}"
            for idx, record in enumerate(case_records, start=1)
        ]
        cases_text = "\n\n".join(case_lines)
    else:
        cases_text = "（未找到足够匹配的历史案例，请结合常识谨慎输出。）"

    if support_chunks:
        support_lines = []
        for offset, chunk in enumerate(support_chunks, start=1):
            source_id = case_count + offset
            title = chunk.get("title") or chunk.get("doc_id") or "补充资料"
            snippet = (chunk.get("text") or "")[:500].strip()
            support_lines.append(
                f"[资料{source_id}] 标题：{title}\n内容：{snippet or '（内容为空）'}"
            )
        support_text = "\n\n".join(support_lines)
    else:
        support_text = "（未补充其它资料）"

    constraints_text = (
        "\n".join(f"- {item}" for item in profile.constraints if item.strip()) or "无"
    )

    prompt_body = f"""
【本次情况】
- 关键问题：{profile.problem_summary}
- 背景：{profile.context}
- 约束条件：
{constraints_text}

【历史案例（注明 [案例编号]）】
{cases_text}

【补充资料（编号延续 Source 列表，从 {case_count + 1} 开始）】
{support_text}
""".strip()

    return prompt_body, constraints_text


async def generate_history_decision_answer(
    raw_question: str,
    history_messages: Sequence[Message],
    call_answer_llm: LLMCall,
    call_profile_llm: LLMCall,
    embedding_provider: EmbeddingProviderStored,
    *,
    kb_ids: Optional[List[str]],
    dense_topk: int,
    lexical_topk: int,
    final_topk: int,
    request_id: Optional[str] = None,
) -> HistoryDecisionResult:
    req_logger = get_request_logger(logger, request_id)
    profile = await parse_to_case_profile(raw_question, call_profile_llm, request_id)
    queries = _dedupe_queries(profile, raw_question)

    case_hits = await _retrieve_case_chunks(
        queries,
        kb_ids,
        embedding_provider,
        dense_topk,
        lexical_topk,
        final_topk,
        request_id,
    )
    case_records, case_chunks = _build_case_records(case_hits[:final_topk], profile)
    skip_docs = {record.id for record in case_records}

    support_chunks = []
    if len(case_chunks) < final_topk:
        support_chunks = await _retrieve_support_chunks(
            raw_question,
            kb_ids,
            skip_docs,
            embedding_provider,
            dense_topk=max(8, dense_topk // 2),
            lexical_topk=max(8, lexical_topk // 2),
            final_topk=final_topk,
            request_id=request_id,
        )

    prompt_body, _ = _build_prompt_blocks(profile, case_records, len(case_chunks), support_chunks)
    user_prompt = f"""
【用户原始问题】
{raw_question}

{prompt_body}

请输出一份决策建议报告，必须包含以下章节：
1. 当前情况判断（说明问题本质、案例相似点/差异并引用 [案例x]）
2. 可借鉴的经验原则（2~4 条，标明来源：[案例x]）
3. 方案规划：至少两个方案（比如方案A/方案B），每个包含【参考案例】【思路】【适用前提】【执行步骤（1、2、3…）】【潜在风险】
4. 风险与坑：列出 2~5 个在历史案例中发生过的坑，说明来自哪些案例
5. 信息缺口：列出 1~3 个需要补充的信息

要求：
- 引用历史案例时使用 [案例编号]；引用补充资料时可使用 [资料编号]。
- 如发现案例与当前场景差异较大，需在“当前情况判断”中明确说明。
- 回答需保持中文，条理清晰，编号规范。
""".strip()

    answer = await call_answer_llm(HISTORY_DECISION_SYSTEM_PROMPT, user_prompt, history_messages)
    combined_chunks = [*case_chunks, *support_chunks]
    req_logger.info(
        "History decision generated answer chars=%s cases=%s support=%s",
        len(answer or ""),
        len(case_chunks),
        len(support_chunks),
    )

    return HistoryDecisionResult(
        answer=answer or "",
        combined_chunks=combined_chunks,
        case_profile=profile,
        search_queries=queries,
        case_count=len(case_chunks),
    )


