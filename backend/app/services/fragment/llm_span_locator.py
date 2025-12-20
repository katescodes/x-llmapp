"""
TenderSampleSpanLocator - 使用 LLM 在招标书 docx 的 body 元素序列中定位“范本片段”的范围（start/end body index）

输入：body 元素窗口（段落/表格），每个元素包含原始 body 索引 i
输出：严格 JSON 数组（由 LLM 生成）并解析为 spans 列表
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class TenderSampleSpan:
    fragment_type: str
    title: str
    start_body_index: int
    end_body_index: int
    confidence: float
    reason: str


def _extract_json_array(text: str) -> List[Dict[str, Any]]:
    """
    从 LLM 输出中容错提取 JSON 数组（严格返回 list[dict]）
    - 支持 markdown code fence 包裹
    - 支持从混杂文本中抽取第一个数组片段
    """
    if not text:
        raise ValueError("empty llm output")

    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if m:
        text = m.group(1).strip()

    # 尝试抽取第一个 JSON 数组
    m2 = re.search(r"(\[[\s\S]*\])", text.strip())
    if m2:
        text = m2.group(1)

    obj = json.loads(text)
    if not isinstance(obj, list):
        raise ValueError("llm output is not a JSON array")
    out: List[Dict[str, Any]] = []
    for it in obj:
        if isinstance(it, dict):
            out.append(it)
    return out


class TenderSampleSpanLocator:
    """
    使用 LLM 定位范本 spans。

    注意：
    - 本类对外提供同步 locate()，内部用 anyio.from_thread.run() 调 async llm_client.chat_completion()
    - locate() 输入的 elements_window 必须是带原始 body index i 的列表
    """

    SYSTEM_PROMPT = """
你是“招标书范本片段定位器”。输入是 Word 文档 body 元素序列（段落/表格），每个元素有索引 i。
任务：找出招标书中“投标文件格式/样表/范本”对应的片段范围（start_body_index/end_body_index），用于后续原样拷贝到投标文件导出文档中。

规则：
1) 范本通常位于“附录/投标文件格式/表格样表”区域。
2) 范本可能由：标题段落 + 若干段落/表格组成；也可能标题在表格第一行。
3) 每个 fragment 必须覆盖完整内容：从标题（或标题前一小段）到下一个同级范本标题之前。
4) 只输出投标人需要填写/提交的表格或格式文本（投标函、授权书、报价表、偏离表、承诺/声明等）。
5) 不要把“招标公告/投标人须知/评标办法/合同条款/技术规范”当成范本。
6) 输出严格 JSON 数组，不要解释文字。
""".strip()

    def __init__(self, model: Optional[str] = None):
        self.model = model

    async def _locate_async(self, elements_window: List[Dict[str, Any]]) -> List[TenderSampleSpan]:
        from app.services.llm_client import get_llm_client

        llm_client = get_llm_client()
        user_prompt = (
            "你拿到的是 docx 的 body 元素序列（段落/表格），索引从 0..N-1。\n"
            "任务是：从“附录/格式/样表/表格/投标文件组成”区域识别范本片段。\n"
            "特别强调：范本常在表格里，标题可能出现在表格第一行或前一段普通段落。\n"
            "输出必须是 index 范围，不要复刻招标目录。\n\n"
            "输入元素窗口（数组，字段 i/t/txt/style/h）：\n"
            f"{json.dumps(elements_window, ensure_ascii=False)}\n\n"
            "现在只输出严格 JSON 数组，格式：\n"
            "[\n"
            "  {\n"
            '    "fragment_type": "BID_LETTER|AUTHORIZATION|PRICE_SUMMARY|PRICE_DETAIL|DEVIATION_BUSINESS|DEVIATION_TECH|COMMITMENT|QUALIFICATION|OTHER",\n'
            '    "title": "投标函（格式）",\n'
            '    "start_body_index": 123,\n'
            '    "end_body_index": 140,\n'
            '    "confidence": 0.86,\n'
            '    "reason": "锚点在‘投标函（格式）’后，连续表格直到下一个‘授权委托书（格式）’"\n'
            "  }\n"
            "]"
        )

        resp = await llm_client.chat_completion(
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            model=self.model,
            temperature=0.1,
            max_tokens=1800,
        )
        text = (resp or {}).get("content", "") or ""
        arr = _extract_json_array(text)

        spans: List[TenderSampleSpan] = []
        for it in arr:
            try:
                spans.append(
                    TenderSampleSpan(
                        fragment_type=str(it.get("fragment_type") or "OTHER").strip() or "OTHER",
                        title=str(it.get("title") or "").strip(),
                        start_body_index=int(it.get("start_body_index")),
                        end_body_index=int(it.get("end_body_index")),
                        confidence=float(it.get("confidence") if it.get("confidence") is not None else 0.0),
                        reason=str(it.get("reason") or "").strip(),
                    )
                )
            except Exception:
                continue
        return spans

    def locate(self, elements_window: List[Dict[str, Any]]) -> List[TenderSampleSpan]:
        """
        同步定位接口（供同步 service/extractor 调用）。
        """
        try:
            import anyio

            return anyio.from_thread.run(self._locate_async, elements_window)
        except Exception:
            # 兜底：如果不在 anyio thread context（理论上很少），再尝试 asyncio.run
            import asyncio

            return asyncio.run(self._locate_async(elements_window))


