"""
PDF 范本检测器 - 先定位区域，再用"标题候选"切片
"""
import re
from typing import Any, Dict, List, Tuple
from rapidfuzz import fuzz

# 标题编号模式（PDF 常见）
H1 = re.compile(r"^\s*[一二三四五六七八九十]+[、.．]\s*\S+")
H2 = re.compile(r"^\s*\d+(?:\.\d+)*[、.．]\s*\S+")
H3 = re.compile(r"^\s*[（(]\s*\d+\s*[)）]\s*\S+")

# 范本关键词（只用于"标题候选"与区域打分，不依赖固定章号）
SAMPLE_KW = [
    "投标函","响应函","报价","报价一览表","开标一览表","分项报价","报价表","报价清单",
    "授权委托书","授权书","法定代表人","身份证明",
    "偏离","商务响应","技术响应","承诺函","声明","资格审查","资质","营业执照","样表","范本","格式"
]

REGION_KW = ["投标文件格式","响应文件格式","样表","范本","格式","附件"]

def _has_kw(s: str, kws: List[str]) -> bool:
    t = (s or "").strip()
    return any(k in t for k in kws)

def _title_score(it: Dict[str, Any], font_p85: float) -> float:
    if it.get("type") != "paragraph":
        return 0.0
    txt = (it.get("text") or "").strip()
    if not txt:
        return 0.0
    fs = float(it.get("fontSize") or 0)
    bold = bool(it.get("bold"))
    center = bool(it.get("center"))

    score = 0.0
    if H1.match(txt) or H2.match(txt) or H3.match(txt):
        score += 5.0
    if _has_kw(txt, SAMPLE_KW):
        score += 4.0
    if fs >= font_p85:
        score += 2.5
    if bold:
        score += 1.2
    if center and len(txt) <= 30:
        score += 1.0

    # 很长的行更像正文，扣分
    if len(txt) >= 80:
        score -= 1.0

    return score

def locate_region(items: List[Dict[str, Any]], window_pages: int = 12) -> Tuple[int, int, Dict[str, Any]]:
    if not items:
        return 0, 0, {"reason": "empty"}

    # page -> indices
    page_to_idxs: Dict[int, List[int]] = {}
    for it in items:
        page_to_idxs.setdefault(int(it.get("pageNo") or 0), []).append(int(it["bodyIndex"]))
    pages = sorted(page_to_idxs.keys())
    if not pages:
        return 0, len(items), {"reason": "no_pages"}

    # 每页得分：区域词 + 标题候选密度 + 表格数
    page_score: Dict[int, float] = {}
    for p in pages:
        idxs = page_to_idxs[p]
        sc = 0.0
        for i in idxs:
            it = items[i]
            if it.get("type") == "table":
                sc += 1.5
                continue
            txt = (it.get("text") or "").strip()
            if not txt:
                continue
            if _has_kw(txt, REGION_KW):
                sc += 6.0
            if _has_kw(txt, SAMPLE_KW):
                sc += 2.5
            if H1.match(txt) or H2.match(txt) or H3.match(txt):
                sc += 2.0
        page_score[p] = sc

    best = (pages[0], pages[0], -1.0)
    for i in range(len(pages)):
        for j in range(i, min(len(pages), i + window_pages)):
            s = sum(page_score.get(pages[k], 0.0) for k in range(i, j + 1))
            if s > best[2]:
                best = (pages[i], pages[j], s)

    p0, p1, best_score = best
    start = min(page_to_idxs[p0])
    end = max(page_to_idxs[p1]) + 1
    end = min(end, len(items))
    diag = {"p_start": p0, "p_end": p1, "best_score": best_score,
            "top_pages": sorted([(p, page_score[p]) for p in pages], key=lambda x: x[1], reverse=True)[:10]}
    return start, end, diag

def detect_pdf_fragments(items: List[Dict[str, Any]], title_normalize_fn, title_to_type_fn) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    输出 fragments:
    {title,norm_key,start_body_index,end_body_index,confidence,strategy}
    """
    # font percentile 85（用于判断"看起来像标题"）
    font_sizes = [float(it.get("fontSize") or 0) for it in items if it.get("type") == "paragraph" and (it.get("text") or "").strip()]
    font_sizes.sort()
    font_p85 = font_sizes[int(len(font_sizes) * 0.85)] if font_sizes else 12.0

    r_start, r_end, region_diag = locate_region(items, window_pages=12)
    seg = items[r_start:r_end]

    # 1) 找标题候选（强约束：要么编号/要么包含范本关键词/要么能映射到已知类型）
    heads = []
    for it in seg:
        if it.get("type") != "paragraph":
            continue
        txt = (it.get("text") or "").strip()
        if not txt:
            continue
        sc = _title_score(it, font_p85)
        if sc < 6.5:
            continue

        title = txt.split("\n")[0].strip()  # 标题一般第一行
        norm = title_normalize_fn(title)
        ftype = title_to_type_fn(norm) if norm else None

        # 强约束过滤：未知且没关键词，不要
        if (not ftype) and (not _has_kw(title, SAMPLE_KW)):
            continue

        heads.append((int(it["bodyIndex"]), title, ftype, sc))

    # 2) 去重（标题相似只留一个，避免重复投标函/授权书）
    heads_sorted = sorted(heads, key=lambda x: x[0])
    kept = []
    for (idx, title, ftype, sc) in heads_sorted:
        dup = False
        for (_, t2, _, _) in kept:
            if fuzz.token_set_ratio(title, t2) >= 92:
                dup = True
                break
        if not dup:
            kept.append((idx, title, ftype, sc))

    # 3) 切片（到下一个标题为止；同时限制最大跨度，防止误扩展）
    fragments = []
    for i, (sidx, title, ftype, sc) in enumerate(kept):
        eidx = kept[i+1][0] - 1 if i + 1 < len(kept) else (r_end - 1)
        eidx = max(eidx, sidx)

        # 限制最大跨页：最多 5 页
        sp = items[sidx].get("pageNo")
        ep = items[eidx].get("pageNo")
        if isinstance(sp, int) and isinstance(ep, int) and (ep - sp) > 5:
            # 往后收缩到 sidx 后 5 页内
            max_page = sp + 5
            while eidx > sidx and int(items[eidx].get("pageNo") or 0) > max_page:
                eidx -= 1

        norm_key = str(ftype) if ftype else f"unknown:{title}"
        fragments.append({
            "norm_key": norm_key,
            "title": title,
            "start_body_index": int(sidx),
            "end_body_index": int(eidx),
            "confidence": min(0.95, 0.60 + sc / 20.0),
            "strategy": "pdf_layout_titlecut",
        })

    diag = {
        "font_p85": font_p85,
        "region": {"start": r_start, "end": r_end, "diag": region_diag},
        "heads_raw": len(heads),
        "heads_kept": len(kept),
        "fragments": len(fragments),
    }
    return fragments, diag

