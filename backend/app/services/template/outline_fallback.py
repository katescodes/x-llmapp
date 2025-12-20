"""
Deterministic outline fallback builder.

When LLM output is empty/invalid, we still want a usable outline for frontend preview.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from app.services.template.docx_extractor import DocxExtractResult, BlockType
from app.services.template.template_spec import OutlineNode


_RE_TRAILING_PAGE_NO = re.compile(r"\s+\d+\s*$")


def _clean_title(text: str) -> str:
    s = (text or "").strip()
    s = re.sub(r"\s+", " ", s)
    # 轻度去掉末尾页码（目录行在 extractor 侧应已打 TOC tag，这里再保险）
    s = _RE_TRAILING_PAGE_NO.sub("", s).strip()
    return s


def build_outline_fallback(extract_result: DocxExtractResult) -> List[OutlineNode]:
    """
    从“正文里的真实标题段落”自动构建 outline：
    - 仅使用：PARAGRAPH && tag=="NORMAL" && outline_level in [0..4]
    - 跳过 TOC/说明/色卡等噪声块（靠 tag）
    """
    roots: List[OutlineNode] = []
    stack: List[Tuple[int, OutlineNode]] = []  # (level, node), level is 1-based
    order_counter: Dict[Tuple[Optional[str], int], int] = {}  # (parent_id, level) -> next order

    blocks = (extract_result.blocks or [])
    for b in blocks:
        if b.type != BlockType.PARAGRAPH:
            continue
        if getattr(b, "tag", None) != "NORMAL":
            continue
        if b.outline_level is None:
            continue
        if not (0 <= int(b.outline_level) <= 4):
            continue

        level = int(b.outline_level) + 1  # 1-based
        title = _clean_title(b.text)
        if not title:
            continue

        # 找到 parent
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent_id = stack[-1][1].id if stack else None

        key = (parent_id, level)
        order_counter[key] = order_counter.get(key, 0) + 1
        order_no = order_counter[key]

        node = OutlineNode(
            id=f"fb-{b.id}",
            title=title,
            level=level,
            order_no=order_no,
            required=True,
            style_hint=b.style_name,
            parent_id=parent_id,
            children=[],
            metadata={"source": "deterministic_fallback", "block_id": b.id},
        )

        if stack:
            stack[-1][1].children.append(node)
        else:
            roots.append(node)
        stack.append((level, node))

    # 最后兜底：确保前端预览不为空
    if not roots:
        roots = [
            OutlineNode(
                id="fb-root",
                title="正文",
                level=1,
                order_no=1,
                required=True,
                style_hint=None,
                parent_id=None,
                children=[],
                metadata={"source": "deterministic_fallback", "reason": "no_heading_detected"},
            )
        ]

    return roots


