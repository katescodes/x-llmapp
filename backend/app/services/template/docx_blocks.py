"""
DOCX Blocks 提取工具
按 body 顺序提取段落和表格的结构化信息，供 LLM 分析使用
"""
from __future__ import annotations
import logging

from docx import Document
from .docx_ooxml import iter_block_items, paragraph_text, CONTENT_MARKER

logger = logging.getLogger(__name__)


def extract_doc_blocks(docx_path: str) -> list[dict]:
    """
    提取文档的结构化块列表
    
    每个块包含：
    - blockId: 唯一标识
    - type: paragraph 或 table
    - styleName: 样式名称
    - text: 文本内容（段落）或表格摘要
    - markerFlags: 标记信息（如是否包含 [[CONTENT]]）
    
    Args:
        docx_path: DOCX 文件路径
        
    Returns:
        块列表
    """
    doc = Document(docx_path)
    blocks = []
    idx = 0
    
    for kind, blk in iter_block_items(doc):
        if kind == "p":
            # 段落
            txt = paragraph_text(blk)
            style_name = None
            try:
                if blk.style:
                    style_name = blk.style.name
            except Exception:
                pass
            
            blocks.append({
                "blockId": f"b{idx}",
                "type": "paragraph",
                "styleName": style_name,
                "text": txt,
                "markerFlags": {
                    "hasContentMarker": bool(txt and CONTENT_MARKER in txt)
                }
            })
        else:
            # 表格：提取前2行、前6列的摘要
            snippet = ""
            style_name = None
            try:
                if blk.style:
                    style_name = blk.style.name
            except Exception:
                pass
            
            try:
                rows = blk.rows[:2]
                cells = []
                for r in rows:
                    cells.append(" | ".join((c.text or "").strip() for c in r.cells[:6]))
                snippet = "\n".join(cells)
            except Exception as e:
                logger.warning(f"提取表格摘要失败: {e}")
            
            blocks.append({
                "blockId": f"b{idx}",
                "type": "table",
                "styleName": style_name,
                "text": snippet,
                "markerFlags": {}
            })
        
        idx += 1
    
    logger.info(f"提取文档块: {len(blocks)} 个块")
    return blocks

