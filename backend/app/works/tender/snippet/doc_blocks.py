"""
文档 Blocks 抽取服务
支持从 DOCX 和 PDF 提取结构化块（段落、表格）
"""
from __future__ import annotations
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

logger = logging.getLogger(__name__)


def extract_blocks_from_docx(docx_path: str) -> List[Dict[str, Any]]:
    """
    从 DOCX 提取结构化 blocks
    
    Block类型：
    - paragraph: {blockId, type:"p", styleName, text}
    - table: {blockId, type:"table", rows:[[cellText, ...], ...]}
    
    Args:
        docx_path: DOCX 文件路径
        
    Returns:
        blocks 列表
    """
    logger.info(f"开始从 DOCX 提取 blocks: {docx_path}")
    
    doc = Document(docx_path)
    blocks = []
    block_idx = 0
    
    # 按 body 顺序遍历所有元素
    for element in doc.element.body:
        # 段落
        if element.tag.endswith('p'):
            para = Paragraph(element, doc)
            text = para.text or ""
            style_name = None
            
            try:
                if para.style:
                    style_name = para.style.name
            except Exception:
                pass
            
            blocks.append({
                "blockId": f"b{block_idx}",
                "type": "p",
                "styleName": style_name,
                "text": text
            })
            block_idx += 1
        
        # 表格
        elif element.tag.endswith('tbl'):
            table = Table(element, doc)
            rows = []
            
            try:
                for row in table.rows:
                    cells = []
                    for cell in row.cells:
                        cells.append((cell.text or "").strip())
                    rows.append(cells)
            except Exception as e:
                logger.warning(f"提取表格失败: {e}")
                rows = [["表格提取失败"]]
            
            blocks.append({
                "blockId": f"b{block_idx}",
                "type": "table",
                "rows": rows
            })
            block_idx += 1
    
    logger.info(f"DOCX blocks 提取完成: {len(blocks)} 个块")
    return blocks


def convert_pdf_to_docx(pdf_path: str, output_dir: Optional[str] = None) -> str:
    """
    将 PDF 转换为 DOCX（使用 LibreOffice）
    
    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录（可选）
        
    Returns:
        转换后的 DOCX 路径
        
    Raises:
        RuntimeError: 转换失败
    """
    logger.info(f"开始转换 PDF -> DOCX: {pdf_path}")
    
    if output_dir is None:
        output_dir = tempfile.gettempdir()
    
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    
    try:
        # 使用 LibreOffice 转换
        cmd = [
            "libreoffice",
            "--headless",
            "--convert-to", "docx",
            "--outdir", str(output_dir_path),
            pdf_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"LibreOffice 转换失败: {result.stderr}")
        
        # 查找输出文件
        pdf_name = Path(pdf_path).stem
        docx_path = output_dir_path / f"{pdf_name}.docx"
        
        if not docx_path.exists():
            raise RuntimeError(f"转换后的文件未找到: {docx_path}")
        
        logger.info(f"PDF 转换成功: {docx_path}")
        return str(docx_path)
    
    except subprocess.TimeoutExpired:
        raise RuntimeError("PDF 转换超时（>120s）")
    except FileNotFoundError:
        raise RuntimeError("LibreOffice 未安装或不在 PATH 中")
    except Exception as e:
        logger.error(f"PDF 转换失败: {e}")
        raise RuntimeError(f"PDF 转换失败: {str(e)}")


