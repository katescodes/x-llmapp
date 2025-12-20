"""
OutlineSampleAttacher - 目录范本挂载器
将抽取的范本片段自动挂载到目录节点的正文槽位
"""
from typing import Any, Dict, List, Optional
import logging
import os

from app.services.dao.tender_dao import TenderDAO
from app.services.fragment.fragment_matcher import FragmentTitleMatcher
from app.services.fragment.fragment_type import FragmentType

logger = logging.getLogger(__name__)


class OutlineSampleAttacher:
    """目录范本挂载器"""
    
    def __init__(self, dao: TenderDAO):
        self.dao = dao
        self.matcher = FragmentTitleMatcher()
    
    def attach(self, project_id: str, outline_nodes: List[Dict[str, Any]]) -> int:
        """
        将范本片段挂载到目录节点
        
        Args:
            project_id: 项目ID
            outline_nodes: 目录节点列表（扁平结构）
        """
        attached_count = 0
        # 1. 获取项目的所有范本片段
        fragments = self.dao.list_fragments("PROJECT", project_id)

        def _is_valid_fragment(frag: Dict[str, Any]) -> bool:
            try:
                src = (frag.get("source_file_key") or "").strip()
                if not src or not str(src).lower().endswith(".docx"):
                    return False
                s = frag.get("start_body_index")
                e = frag.get("end_body_index")
                if s is None or e is None:
                    return False
                s = int(s)
                e = int(e)
                if s < 0 or e < 0 or s > e:
                    return False
                return True
            except Exception:
                return False
        
        # 按类型组织片段（仅保留合法片段）
        fragments_by_type: Dict[str, List[Dict[str, Any]]] = {}
        for frag in fragments:
            if not _is_valid_fragment(frag):
                # 避免“挂载空”：没有合法 start/end/source 的片段不参与匹配
                continue
            ftype = frag.get("fragment_type")
            if ftype not in fragments_by_type:
                fragments_by_type[ftype] = []
            fragments_by_type[ftype].append(frag)

        # 如果没有任何可用片段：清理历史的 TEMPLATE_SAMPLE 标记，避免“挂载但没有内容”
        if not fragments_by_type:
            for node in outline_nodes:
                node_id = node.get("id")
                if not node_id:
                    continue
                existing_body = self.dao.get_section_body(project_id, node_id)
                if not existing_body:
                    continue
                if existing_body.get("source") != "TEMPLATE_SAMPLE":
                    continue
                # 不覆盖 USER/AI；这里仅清理 TEMPLATE_SAMPLE
                self.dao.upsert_section_body(
                    project_id=project_id,
                    node_id=node_id,
                    source="EMPTY",
                    fragment_id=None,
                    content_html=None,
                )
            return 0
        
        # 2. 遍历目录节点，匹配并挂载
        for node in outline_nodes:
            node_id = node.get("id")
            if not node_id:
                continue
            
            # attach 策略：
            # - 仅当该 node 当前 section_body 不是 USER（或 USER 为空）时才覆盖挂载
            existing_body = self.dao.get_section_body(project_id, node_id)
            if existing_body:
                # 如果已有用户编辑内容，跳过
                if existing_body.get("source") == "USER":
                    if existing_body.get("content_html") or existing_body.get("content_json"):
                        continue
                # 如果已有 AI 生成内容，跳过
                if existing_body.get("source") == "AI":
                    continue
                # 如果已有 TEMPLATE_SAMPLE 且有内容，跳过（避免重复覆盖）
                if existing_body.get("source") == "TEMPLATE_SAMPLE":
                    if existing_body.get("content_json") or existing_body.get("content_html"):
                        continue
            
            # 归一化节点标题
            node_title = node.get("title", "")
            node_title_norm = self.matcher.normalize(node_title)
            
            if not node_title_norm:
                continue
            
            # 匹配 FragmentType
            ftype = self.matcher.match_type(node_title_norm)
            if not ftype:
                continue
            
            # 查找该类型的最佳匹配片段
            best_fragment = self._find_best_fragment(
                node_title_norm,
                fragments_by_type.get(str(ftype), [])
            )
            
            if not best_fragment:
                continue
            # 二次校验（防止 candidates 中混入不合法）
            if not _is_valid_fragment(best_fragment):
                continue
            
            # 挂载片段并写入 content_json（使前端立即可见）
            content_json = self._extract_fragment_blocks(best_fragment)
            
            self.dao.upsert_section_body(
                project_id=project_id,
                node_id=node_id,
                source="TEMPLATE_SAMPLE",
                fragment_id=best_fragment["id"],
                content_html=None,  # 不存储HTML
                content_json=content_json,  # ✅ 写入结构化内容，前端立即可见
            )
            attached_count += 1

        return attached_count
    
    def _find_best_fragment(
        self,
        node_title_norm: str,
        candidates: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        从候选片段中找到最佳匹配
        
        匹配规则：
        1. 优先标题完全相等
        2. 其次标题包含关系
        3. 最后按置信度和范围长度排序
        """
        if not candidates:
            return None
        
        # 精确匹配
        for frag in candidates:
            frag_title_norm = frag.get("title_norm", "")
            if frag_title_norm == node_title_norm:
                return frag
        
        # 包含匹配
        matches_with_score = []
        for frag in candidates:
            frag_title_norm = frag.get("title_norm", "")
            
            if node_title_norm in frag_title_norm or frag_title_norm in node_title_norm:
                # 计算得分：置信度 + 范围长度
                confidence = frag.get("confidence") or 0.0
                range_len = frag.get("end_body_index", 0) - frag.get("start_body_index", 0)
                score = confidence * 1000 + range_len
                matches_with_score.append((score, frag))
        
        if matches_with_score:
            matches_with_score.sort(key=lambda x: x[0], reverse=True)
            return matches_with_score[0][1]
        
        # 如果没有包含匹配，返回第一个（已按置信度排序）
        return candidates[0] if candidates else None
    
    def _extract_fragment_blocks(self, fragment: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        从源文件中提取片段的 blocks 内容
        
        Returns:
            blocks 列表，格式：[{type:'paragraph'|'table', text/tableData/...}, ...]
        """
        try:
            from docx import Document
            from docx.text.paragraph import Paragraph
            from docx.table import Table
            
            source_file = fragment.get("source_file_key")
            if not source_file or not os.path.exists(source_file):
                logger.warning(f"[attacher] source_file not found: {source_file}")
                return []
            
            start_idx = int(fragment.get("start_body_index", 0))
            end_idx = int(fragment.get("end_body_index", 0))
            
            if start_idx < 0 or end_idx < 0 or start_idx > end_idx:
                logger.warning(f"[attacher] invalid indices: start={start_idx}, end={end_idx}")
                return []
            
            doc = Document(source_file)
            
            # 使用与 fragment_extractor 相同的逻辑：按 body 顺序提取
            para_map = {p._p: p for p in doc.paragraphs}
            tbl_map = {t._tbl: t for t in doc.tables}
            
            blocks = []
            idx = 0
            
            for child in doc.element.body.iterchildren():
                # 只提取指定范围的 blocks
                if idx < start_idx:
                    idx += 1
                    continue
                if idx > end_idx:
                    break
                
                tag = child.tag.split("}")[-1]
                if tag == "p":
                    p = para_map.get(child)
                    if p:
                        text = (p.text or "").strip()
                        blocks.append({
                            "type": "paragraph",
                            "text": text,
                            "styleName": getattr(getattr(p, "style", None), "name", None),
                        })
                elif tag == "tbl":
                    t = tbl_map.get(child)
                    if t:
                        rows = []
                        for r in t.rows:
                            rows.append([(c.text or "").strip() for c in r.cells])
                        blocks.append({
                            "type": "table",
                            "tableData": rows,
                            "styleName": getattr(getattr(t, "style", None), "name", None),
                        })
                
                idx += 1
            
            logger.info(f"[attacher] extracted {len(blocks)} blocks from fragment {fragment.get('id')}")
            return blocks
            
        except Exception as e:
            logger.error(f"[attacher] _extract_fragment_blocks failed: {type(e).__name__}: {e}")
            return []
