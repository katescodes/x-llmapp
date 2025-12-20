"""
通用的 docx 样式/层级推断工具
用于避免直接访问 python-docx 的 oxml 属性（某些模板会触发 AttributeError）
"""

from __future__ import annotations

import re
from typing import Optional

from docx.oxml.ns import nsmap

# 兼容：标题 1 / +标题1 / +标题 1 / ＋标题1
_RE_HEADING_ZH = re.compile(r"(?:[\+＋]\s*)?标题\s*([1-9])")
_RE_HEADING_EN = re.compile(r"Heading\s*([1-9])", re.I)


def guess_heading_level(paragraph) -> Optional[int]:
    """
    稳健推断段落标题级别：返回 1..9 或 None

    1) 优先从段落 style.name / base_style 链推断
       兼容：+标题1~+标题5（以及 base_style 指向 Heading 1..5）
    2) 兜底：从段落 XML 里找 w:outlineLvl（0-based），再转 1-based
    """
    # 1) style.name / base_style
    try:
        s = getattr(paragraph, "style", None)
        for _ in range(10):
            if not s:
                break
            name = getattr(s, "name", "") or ""
            m = _RE_HEADING_ZH.search(name)
            if m:
                return int(m.group(1))
            m = _RE_HEADING_EN.search(name)
            if m:
                return int(m.group(1))
            s = getattr(s, "base_style", None)
    except Exception:
        pass

    # 2) XML: w:outlineLvl/@w:val (0-based)
    try:
        p = getattr(paragraph, "_p", None) or getattr(paragraph, "_element", None)
        if p is not None:
            vals = p.xpath("./w:pPr/w:outlineLvl/@w:val", namespaces=nsmap)
            if vals:
                return int(vals[0]) + 1
    except Exception:
        pass

    return None


