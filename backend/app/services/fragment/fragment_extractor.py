"""
TenderSampleFragmentExtractor - 招标书范本片段抽取器
从招标书中抽取投标文件格式范本（投标函、授权书、报价表等）
"""
import os
import logging
import json
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from app.services.dao.tender_dao import TenderDAO
from app.services.fragment.fragment_matcher import FragmentTitleMatcher
from app.services.fragment.fragment_type import FragmentType
from docx import Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.text.paragraph import Paragraph
from docx.table import Table
from app.services.docx_style_utils import guess_heading_level

from app.services.fragment.llm_span_locator import TenderSampleSpanLocator, TenderSampleSpan
from app.services.fragment.pdf_blocks import extract_pdf_body_items
from app.services.fragment.pdf_layout_extractor import extract_pdf_items
from app.services.fragment.pdf_sample_detector import detect_pdf_fragments


class TenderSampleFragmentExtractor:
    """招标书范本片段抽取器"""
    
    def __init__(self, dao: TenderDAO):
        self.dao = dao
        self.matcher = FragmentTitleMatcher()
        self.locator = TenderSampleSpanLocator()
    
    # ==================== body 扫描（段落/表格） ====================
    def _para_style_name(self, para: Paragraph) -> str:
        try:
            return (para.style.name or "") if para.style else ""
        except Exception:
            return ""
    
    def _table_style_name(self, tbl: Table) -> str:
        try:
            return (tbl.style.name or "") if getattr(tbl, "style", None) else ""
        except Exception:
            return ""
    
    def _table_text_preview(self, tbl: Table, max_rows: int = 8, max_cells: int = 6, max_chars: int = 200) -> str:
        """
        表格文本预览：
        - 取前 max_rows 行
        - 每行取前 max_cells 个单元格
        - 单元格内取所有段落拼接
        """
        rows = []
        try:
            for r in tbl.rows[:max_rows]:
                cells_txt = []
                for c in r.cells[:max_cells]:
                    parts = []
                    for p in c.paragraphs:
                        t = (p.text or "").strip()
                        if t:
                            parts.append(t)
                    ct = " ".join(parts).strip()
                    if ct:
                        cells_txt.append(ct)
                rt = " | ".join(cells_txt).strip()
                if rt:
                    rows.append(rt)
        except Exception:
            pass
        txt = "\n".join(rows).strip()
        if len(txt) > max_chars:
            txt = txt[:max_chars]
        return txt

    def _normalize_anchor_text(self, s: str) -> str:
        """
        用于关键词匹配的归一化：
        - 去空白
        - 去常见标点
        - 小写（对英文）
        """
        import re

        x = (s or "").strip().lower()
        x = re.sub(r"[\u3000\s]+", "", x)
        x = re.sub(r"[：:。．\.,，;；\(\)（）\[\]【】《》<>]", "", x)
        return x

    def _extract_body_items(self, doc):
        """
        以 doc.element.body 的真实索引为 bodyIndex（与 LLM span 索引体系一致）
        返回结构：[{bodyIndex, type, text/styleName, tableData?}, ...]
        """
        items = []
        body_elements = list(doc.element.body)

        for idx, el in enumerate(body_elements):
            if isinstance(el, CT_P):
                p = Paragraph(el, doc)
                text = (p.text or "").strip()
                items.append({
                    "bodyIndex": idx,
                    "type": "paragraph",
                    "styleName": self._para_style_name(p),
                    "text": text,
                })
            elif isinstance(el, CT_Tbl):
                t = Table(el, doc)
                rows = []
                try:
                    for r in t.rows:
                        rows.append([(c.text or "").strip() for c in r.cells])
                except Exception:
                    rows = []
                items.append({
                    "bodyIndex": idx,
                    "type": "table",
                    "styleName": self._table_style_name(t),
                    "tableData": rows,
                    "text": self._table_text_preview(t, max_rows=8, max_cells=6, max_chars=200),
                })

        return items
    
    def _identify_fragments_by_rules(self, body_items):
        import re

        # 定位"投标文件格式"区域（不依赖具体章号）
        def locate_format_section(items):
            # 目录条目识别（避免把目录里的"投标文件格式"当正文）
            def is_toc_line(t: str) -> bool:
                t = (t or "").strip()
                if not t:
                    return False
                if "（页码）" in t:
                    return True
                if ("…" in t or "...." in t) and re.search(r"\d+\s*$", t):
                    return True
                return False

            # 大标题（任意章号）：第X章/第X节/第X部分/第X卷/附件X
            major_re = re.compile(r"^\s*(第[一二三四五六七八九十百千0-9]+[章节部分卷]|附件[一二三四五六七八九十0-9]*)")

            # 范本区关键词（起点候选）
            # ✅ 扩展关键词，提高识别率
            start_kw = [
                "投标文件格式", "响应文件格式", "投标文件样表",
                "样表", "格式", "范本", "表格", "附件",
                "投标文件", "响应文件", "投标书", "标书格式",
                "投标资料", "报价文件", "商务标", "技术标",
                "资格文件", "投标材料"
            ]

            # 范本区的典型标题/内容关键词（用于打分）
            # ✅ 扩展关键词，涵盖更多范本类型
            target_kw = [
                "开标一览表", "投标函", "报价", "货物报价", "工程量清单",
                "法定代表人", "授权委托书", "授权书", "委托书",
                "商务", "合同条款", "技术", "偏离", "响应",
                "资质证书", "营业执照", "证书", "证明",
                "投标保证金", "保证金", "履约保证",
                "项目组织", "业绩", "资格", "声明函",
                "商务条款", "技术方案", "施工方案", "实施方案",
                "设备清单", "材料清单", "人员配备", "组织架构"
            ]

            # 表单标题行（"一、xx / 1、xx / (1)xx / 1.1 xx"）
            head_re = re.compile(r"^\s*((?:[一二三四五六七八九十]+)|(?:\d+(?:\.\d+)*))\s*[、.．]\s*\S+")
            head_re2 = re.compile(r"^\s*[（(]\s*\d+\s*[)）]\s*\S+")

            def score_candidate(si: int):
                win = items[si: min(len(items), si + 280)]
                head_cnt = 0
                kw_cnt = 0
                tbl_cnt = 0
                for it in win:
                    if it.get("type") == "table":
                        tbl_cnt += 1
                        continue
                    if it.get("type") != "paragraph":
                        continue
                    t = (it.get("text") or "").strip()
                    if not t or is_toc_line(t):
                        continue
                    if head_re.match(t) or head_re2.match(t):
                        head_cnt += 1
                    if any(k in t for k in target_kw):
                        kw_cnt += 1

                # 起点本身是大标题，略加分（但不依赖具体章号）
                start_txt = (items[si].get("text") or "")
                major_bonus = 2 if major_re.match(start_txt.strip()) else 0

                # 范本区通常表格更多，适当加权
                return head_cnt * 3 + kw_cnt * 2 + min(tbl_cnt, 20) + major_bonus, (head_cnt, kw_cnt, tbl_cnt, major_bonus)

            # 1) 收集候选起点（所有包含 start_kw 的段落）
            candidates = []
            for i, it in enumerate(items):
                if it.get("type") != "paragraph":
                    continue
                t = (it.get("text") or "").strip()
                if not t or is_toc_line(t):
                    continue
                if any(k in t for k in start_kw):
                    candidates.append(i)

            # 2) 选择最高分候选
            # ✅ 如果没有找到候选，则从第一个有范本关键词的地方开始
            if not candidates:
                # 兜底策略：查找任意包含范本关键词的位置
                for i, it in enumerate(items):
                    if it.get("type") != "paragraph":
                        continue
                    t = (it.get("text") or "").strip()
                    if not t or is_toc_line(t):
                        continue
                    # 只要包含任何范本相关词汇，就尝试作为起点
                    if any(k in t for k in target_kw):
                        candidates.append(i)
                        if len(candidates) >= 3:  # 找到3个候选就够了
                            break
            
            if not candidates:
                # 仍然没找到，使用整个文档
                return 0, len(items), {"reason": "no_candidates_fallback_to_full_doc"}


            best_i = candidates[0]
            best_score = -1
            best_detail = None
            for si in candidates:
                sc, detail = score_candidate(si)
                if sc > best_score:
                    best_score = sc
                    best_i = si
                    best_detail = detail

            start = best_i

            # 3) 结束点：找 start 之后第一个"同级大标题"（major_re），作为 end
            end = len(items)
            for j in range(start + 1, len(items)):
                it = items[j]
                if it.get("type") != "paragraph":
                    continue
                t = (it.get("text") or "").strip()
                if not t or is_toc_line(t):
                    continue
                if major_re.match(t):
                    end = j
                    break

            diag = {
                "candidates": len(candidates),
                "chosen_start": start,
                "chosen_end": end,
                "best_score": best_score,
                "best_detail": best_detail,  # (head_cnt, kw_cnt, tbl_cnt, major_bonus)
                "chosen_text": (items[start].get("text") or "")[:80],
            }
            return start, end, diag

        start, end, diag = locate_format_section(body_items)
        seg = body_items[start:end]
        # 把 diag 存下来用于接口诊断
        self._last_rules_diag = diag

        # 标题正则：支持 "一、xx / 1、xx / 1.xx / （1）xx"
        head_re = re.compile(r"^((?:[一二三四五六七八九十]+)|(?:\d+(?:\.\d+)*))\s*[、.．]\s*(.+)$")
        head_re2 = re.compile(r"^[（(]\s*(\d+)\s*[)）]\s*(.+)$")

        def clean_title(t: str) -> str:
            t = (t or "").strip()
            # 去掉点线页码
            t = re.sub(r"[.…·\.]{2,}\s*（?页码）?\s*$", "", t).strip()
            t = re.sub(r"（页码）$", "", t).strip()
            return t

        def is_heading_line(txt: str) -> bool:
            txt = (txt or "").strip()
            if not txt:
                return False
            if head_re.match(txt) or head_re2.match(txt):
                return True
            return False

        def heading_title(txt: str) -> str:
            txt = (txt or "").strip()
            m = head_re.match(txt)
            if m:
                return clean_title(m.group(2))
            m = head_re2.match(txt)
            if m:
                return clean_title(m.group(2))
            return ""

        # 在 seg 内找标题行（忽略"目录页码"那种行）
        heads = []
        for k, it in enumerate(seg):
            if it.get("type") != "paragraph":
                continue
            txt = (it.get("text") or "").strip()
            if not txt:
                continue
            # 忽略目录条目（含"（页码）"或点线）
            if "（页码）" in txt:
                continue
            if is_heading_line(txt):
                title = heading_title(txt)
                if title:
                    heads.append((k, title))

        # 没找到标题：兜底全局扫描（避免定位失败直接 0）
        if not heads:
            # norm_key 映射（与正常流程保持一致）
            norm_map = {
                "开标一览表": "bid_opening_form",
                "投标函": "bid_letter",
                "货物报价一览表": "price_list",
                "对商务要求及合同条款的响应": "biz_deviation",
                "对技术要求的响应": "tech_deviation",
                "货物服务技术方案": "tech_plan",
                "法定代表人身份证明及授权委托书": "power_of_attorney",
                "法定代表人授权书": "power_of_attorney",
                "法人授权书": "power_of_attorney",
                "授权委托书": "power_of_attorney",
                "各类资质证书及其他重要资料": "license_list",
                "资质证书": "license_list",
            }
            
            # 先收集所有匹配的索引
            matched_indices = []
            for i, it in enumerate(body_items):
                if it.get("type") != "paragraph":
                    continue
                txt = (it.get("text") or "").strip()
                if not txt:
                    continue
                # 关键字短行兜底
                if len(txt) <= 40 and any(k in txt for k in ["开标一览表", "投标函", "授权委托书", "法定代表人身份证明"]):
                    matched_indices.append(i)
            
            fallback_frags = []
            for idx, i in enumerate(matched_indices):
                it = body_items[i]
                txt = (it.get("text") or "").strip()
                title = clean_title(txt)
                
                # 匹配 norm_key
                nk = None
                for k, v in norm_map.items():
                    if k in title:
                        nk = v
                        break
                if not nk:
                    nk = f"unknown:{title}"
                
                start_body_idx = int(it.get("bodyIndex"))
                
                # end = next_start - 1（不要包含下一个标题）
                if idx + 1 < len(matched_indices):
                    next_i = matched_indices[idx + 1]
                    next_start_body_idx = int(body_items[next_i].get("bodyIndex"))
                    end_body_idx = max(start_body_idx, next_start_body_idx - 1)
                else:
                    # 最后一个，到文档结尾
                    end_body_idx = int(body_items[-1].get("bodyIndex")) if body_items else start_body_idx
                
                fallback_frags.append({
                    "norm_key": nk,
                    "title": title,
                    "start_body_index": start_body_idx,
                    "end_body_index": end_body_idx,
                    "confidence": 0.50,
                    "strategy": "rules_fallback_keyword",
                })

            # 若兜底仍为空，直接返回 []
            if not fallback_frags:
                # 给上层诊断用
                self._last_rules_diag["heads_found"] = 0
                return []
            
            # 更新诊断信息并返回兜底结果
            self._last_rules_diag["heads_found"] = len(fallback_frags)
            self._last_rules_diag["fallback_used"] = True
            return fallback_frags

        # norm_key 映射（含法人授权/授权委托书同义）
        norm_map = {
            "开标一览表": "bid_opening_form",
            "投标函": "bid_letter",
            "货物报价一览表": "price_list",
            "对商务要求及合同条款的响应": "biz_deviation",
            "对技术要求的响应": "tech_deviation",
            "货物服务技术方案": "tech_plan",
            "法定代表人身份证明及授权委托书": "power_of_attorney",
            "法定代表人授权书": "power_of_attorney",
            "法人授权书": "power_of_attorney",
            "授权委托书": "power_of_attorney",
            "各类资质证书及其他重要资料": "license_list",
            "资质证书": "license_list",
        }

        # section 最后一个可用 bodyIndex
        section_last_body_idx = int(seg[-1].get("bodyIndex")) if seg else 0

        fragments = []
        for idx, (pos, title) in enumerate(heads):
            start_item = seg[pos]
            start_body_idx = int(start_item.get("bodyIndex"))

            if idx + 1 < len(heads):
                next_pos = heads[idx + 1][0]
                next_start_body_idx = int(seg[next_pos].get("bodyIndex"))
                end_body_idx = max(start_body_idx, next_start_body_idx - 1)
            else:
                end_body_idx = max(start_body_idx, section_last_body_idx)

            nk = None
            for k, v in norm_map.items():
                if k in title:
                    nk = v
                    break
            if not nk:
                nk = f"unknown:{title}"

            fragments.append({
                "norm_key": nk,
                "title": title,
                "start_body_index": start_body_idx,
                "end_body_index": end_body_idx,
                "confidence": 0.70,
                "strategy": "rules_format_section_ranked",
            })

        # 更新诊断信息
        self._last_rules_diag["heads_found"] = len(heads)
        return fragments

    def _scan_body_elements(self, doc: Document) -> Tuple[List[Dict[str, Any]], List[int]]:
        """
        直接遍历 doc.element.body 的 CT_P / CT_Tbl，生成 elements_meta + anchors。
        elements_meta: {i,t,txt,style,h}
        anchors: 命中关键词的 body index 列表
        """
        body_elements = list(doc.element.body)
        elements_meta: List[Dict[str, Any]] = []
        anchors: List[int] = []

        # 候选锚点关键词（normalize 后匹配）
        keywords = [
            "投标函", "响应函", "格式", "样表", "范本", "授权委托书", "法定代表人授权",
            "开标一览表", "报价一览表", "报价表", "分项报价", "报价清单",
            "偏离表", "技术响应表", "商务响应表", "承诺函", "声明", "资格审查",
        ]
        # 区域起点提示
        appendix_patterns = [
            r"附录.*投标文件格式",
            r"投标文件格式",
            r"投标文件组成",
            r"响应文件格式",
            r"表格样表",
        ]

        import re
        appendix_re = re.compile("|".join(appendix_patterns))

        for idx, el in enumerate(body_elements):
            if isinstance(el, CT_P):
                para = Paragraph(el, doc)
                text = (para.text or "").strip()
                if not text:
                    continue
                style = self._para_style_name(para)
                lvl = guess_heading_level(para)
                meta = {
                    "i": idx,
                    "t": "P",
                    "txt": (text[:200] if len(text) > 200 else text),
                    "style": style,
                    "h": lvl,
                }
                elements_meta.append(meta)

                norm = self._normalize_anchor_text(text)
                if any(self._normalize_anchor_text(k) in norm for k in keywords) or appendix_re.search(norm):
                    anchors.append(idx)
            elif isinstance(el, CT_Tbl):
                tbl = Table(el, doc)
                text = self._table_text_preview(tbl, max_rows=8, max_cells=6, max_chars=200)
                if not text:
                    continue
                style = self._table_style_name(tbl)
                meta = {
                    "i": idx,
                    "t": "T",
                    "txt": text,
                    "style": style,
                    "h": None,
                }
                elements_meta.append(meta)

                norm = self._normalize_anchor_text(text)
                if any(self._normalize_anchor_text(k) in norm for k in keywords) or appendix_re.search(norm):
                    anchors.append(idx)
            else:
                continue

        # anchors 去重并排序
        anchors = sorted(set(int(i) for i in anchors))
        return elements_meta, anchors

    def _build_llm_window_indices(self, n_total: int, anchors: List[int], elements_meta: List[Dict[str, Any]]) -> List[int]:
        """
        构造 LLM 输入窗口（控制 token）：
        - 找到“附录/格式/样表”起点 idx0（没有就用第一个命中锚点-20）
        - 从 idx0 开始取最多 260 个元素
        - 对每个锚点覆盖 [i-5, i+25] 合并去重
        """
        import re

        def _is_appendix(meta: Dict[str, Any]) -> bool:
            txt = self._normalize_anchor_text(meta.get("txt") or "")
            return bool(re.search(r"(附录|投标文件格式|响应文件格式|投标文件组成|样表|范本)", txt))

        idx0: Optional[int] = None
        for m in elements_meta:
            if _is_appendix(m):
                idx0 = int(m["i"])
                break

        if idx0 is None:
            idx0 = max(0, (anchors[0] - 20)) if anchors else 0

        ordered: List[int] = []
        seen = set()

        def _push(i: int):
            if i < 0 or i >= n_total:
                return
            if i in seen:
                return
            seen.add(i)
            ordered.append(i)

        # 优先：锚点窗口
        for a in anchors:
            for i in range(max(0, a - 5), min(n_total, a + 26)):
                _push(i)

        # 再补：从 idx0 起连续窗口（用于让 LLM 看见“区域连续性”）
        for i in range(idx0, min(n_total, idx0 + 260)):
            _push(i)

        return ordered[:260]

    def _map_llm_type_to_internal(self, llm_type: str, title: str) -> str:
        """
        LLM 输出的 fragment_type（验收要求的枚举）映射为当前系统内部 FragmentType（用于后续 matcher/attacher）。
        若标题可被 matcher 命中，则以 matcher 为准。
        """
        title_norm = self.matcher.normalize(title or "")
        mt = self.matcher.match_type(title_norm) if title_norm else None
        if mt:
            return str(mt)

        t = (llm_type or "").strip().upper()
        mapping = {
            "BID_LETTER": str(FragmentType.BID_LETTER),
            "AUTHORIZATION": str(FragmentType.LEGAL_REP_AUTHORIZATION),
            "PRICE_SUMMARY": str(FragmentType.BID_OPENING_SCHEDULE),
            "PRICE_DETAIL": str(FragmentType.ITEMIZED_PRICE_SCHEDULE),
            "DEVIATION_BUSINESS": str(FragmentType.BIZ_DEVIATION_TABLE),
            "DEVIATION_TECH": str(FragmentType.TECH_DEVIATION_TABLE),
            "COMMITMENT": str(FragmentType.SERVICE_COMMITMENT),
            "QUALIFICATION": str(FragmentType.OTHER_FORMAT),
            "OTHER": str(FragmentType.OTHER_FORMAT),
        }
        return mapping.get(t, str(FragmentType.OTHER_FORMAT))
    
    def extract_and_upsert(
        self,
        project_id: str,
        tender_docx_path: str,
        file_key: Optional[str] = None,
        file_sha256: Optional[str] = None
    ) -> int:
        """
        从招标书中抽取范本片段并保存到数据库，返回 upserted_fragments 数量（永不抛异常）。
        
        Args:
            project_id: 项目ID
            tender_docx_path: 招标书 docx 文件路径
            file_key: 文件存储key（可选）
            file_sha256: 文件SHA256（可选）
        """
        try:
            summary = self.extract_and_upsert_summary(
                project_id=project_id,
                tender_docx_path=tender_docx_path,
                file_key=file_key,
                file_sha256=file_sha256,
            )
            return int((summary or {}).get("upserted_fragments") or 0)
        except Exception:
            return 0

    def extract_and_upsert_summary(
        self,
        project_id: str,
        tender_docx_path: str,
        file_key: Optional[str] = None,
        file_sha256: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        从招标书中抽取范本片段并保存到数据库，返回 summary（用于诊断/日志）。
        """
        logger = logging.getLogger(__name__)
        errors: List[str] = []

        # 1. 读取 docx 文件
        if not os.path.exists(tender_docx_path):
            msg = f"tender docx not found: {tender_docx_path}"
            errors.append(msg)
            logger.warning(f"[samples] extractor: {msg}. project_id={project_id}")
            return {
                "candidate_titles": 0,
                "matched_sections": 0,
                "upserted_fragments": 0,
                "errors": errors,
            }
        
        ext = os.path.splitext(tender_docx_path or "")[1].lower().strip()

        # ===== 1) 解析输入为"统一的 body_items" =====
        doc = None
        pdf_diag = None

        if ext == ".pdf":
            # ✅ 使用新的 PDF layout extractor（正确顺序 + 去噪 + 表格）
            items, pdf_diag = extract_pdf_items(tender_docx_path, max_pages=500)
            n_total = len(items)

            logger.info(f"[samples][pdf] layout_diag={pdf_diag}, project_id={project_id}")

            # ✅ 使用新的 PDF detector（区域定位 + 标题候选切片）
            fragments, det_diag = detect_pdf_fragments(
                items=items,
                title_normalize_fn=self.matcher.normalize,
                title_to_type_fn=lambda norm: self.matcher.match_type(norm),
            )
            logger.info(f"[samples][pdf] detect_diag={det_diag}, project_id={project_id}")

            # ✅ 直接 upsert fragments（跳过 LLM 流程）
            upserted = 0
            for frag in fragments:
                s = int(frag["start_body_index"])
                e = int(frag["end_body_index"])
                if s < 0 or e < s or e >= len(items):
                    continue

                # 保存 blocks_json（paragraph/table 混排）
                blocks = items[s:e+1]
                title = (frag.get("title") or "").strip()
                norm_key = frag.get("norm_key") or "OTHER"
                title_norm = self.matcher.normalize(title)

                diagnostics = {
                    "pdf_layout_diag": pdf_diag,
                    "pdf_detect_diag": det_diag,
                    "strategy": frag.get("strategy"),
                    "confidence": float(frag.get("confidence") or 0),
                }

                try:
                    self.dao.upsert_fragment(
                        owner_type="PROJECT",
                        owner_id=project_id,
                        source_file_key=str(file_key or tender_docx_path),
                        source_file_sha256=file_sha256,
                        fragment_type=str(norm_key),
                        title=title,
                        title_norm=title_norm,
                        path_hint=None,
                        heading_level=1,
                        start_body_index=s,
                        end_body_index=e,
                        confidence=float(frag.get("confidence") or 0.7),
                        diagnostics_json=json.dumps(diagnostics, ensure_ascii=False),
                        blocks_json=json.dumps(blocks, ensure_ascii=False),
                    )
                    upserted += 1
                    logger.info(
                        f"[samples][pdf] fragment upserted. project_id={project_id}, type={norm_key}, "
                        f"title={title[:80]!r}, start={s}, end={e}, conf={frag.get('confidence')}"
                    )
                except Exception as ex:
                    errors.append(f"upsert_fragment failed: {type(ex).__name__}: {str(ex)}")
                    logger.warning(f"[samples][pdf] upsert failed: {type(ex).__name__}: {str(ex)}. project_id={project_id}")

            # 返回 PDF 专用 summary（不走后续的 LLM/规则流程）
            return {
                "body_elements": len(items),
                "anchors_found": 0,
                "llm_spans_raw": 0,
                "llm_spans_valid": 0,
                "fragments_detected": len(fragments),
                "upserted_fragments": upserted,
                "rules_diag": {"pdf_layout": pdf_diag, "pdf_detect": det_diag},
                "errors": errors,
                "input_ext": ext,
                "pdf_diag": pdf_diag,
            }

        else:
            with open(tender_docx_path, "rb") as f:
                docx_bytes = f.read()
            doc = Document(BytesIO(docx_bytes))
            body_elements = list(doc.element.body)
            n_total = len(body_elements)

            # docx 的原逻辑保持不变
            elements_meta, anchors = self._scan_body_elements(doc)

        logger.info(
            f"[samples] extractor: input parsed. project_id={project_id}, ext={ext}, "
            f"n_total={n_total}, elements_meta={len(elements_meta)}, anchors_found={len(anchors)}, pdf_diag={pdf_diag}"
        )
        for i in anchors[:40]:
            # 打印锚点命中前 40 条（便于定位为什么 0）
            m = next((x for x in elements_meta if int(x.get("i")) == int(i)), None)
            if m:
                logger.info(f"[samples] extractor: anchor i={m.get('i')} t={m.get('t')} txt={str(m.get('txt') or '')[:80]!r}")

        # 3) 构造 LLM 输入窗口（最多 260 个元素）
        window_indices = self._build_llm_window_indices(n_total=n_total, anchors=anchors, elements_meta=elements_meta)
        elements_window = []
        meta_by_i = {int(m["i"]): m for m in elements_meta if "i" in m}
        for i in window_indices:
            m = meta_by_i.get(int(i))
            if not m:
                # 对于没提到 text 的空元素，跳过（避免 token 浪费）
                continue
            elements_window.append(
                {
                    "i": int(m.get("i")),
                    "t": m.get("t"),
                    "txt": m.get("txt"),
                    "style": m.get("style"),
                    "h": m.get("h"),
                }
            )

        # 4) 调 LLM 定位 spans（校验+过滤）
        spans: List[TenderSampleSpan] = []
        llm_errors: List[str] = []
        try:
            spans = self.locator.locate(elements_window)
        except Exception as e:
            llm_errors.append(f"llm locate failed: {type(e).__name__}: {str(e)}")
            spans = []

        valid_spans: List[TenderSampleSpan] = []
        for sp in spans:
            try:
                s = int(sp.start_body_index)
                e = int(sp.end_body_index)
                conf = float(sp.confidence)
                if s < 0 or e < 0 or s >= n_total or e >= n_total:
                    continue
                if s > e:
                    continue
                if conf < 0.55:
                    continue
                valid_spans.append(sp)
            except Exception:
                continue

        logger.info(
            f"[samples] extractor: llm spans. project_id={project_id}, raw={len(spans)}, valid={len(valid_spans)}"
        )

        # 5) 若 spans 为空：回退到改进的规则方法（PDF 已在前面提前返回，这里只处理 DOCX）
        fallback_spans: List[TenderSampleSpan] = []
        rules_fragments = []
        if not valid_spans:
            # 对 DOCX：用 _extract_body_items(doc)
            try:
                body_items = self._extract_body_items(doc)
                logger.info(f"[samples] extractor: body_items extracted for rules. project_id={project_id}, count={len(body_items)}")
            except Exception as e:
                logger.warning(f"[samples] extractor: _extract_body_items failed: {type(e).__name__}: {str(e)}. project_id={project_id}")
                body_items = []
            
            # 调用改进的规则方法
            if body_items:
                try:
                    rules_fragments = self._identify_fragments_by_rules(body_items)
                    logger.info(f"[samples] extractor: rules fragments detected. project_id={project_id}, count={len(rules_fragments)}")
                except Exception as e:
                    logger.warning(f"[samples] extractor: rules method failed: {type(e).__name__}: {str(e)}. project_id={project_id}")
                    rules_fragments = []
            
            # 转换为 spans 格式
            for frag in rules_fragments:
                fallback_spans.append(
                    TenderSampleSpan(
                        fragment_type=frag.get("norm_key", "OTHER"),
                        title=frag.get("title", ""),
                        start_body_index=int(frag.get("start_body_index", 0)),
                        end_body_index=int(frag.get("end_body_index", 0)),
                        confidence=float(frag.get("confidence", 0.70)),
                        reason=frag.get("strategy", "rules_format_section_ranked"),
                    )
                )
            valid_spans = fallback_spans
            logger.info(f"[samples] extractor: fallback to rules method. project_id={project_id}, spans={len(valid_spans)}")

        # 6) Upsert 新 fragments（使用 file_key 去重，不再清空旧数据）
        upserted = 0
        for sp in valid_spans:
            start_body_index = int(sp.start_body_index)
            end_body_index = int(sp.end_body_index)
            title = (sp.title or "").strip() or f"FRAG_{start_body_index}"

            internal_type = self._map_llm_type_to_internal(sp.fragment_type, title)
            title_norm = self.matcher.normalize(title)

            # heading_level：尽量用扫描到的 h，否则默认 1
            heading_level = None
            try:
                heading_level = meta_by_i.get(start_body_index, {}).get("h")
            except Exception:
                heading_level = None
            if heading_level is None:
                heading_level = 1

            diagnostics = {
                "llm_fragment_type": sp.fragment_type,
                "confidence": float(sp.confidence),
                "reason": sp.reason,
                "window_size": len(elements_window),
                "anchors_found": len(anchors),
            }
            try:
                # 使用 upsert 而不是 create，避免重复插入
                self.dao.upsert_fragment(
                    owner_type="PROJECT",
                    owner_id=project_id,
                    # 使用稳定的 file_key 而不是临时路径
                    source_file_key=str(file_key or tender_docx_path),
                    source_file_sha256=file_sha256,
                    fragment_type=str(internal_type),
                    title=title,
                    title_norm=title_norm,
                    path_hint=None,
                    heading_level=int(heading_level),
                    start_body_index=int(start_body_index),
                    end_body_index=int(end_body_index),
                    confidence=float(sp.confidence),
                    diagnostics_json=json.dumps(diagnostics, ensure_ascii=False),
                )
                upserted += 1
                logger.info(
                    f"[samples] extractor: fragment upserted. project_id={project_id}, type={internal_type}, "
                    f"title={title[:80]!r}, start={start_body_index}, end={end_body_index}, conf={sp.confidence}"
                )
            except Exception as e:
                msg = f"upsert_fragment failed: {type(e).__name__}: {e}"
                errors.append(msg)
                logger.warning(f"[samples] extractor: {msg}. project_id={project_id}, title={title[:80]!r}")

        if llm_errors:
            for le in llm_errors[:5]:
                logger.warning(f"[samples] extractor: {le}. project_id={project_id}")

        # 获取规则诊断信息
        rules_diag = getattr(self, "_last_rules_diag", {}) if isinstance(getattr(self, "_last_rules_diag", {}), dict) else {}
        
        # fragments_detected: LLM 检测到的或规则检测到的总数（不是 upserted 数，因为可能有重复）
        fragments_detected = len(valid_spans)

        logger.info(f"[samples] extractor: done. project_id={project_id}, fragments_detected={fragments_detected}, upserted_fragments={upserted}")
        return {
            "body_elements": n_total,
            "anchors_found": len(anchors),
            "llm_spans_raw": len(spans),
            "llm_spans_valid": len(valid_spans),
            "fragments_detected": fragments_detected,
            "upserted_fragments": upserted,
            "rules_diag": rules_diag,
            "errors": errors,
            "input_ext": ext,
            "pdf_diag": pdf_diag,
        }
    def get_fragments(self, project_id: str) -> List[dict]:
        """获取项目的所有范本片段"""
        return self.dao.list_fragments("PROJECT", project_id)
