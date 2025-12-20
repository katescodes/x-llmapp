"""
确定性 style_hints fallback
目标：即使 LLM 解析失败，也能给出可用的 style_hints（至少标题/正文不为空）
"""

from __future__ import annotations

import re
from typing import Optional, Dict, Any

from app.services.template.docx_extractor import DocxExtractResult, BlockType
from app.services.template.template_spec import StyleHints

_RE_H_ZH = re.compile(r"标题\s*([1-9])")
_RE_H_EN = re.compile(r"Heading\s*([1-9])", re.I)


def _match_heading_level(style_name: str) -> Optional[int]:
    m = _RE_H_ZH.search(style_name or "")
    if m:
        return int(m.group(1))
    m = _RE_H_EN.search(style_name or "")
    if m:
        return int(m.group(1))
    return None


def _pick_most_common_style(style_count: Dict[str, int], predicate) -> Optional[str]:
    best = None
    best_cnt = -1
    for name, cnt in style_count.items():
        if not name:
            continue
        if predicate(name):
            if cnt > best_cnt:
                best_cnt = cnt
                best = name
    return best


def build_style_hints_fallback(extract_result: DocxExtractResult) -> StyleHints:
    style_stats = extract_result.style_stats or {}
    style_count: Dict[str, int] = style_stats.get("style_count") or {}
    heading_style_by_level = style_stats.get("heading_style_by_level") or {}
    body_style_guess = style_stats.get("body_style_guess")
    has_table = bool(style_stats.get("has_table", False))

    # heading1..5：优先匹配 “标题1/Heading 1” 等样式名（含前缀 + 也能命中）
    heading_styles: Dict[int, Optional[str]] = {}
    for lvl in range(1, 6):
        # 1) extractor 的按层级统计（更可靠）
        by_lvl = heading_style_by_level.get(str(lvl))
        if isinstance(by_lvl, str) and by_lvl.strip():
            heading_styles[lvl] = by_lvl.strip()
            continue

        # 2) 兜底：按名称匹配
        heading_styles[lvl] = _pick_most_common_style(
            style_count, lambda n, _lvl=lvl: _match_heading_level(n) == _lvl
        )

    # body：优先 “正文” 样式，其次选最常用的非标题段落样式
    body_style = (body_style_guess or "").strip() or None
    if not body_style:
        body_style = _pick_most_common_style(style_count, lambda n: "正文" in n)
    if not body_style:
        body_style = _pick_most_common_style(style_count, lambda n: _match_heading_level(n) is None)

    # table：尝试从 style_count 里找“表格/Table”，否则为空（table block 本身没有 style_name）
    table_style = _pick_most_common_style(style_count, lambda n: ("表格" in n) or ("table" in (n or "").lower()))
    if not has_table:
        table_style = None

    # list：统计有 num_id 的段落样式（可选）
    list_style_count: Dict[str, int] = {}
    for b in extract_result.blocks:
        if b.type != BlockType.PARAGRAPH:
            continue
        if b.num_id is None:
            continue
        if not b.style_name:
            continue
        list_style_count[b.style_name] = list_style_count.get(b.style_name, 0) + 1
    list_style = None
    if list_style_count:
        list_style = max(list_style_count.items(), key=lambda x: x[1])[0]

    # numbering_candidate：只有 numId 存在时才给候选（避免 None/空壳）
    numbering_candidate: Optional[Dict[str, Any]] = None
    num_stats = extract_result.numbering_stats or {}
    if num_stats.get("has_numbering"):
        nc = num_stats.get("numbering_count") or {}
        lc = num_stats.get("level_count") or {}
        if nc:
            num_id = max(nc.items(), key=lambda x: x[1])[0]
            ilvl = max(lc.items(), key=lambda x: x[1])[0] if lc else 0
            numbering_candidate = {"numId": num_id, "ilvl": ilvl}

    # 其余页面/目录样式：可以为空；这里给一组稳定默认值，保证预览可用
    hints = StyleHints(
        heading1_style=heading_styles[1],
        heading2_style=heading_styles[2],
        heading3_style=heading_styles[3],
        heading4_style=heading_styles[4],
        heading5_style=heading_styles[5],
        body_style=body_style,
        table_style=table_style,
        numbering_candidate=numbering_candidate,
        list_style=list_style,
        page_background="#ffffff",
        font_family=None,
        font_size=None,
        line_height=None,
        toc_indent_1="0px",
        toc_indent_2="20px",
        toc_indent_3="40px",
        toc_indent_4="60px",
    )
    return hints