def extract_blocks_from_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """
    从 PDF 提取结构化 blocks（先转 DOCX 再提取，失败则用PyMuPDF）
    
    Args:
        pdf_path: PDF 文件路径
        
    Returns:
        blocks 列表
    """
    logger.info(f"开始从 PDF 提取 blocks: {pdf_path}")
    
    # 尝试方法1: PDF -> DOCX -> blocks（更准确）
    try:
        docx_path = convert_pdf_to_docx(pdf_path)
        try:
            blocks = extract_blocks_from_docx(docx_path)
            logger.info(f"PDF 通过 DOCX 转换成功提取: {len(blocks)} 个块")
            return blocks
        finally:
            # 清理临时文件
            try:
                Path(docx_path).unlink()
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"PDF 转换为 DOCX 失败: {e}，尝试直接解析 PDF")
    
    # 尝试方法2: 直接用 PyMuPDF 提取（fallback）
    try:
        from app.services.fragment.pdf_blocks import extract_pdf_body_items
        
        body_items, diag = extract_pdf_body_items(pdf_path)
        logger.info(f"PDF 直接解析成功: {diag['blocks']} 个块（{diag['pages']} 页）")
        
        # 【重要】按页码和bodyIndex重新排序，确保内容连续
        body_items_sorted = sorted(body_items, key=lambda x: (x.get('pageNo', 0), x['bodyIndex']))
        
        # 转换为标准 blocks 格式
        blocks = []
        for idx, item in enumerate(body_items_sorted):
            blocks.append({
                "blockId": f"b{idx}",  # 重新分配blockId
                "type": "p",
                "styleName": item.get('styleName'),
                "text": item['text'],
                "pageNo": item.get('pageNo')
            })
        
        logger.info(f"PDF blocks已按页码重新排序")
        return blocks
    except Exception as e:
        logger.error(f"PDF 直接解析也失败: {e}")
        raise RuntimeError(f"PDF 提取失败（尝试了转换和直接解析）: {str(e)}")


def extract_blocks(file_path: str) -> List[Dict[str, Any]]:
    """
    智能提取文档 blocks（自动识别格式）
    
    Args:
        file_path: 文件路径（.docx 或 .pdf）
        
    Returns:
        blocks 列表
    """
    file_path_lower = file_path.lower()
    
    if file_path_lower.endswith('.docx'):
        return extract_blocks_from_docx(file_path)
    elif file_path_lower.endswith('.pdf'):
        return extract_blocks_from_pdf(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {file_path}")


def get_block_text_snippet(block: Dict[str, Any], max_length: int = 200) -> str:
    """
    获取 block 的文本摘要（用于 LLM 分析）
    
    Args:
        block: block 字典
        max_length: 最大长度
        
    Returns:
        文本摘要
    """
    if block["type"] == "p":
        text = block.get("text", "")
        return text[:max_length]
    
    elif block["type"] == "table":
        rows = block.get("rows", [])
        if not rows:
            return "[空表格]"
        
        # 只取第一行
        first_row = rows[0]
        text = " | ".join(first_row)
        return text[:max_length] + f" [表格{len(rows)}行]"
    
    return ""


def blocks_to_text(blocks: List[Dict[str, Any]], include_tables: bool = True) -> str:
    """
    将 blocks 转换为纯文本内容
    
    用于：
    - 范本内容展示
    - 全文搜索
    - 内容预览
    
    Args:
        blocks: blocks 列表
        include_tables: 是否包含表格内容（默认True）
        
    Returns:
        纯文本内容
    """
    parts = []
    
    for block in blocks:
        block_type = block.get("type", "")
        
        # 段落类型
        if block_type == "p":
            text = block.get("text", "").strip()
            if text:
                parts.append(text)
                parts.append("")  # 段落间空行
        
        # 表格类型
        elif block_type == "table" and include_tables:
            rows = block.get("rows", [])
            if not rows:
                continue
            
            # 表格标记
            parts.append("[表格开始]")
            
            # 表头
            if len(rows) > 0:
                header = rows[0]
                parts.append(" | ".join(str(cell).strip() for cell in header))
                parts.append("-" * 50)  # 分隔线
            
            # 表格内容
            for row in rows[1:]:
                parts.append(" | ".join(str(cell).strip() for cell in row))
            
            parts.append("[表格结束]")
            parts.append("")
    
    # 合并并清理多余空行
    text = "\n".join(parts)
    
    # 清理连续的空行（保留最多一个空行）
    import re
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

