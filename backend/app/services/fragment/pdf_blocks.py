import re
from typing import Any, Dict, List, Tuple

def _guess_heading_level_from_text(t: str) -> int | None:
    s = (t or "").strip()
    if not s:
        return None

    # 大章/附件
    if re.match(r"^\s*(第[一二三四五六七八九十百千0-9]+[章节部分卷]|附件[一二三四五六七八九十0-9]+)\b", s):
        return 1

    # 一、 / 1、 / 1.1 / （1）
    if re.match(r"^\s*([一二三四五六七八九十]+|\d+(?:\.\d+)*)\s*[、.．]\s*\S+", s):
        return 2
    if re.match(r"^\s*[（(]\s*\d+\s*[)）]\s*\S+", s):
        return 3

    # 短标题启发式（表/函/书/格式/样表）
    if len(s) <= 24 and any(k in s for k in ["表", "函", "书", "格式", "样表", "范本", "授权", "投标"]):
        return 3

    return None

def extract_pdf_body_items(pdf_path: str, max_pages: int = 300) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    从 PDF 抽取"可定位"的 body_items（按版面块排序）：
    body_items: [{bodyIndex,type,text,styleName,pageNo}, ...]
    diag: {pages, blocks, empty_pages}
    """
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    pages = min(len(doc), max_pages)

    raw_blocks: List[Tuple[float, float, int, str]] = []
    empty_pages = 0

    for pno in range(pages):
        page = doc[pno]
        blocks = page.get_text("blocks")  # (x0,y0,x1,y1,text,block_no,block_type,...)
        if not blocks:
            empty_pages += 1
            continue
        for b in blocks:
            x0, y0, x1, y1, text = b[0], b[1], b[2], b[3], b[4]
            if not text:
                continue
            # 保留换行（范本常有"致：xxx"这种格式）
            lines = [ln.strip() for ln in str(text).splitlines() if ln.strip()]
            if not lines:
                continue
            txt = "\n".join(lines).strip()
            if not txt:
                continue
            raw_blocks.append((y0, x0, pno, txt))

    # 版面顺序：先 y 再 x
    raw_blocks.sort(key=lambda x: (x[0], x[1]))

    body_items: List[Dict[str, Any]] = []
    idx = 0
    for (y0, x0, pno, txt) in raw_blocks:
        body_items.append({
            "bodyIndex": idx,
            "type": "paragraph",
            "styleName": None,
            "text": txt,
            "pageNo": int(pno),
            "headingGuess": _guess_heading_level_from_text(txt),
        })
        idx += 1

    diag = {
        "pages": pages,
        "blocks": len(body_items),
        "empty_pages": empty_pages,
    }
    return body_items, diag

