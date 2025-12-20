"""
Export-time style applier:
- Ensure paragraph styles exist for spec.style_hints (AI_* fallback)
- Create missing styles from spec.style_rules so export can always apply formatting
"""

from __future__ import annotations

from typing import Optional, Dict, Any

from docx.document import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

from app.services.template.template_spec import TemplateSpec


def _has_style(doc: Document, name: Optional[str]) -> bool:
    if not name:
        return False
    try:
        _ = doc.styles[name]
        return True
    except Exception:
        return False


def _ensure_paragraph_style(doc: Document, name: str):
    try:
        return doc.styles[name]
    except Exception:
        return doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)


def _apply_rule_to_style(style, rule: Dict[str, Any]) -> None:
    font = style.font
    pf = style.paragraph_format

    ff = rule.get("font_family")
    if isinstance(ff, str) and ff.strip():
        try:
            font.name = ff.strip()
        except Exception:
            pass

    fs = rule.get("font_size_pt")
    if isinstance(fs, (int, float)) and fs > 0:
        try:
            font.size = Pt(float(fs))
        except Exception:
            pass

    if isinstance(rule.get("bold"), bool):
        try:
            font.bold = bool(rule.get("bold"))
        except Exception:
            pass

    color = rule.get("color")
    if isinstance(color, str) and color.strip().startswith("#") and len(color.strip()) == 7:
        try:
            hexv = color.strip().lstrip("#")
            font.color.rgb = RGBColor.from_string(hexv.upper())
        except Exception:
            pass

    alignment = rule.get("alignment")
    if isinstance(alignment, str):
        m = {
            "left": WD_ALIGN_PARAGRAPH.LEFT,
            "center": WD_ALIGN_PARAGRAPH.CENTER,
            "right": WD_ALIGN_PARAGRAPH.RIGHT,
            "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
        }
        if alignment in m:
            try:
                pf.alignment = m[alignment]
            except Exception:
                pass

    ls = rule.get("line_spacing")
    if ls is not None:
        try:
            if isinstance(ls, (int, float)):
                pf.line_spacing = float(ls)
            elif isinstance(ls, str):
                s = ls.strip().lower()
                if s.endswith("pt"):
                    pf.line_spacing = Pt(float(s.replace("pt", "").strip()))
                else:
                    pf.line_spacing = float(s)
        except Exception:
            pass

    # first line indent: chars -> pt (粗略：chars * font_size_pt；缺省 12pt/char)
    flc = rule.get("first_line_indent_chars")
    if isinstance(flc, int) and flc > 0:
        try:
            fspt = rule.get("font_size_pt")
            per_char = float(fspt) if isinstance(fspt, (int, float)) and fspt > 0 else 12.0
            pf.first_line_indent = Pt(per_char * float(flc))
        except Exception:
            pass

    sb = rule.get("space_before_pt")
    if isinstance(sb, (int, float)) and sb >= 0:
        try:
            pf.space_before = Pt(float(sb))
        except Exception:
            pass

    sa = rule.get("space_after_pt")
    if isinstance(sa, (int, float)) and sa >= 0:
        try:
            pf.space_after = Pt(float(sa))
        except Exception:
            pass


def ensure_styles_from_spec(doc: Document, spec: TemplateSpec) -> None:
    """
    Ensure spec.style_hints.* are usable in this doc:
    - If missing/invalid style name, create AI_* style based on spec.style_rules and rewrite hints.
    """
    hints = getattr(spec, "style_hints", None)
    rules = getattr(spec, "style_rules", None) or []

    # map target -> rule dict
    rule_by_target: Dict[str, Dict[str, Any]] = {}
    for r in rules:
        if isinstance(r, dict):
            t = r.get("target")
            if isinstance(t, str) and t:
                rule_by_target[t] = r
        else:
            # dataclass StyleRule
            try:
                t = getattr(r, "target", None)
                if isinstance(t, str) and t:
                    rule_by_target[t] = {
                        "target": t,
                        "font_family": getattr(r, "font_family", None),
                        "font_size_pt": getattr(r, "font_size_pt", None),
                        "bold": getattr(r, "bold", None),
                        "color": getattr(r, "color", None),
                        "line_spacing": getattr(r, "line_spacing", None),
                        "first_line_indent_chars": getattr(r, "first_line_indent_chars", None),
                        "alignment": getattr(r, "alignment", None),
                        "space_before_pt": getattr(r, "space_before_pt", None),
                        "space_after_pt": getattr(r, "space_after_pt", None),
                    }
            except Exception:
                continue

    def _ensure_one(attr: str, ai_name: str, target: str):
        if not hints:
            return
        cur = getattr(hints, attr, None)
        if _has_style(doc, cur):
            return

        # create AI_* if needed
        style = _ensure_paragraph_style(doc, ai_name)
        rule = rule_by_target.get(target) or {}
        _apply_rule_to_style(style, rule)
        setattr(hints, attr, ai_name)

    _ensure_one("heading1_style", "AI_H1", "heading1")
    _ensure_one("heading2_style", "AI_H2", "heading2")
    _ensure_one("heading3_style", "AI_H3", "heading3")
    _ensure_one("body_style", "AI_BODY", "body")


