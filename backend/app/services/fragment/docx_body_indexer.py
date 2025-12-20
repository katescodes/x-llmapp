"""
DocxBodyIndexer - Word 文档结构索引器
用于解析 docx 文档，识别章节标题及其在 bodyElements 中的索引
"""
import re
from dataclasses import dataclass
from io import BytesIO
from typing import List, Optional

from docx import Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.text.paragraph import Paragraph

from app.services.docx_style_utils import guess_heading_level


@dataclass
class HeadingNode:
    """章节标题节点"""
    title: str
    level: int
    start_index: int          # 标题段落自身的索引
    end_index_candidate: int  # 到下一个同级或更高级标题前（不含下一个标题）


class DocxBodyIndexer:
    """Word 文档结构索引器"""
    
    def __init__(self):
        self._chapter_pattern = re.compile(r'^第[一二三四五六七八九十0-9]+[章节篇编]')
        self._numbering_pattern = re.compile(r'^\d+(\.\d+)*\.?\s+')
    
    def index_headings(self, docx_bytes: bytes) -> List[HeadingNode]:
        """
        解析 docx 并识别章节标题
        
        Args:
            docx_bytes: Word 文档字节内容
            
        Returns:
            章节标题列表
        """
        doc = Document(BytesIO(docx_bytes))
        body_elements = list(doc.element.body)
        
        headings: List[HeadingNode] = []
        
        for idx, element in enumerate(body_elements):
            if isinstance(element, CT_P):
                para = Paragraph(element, doc)
                heading_info = self._extract_heading_info(para)
                
                if heading_info:
                    title, level = heading_info
                    headings.append(HeadingNode(
                        title=title,
                        level=level,
                        start_index=idx,
                        end_index_candidate=-1  # 稍后计算
                    ))
        
        # 计算每个标题的结束索引
        self._compute_end_indices(headings, len(body_elements))
        
        return headings
    
    def _extract_heading_info(self, para: Paragraph) -> Optional[tuple[str, int]]:
        """
        从段落中提取标题信息
        
        Returns:
            (title, level) 或 None
        """
        text = para.text.strip()
        if not text:
            return None
        
        # 方法1: 使用大纲级别
        level = guess_heading_level(para)
        if level is not None:
            return (text, level)
        
        # 方法2: 使用标题样式
        level = self._get_heading_style_level(para)
        if level is not None:
            return (text, level)
        
        # 方法3: 使用正则匹配章节标题
        if self._chapter_pattern.match(text):
            return (text, 1)  # 假设"第X章"为一级标题
        
        # 方法4: 使用编号模式推断
        match = self._numbering_pattern.match(text)
        if match:
            numbering = match.group(0).strip().rstrip('.')
            level = len(numbering.split('.'))
            return (text, level)
        
        return None
    
    def _get_outline_level(self, para: Paragraph) -> Optional[int]:
        """获取段落的大纲级别"""
        # 兼容保留：不再直接访问 pPr.outlineLvl（某些模板会 AttributeError）
        lvl = guess_heading_level(para)
        return (lvl - 1) if lvl is not None else None
    
    def _get_heading_style_level(self, para: Paragraph) -> Optional[int]:
        """从样式名称中提取标题级别"""
        if not para.style:
            return None
        
        style_name = para.style.name or ""
        
        # 匹配 "Heading 1", "标题 1" 等
        patterns = [
            (r'Heading\s*(\d+)', 1),
            (r'标题\s*(\d+)', 1),
            (r'Heading(\d+)', 1),
            (r'Title', 1),
        ]
        
        for pattern, base in patterns:
            match = re.match(pattern, style_name, re.IGNORECASE)
            if match:
                if len(match.groups()) > 0:
                    return int(match.group(1))
                return base
        
        return None
    
    def _compute_end_indices(self, headings: List[HeadingNode], total_elements: int):
        """计算每个标题的结束索引（到下一个同级或更高级标题前）"""
        for i, heading in enumerate(headings):
            # 查找下一个同级或更高级（level 更小或相等）的标题
            next_heading_idx = None
            for j in range(i + 1, len(headings)):
                if headings[j].level <= heading.level:
                    next_heading_idx = headings[j].start_index
                    break
            
            if next_heading_idx is not None:
                # 结束于下一个标题之前（不含标题自身）
                heading.end_index_candidate = next_heading_idx - 1
            else:
                # 最后一个标题，结束于文档末尾
                heading.end_index_candidate = total_elements - 1
