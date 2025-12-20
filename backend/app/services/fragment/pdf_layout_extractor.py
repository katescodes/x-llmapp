"""
PDF 版面抽取器 - 正确顺序 + 去目录/页眉页脚 + 表格识别
"""
import re
from typing import Any, Dict, List, Tuple

def _norm(s: str) -> str:
    x = (s or "").strip().lower()
    x = re.sub(r"[\u3000\s]+", "", x)
    x = re.sub(r"[：:。．\.,，;；\(\)（）\[\]【】《》<>·•]", "", x)
    return x

DOT_LEADER = re.compile(r"[.…\.]{2,}\s*\d+\s*$")
TOC_LIKE_1 = re.compile(r"^\s*\d+(?:\.\d+)*\s+.+\s+\d+\s*$")
TOC_LIKE_2 = re.compile(r"^\s*(?:[一二三四五六七八九十]+|\d+)[、.．]\s+.+\s+\d+\s*$")

def _is_toc_line(t: str) -> bool:
    s = (t or "").strip()
    if not s:
        return False
    if s in ("目录", "目 录", "Contents", "CONTENTS"):
        return True
    if DOT_LEADER.search(s):
        return True
    if TOC_LIKE_1.match(s) or TOC_LIKE_2.match(s):
        return True
    return False

def extract_pdf_items(pdf_path: str, max_pages: int = 500) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    输出 items（兼容 blocks_json）：
    - paragraph: {type:'paragraph', bodyIndex, pageNo, bbox, text, fontSize, bold, center}
    - table: {type:'table', bodyIndex, pageNo, bbox, tableData}
    """
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    pages = min(len(doc), max_pages)

    # 1) 先抽"行级文本"，并统计页眉/页脚重复
    header_cnt, footer_cnt = {}, {}
    per_page_lines: List[List[Dict[str, Any]]] = []
    toc_pages = set()
    raw_line_cnt = 0

    for pno in range(pages):
        page = doc[pno]
        height = float(page.rect.height)
        top_y = height * 0.08
        bot_y = height * 0.92

        d = page.get_text("rawdict")
        lines: List[Dict[str, Any]] = []

        for b in d.get("blocks", []):
            if b.get("type") != 0:
                continue
            for ln in b.get("lines", []) or []:
                spans = ln.get("spans", []) or []
                txt = "".join((sp.get("text") or "") for sp in spans).strip()
                if not txt:
                    continue
                raw_line_cnt += 1
                bbox = ln.get("bbox") or b.get("bbox")
                if not bbox:
                    continue
                x0, y0, x1, y1 = map(float, bbox)

                max_size = 0.0
                bold = False
                for sp in spans:
                    max_size = max(max_size, float(sp.get("size") or 0))
                    flags = int(sp.get("flags") or 0)
                    if flags & 2:
                        bold = True

                center = abs((x0 + x1) / 2.0 - float(page.rect.width) / 2.0) <= float(page.rect.width) * 0.08

                lines.append({
                    "pageNo": pno,
                    "bbox": [x0, y0, x1, y1],
                    "x0": x0, "y0": y0,
                    "text": txt,
                    "fontSize": max_size,
                    "bold": bold,
                    "center": center,
                })

        # 目录页判定：TOC 行占比高
        toc_hits = sum(1 for ln in lines if _is_toc_line(ln["text"]))
        if lines and toc_hits >= 8 and (toc_hits / max(1, len(lines))) >= 0.35:
            toc_pages.add(pno)

        top_lines = [ln for ln in lines if ln["bbox"][1] <= top_y]
        bot_lines = [ln for ln in lines if ln["bbox"][3] >= bot_y]

        for ln in top_lines[:3]:
            k = _norm(ln["text"])
            if k:
                header_cnt[k] = header_cnt.get(k, 0) + 1
        for ln in bot_lines[-3:]:
            k = _norm(ln["text"])
            if k:
                footer_cnt[k] = footer_cnt.get(k, 0) + 1

        per_page_lines.append(lines)

    min_rep = max(3, int(pages * 0.30))
    header_set = {k for k, c in header_cnt.items() if c >= min_rep}
    footer_set = {k for k, c in footer_cnt.items() if c >= min_rep}

    # 2) 表格：用 PyMuPDF 的 find_tables（有就用；没有也不影响）
    table_items: List[Dict[str, Any]] = []
    for pno in range(pages):
        if pno in toc_pages:
            continue
        page = doc[pno]
        try:
            tabs = page.find_tables()
            for t in (tabs.tables or []):
                bbox = list(map(float, t.bbox))
                tableData = []
                for row in t.extract():
                    tableData.append([(c or "").strip() for c in row])
                table_items.append({
                    "type": "table",
                    "pageNo": pno,
                    "bbox": bbox,
                    "tableData": tableData,
                })
        except Exception:
            continue

    # 3) 去噪并按阅读顺序输出 paragraph/table 混排
    kept: List[Dict[str, Any]] = []
    removed_toc_pages_lines = removed_hf = removed_toc_lines = 0

    for pno, lines in enumerate(per_page_lines):
        if pno in toc_pages:
            removed_toc_pages_lines += len(lines)
            continue

        for ln in lines:
            t = (ln["text"] or "").strip()
            if not t:
                continue
            n = _norm(t)

            if n in header_set or n in footer_set:
                removed_hf += 1
                continue
            if _is_toc_line(t):
                removed_toc_lines += 1
                continue
            if len(t) <= 3 and t.isdigit():
                continue

            kept.append(ln)

    # 先合并"行→段落"（减少碎片，提升标题识别稳定性）
    kept.sort(key=lambda x: (int(x["pageNo"]), float(x["y0"]), float(x["x0"])))
    paragraphs: List[Dict[str, Any]] = []
    cur = None

    def flush():
        nonlocal cur
        if cur:
            cur["text"] = cur["text"].strip()
            if cur["text"]:
                paragraphs.append(cur)
        cur = None

    for ln in kept:
        txt = (ln["text"] or "").strip()
        if not txt:
            continue
        if cur is None:
            cur = dict(ln)
            continue

        # 同页、接近位置、左对齐相近 -> 认为同一段
        same_page = int(ln["pageNo"]) == int(cur["pageNo"])
        gap = float(ln["bbox"][1]) - float(cur["bbox"][3])
        left_close = abs(float(ln["bbox"][0]) - float(cur["bbox"][0])) <= 12.0
        font_close = abs(float(ln["fontSize"]) - float(cur["fontSize"])) <= 1.0

        if same_page and gap >= 0 and gap <= 6.0 and left_close and font_close and (not ln["center"]):
            cur["text"] += "\n" + txt
            # expand bbox
            cur["bbox"][2] = max(cur["bbox"][2], ln["bbox"][2])
            cur["bbox"][3] = max(cur["bbox"][3], ln["bbox"][3])
            cur["bold"] = cur["bold"] or ln["bold"]
        else:
            flush()
            cur = dict(ln)

    flush()

    # 4) 混排：把表格插入到 paragraph 流里（按 pageNo, y0）
    merged: List[Dict[str, Any]] = []
    # 先把 paragraph 转 item
    for p in paragraphs:
        merged.append({
            "type": "paragraph",
            "pageNo": int(p["pageNo"]),
            "bbox": p["bbox"],
            "text": p["text"],
            "fontSize": float(p.get("fontSize") or 0),
            "bold": bool(p.get("bold")),
            "center": bool(p.get("center")),
        })
    # 表格补进来
    for t in table_items:
        merged.append({
            "type": "table",
            "pageNo": int(t["pageNo"]),
            "bbox": t["bbox"],
            "tableData": t["tableData"],
        })

    merged.sort(key=lambda x: (int(x["pageNo"]), float(x["bbox"][1]), float(x["bbox"][0])))

    items: List[Dict[str, Any]] = []
    for i, it in enumerate(merged):
        it2 = dict(it)
        it2["bodyIndex"] = i
        items.append(it2)

    diag = {
        "pages": pages,
        "raw_line_cnt": raw_line_cnt,
        "toc_pages": sorted(list(toc_pages))[:30],
        "min_repeat_pages": min_rep,
        "kept_items": len(items),
        "removed_toc_pages_lines": removed_toc_pages_lines,
        "removed_hf": removed_hf,
        "removed_toc_lines": removed_toc_lines,
        "tables_found": len(table_items),
    }
    return items, diag

