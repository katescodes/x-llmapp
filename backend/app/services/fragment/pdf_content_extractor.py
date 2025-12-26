"""
PDF范本内容提取器 - 提取范本的完整原文（包括表格和文字）
"""
import re
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def extract_fragment_content(
    items: List[Dict[str, Any]], 
    start_idx: int, 
    end_idx: int
) -> Dict[str, Any]:
    """
    提取fragment的完整内容（包括表格和文字）
    
    Args:
        items: PDF的所有items
        start_idx: fragment起始索引
        end_idx: fragment结束索引
    
    Returns:
        {
            "type": "mixed" | "table" | "text",
            "items": [...],
            "html": "...",
            "text": "..."
        }
    """
    if start_idx < 0 or end_idx >= len(items) or start_idx > end_idx:
        logger.warning(f"Invalid indices: start={start_idx}, end={end_idx}, len={len(items)}")
        return {
            "type": "text",
            "items": [],
            "html": "",
            "text": ""
        }
    
    content_items = []
    text_parts = []
    html_parts = []
    
    # 提取start_idx到end_idx之间的所有items
    for it in items[start_idx:end_idx + 1]:
        item_type = it.get("type")
        
        if item_type == "paragraph":
            # 段落文本
            text = (it.get("text") or "").strip()
            if text:
                content_items.append({
                    "type": "paragraph",
                    "text": text,
                    "html": f"<p>{_escape_html(text)}</p>"
                })
                text_parts.append(text)
                html_parts.append(f"<p>{_escape_html(text)}</p>")
        
        elif item_type == "table":
            # ✅ 表格：使用tableData而不是text字段
            table_data = it.get("tableData", [])
            
            if table_data:
                # 从tableData生成HTML和文本
                table_html = _convert_tabledata_to_html(table_data)
                table_text = _convert_tabledata_to_text(table_data)
                
                content_items.append({
                    "type": "table",
                    "text": table_text,
                    "html": table_html,
                    "rows": len(table_data),
                    "cols": len(table_data[0]) if table_data else 0
                })
                text_parts.append(table_text)
                html_parts.append(table_html)
    
    # 判断内容类型
    has_table = any(it["type"] == "table" for it in content_items)
    has_text = any(it["type"] == "paragraph" for it in content_items)
    
    if has_table and has_text:
        content_type = "mixed"
    elif has_table:
        content_type = "table"
    else:
        content_type = "text"
    
    return {
        "type": content_type,
        "items": content_items,
        "html": "\n".join(html_parts),
        "text": "\n\n".join(text_parts)
    }


def _escape_html(text: str) -> str:
    """HTML转义"""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;"))


def _convert_tabledata_to_html(table_data: List[List[str]]) -> str:
    """
    将PDF表格数据（tableData）转换为HTML表格
    
    Args:
        table_data: 二维数组，如 [["序号", "项目"], ["1", "开标一览表"]]
    
    Returns:
        HTML表格字符串
    """
    if not table_data:
        return ""
    
    html = ['<table border="1" style="border-collapse: collapse; width: 100%; margin: 10px 0;">']
    
    for i, row in enumerate(table_data):
        if not row:
            continue
        
        # 第一行作为表头（如果看起来像标题）
        is_header = (i == 0 and any(kw in " ".join(row) for kw in ["序号", "项目", "名称", "编号", "内容", "要求", "标准", "金额", "数量"]))
        
        if is_header:
            html.append("<thead><tr>")
            for cell in row:
                html.append(f"<th style='padding: 8px; background-color: #f5f5f5; text-align: left; border: 1px solid #ddd;'>{_escape_html(cell)}</th>")
            html.append("</tr></thead>")
            html.append("<tbody>")
        else:
            if i == 0:
                html.append("<tbody>")
            html.append("<tr>")
            for cell in row:
                html.append(f"<td style='padding: 8px; border: 1px solid #ddd;'>{_escape_html(cell)}</td>")
            html.append("</tr>")
    
    html.append("</tbody>")
    html.append("</table>")
    return "".join(html)


def _convert_tabledata_to_text(table_data: List[List[str]]) -> str:
    """
    将PDF表格数据（tableData）转换为纯文本
    
    Args:
        table_data: 二维数组
    
    Returns:
        纯文本字符串，使用 | 分隔单元格
    """
    if not table_data:
        return ""
    
    lines = []
    for row in table_data:
        if row:
            line = " | ".join(cell for cell in row)
            lines.append(line)
    
    return "\n".join(lines)


def _convert_table_to_html(table_text: str) -> str:
    """
    将PDF表格文本转换为HTML表格
    
    简单版本：将文本按行列分割后生成HTML
    """
    if not table_text:
        return ""
    
    lines = table_text.split("\n")
    if not lines:
        return ""
    
    html = ['<table border="1" style="border-collapse: collapse; width: 100%; margin: 10px 0;">']
    
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        
        # 按 | 分割单元格（如果有）
        if "|" in line:
            cells = [c.strip() for c in line.split("|") if c.strip()]
        else:
            # 没有|分隔符，尝试按空格分割（至少4个空格）
            cells = re.split(r'\s{4,}', line.strip())
            cells = [c for c in cells if c]
        
        if not cells:
            # 如果没有单元格，整行作为一个单元格
            cells = [line.strip()]
        
        # 第一行作为表头（如果看起来像标题）
        if i == 0 and (len(cells) > 1 or any(kw in line for kw in ["项目", "名称", "序号", "编号", "内容", "要求", "标准"])):
            html.append("<thead><tr>")
            for cell in cells:
                html.append(f"<th style='padding: 8px; background-color: #f5f5f5; text-align: left;'>{_escape_html(cell)}</th>")
            html.append("</tr></thead>")
            html.append("<tbody>")
        else:
            if i == 0:
                html.append("<tbody>")
            html.append("<tr>")
            for cell in cells:
                html.append(f"<td style='padding: 8px; border: 1px solid #ddd;'>{_escape_html(cell)}</td>")
            html.append("</tr>")
    
    html.append("</tbody>")
    html.append("</table>")
    return "".join(html)


def sanitize_html(html: str, allowed_tags: List[str] = None) -> str:
    """
    清理HTML，只保留安全的标签
    
    简单版本：只允许特定标签
    """
    if allowed_tags is None:
        allowed_tags = ['table', 'tr', 'td', 'th', 'thead', 'tbody', 'p', 'br', 'strong', 'em', 'span', 'div']
    
    # 简单实现：去除script和style标签
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    
    # 去除on*事件属性
    html = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', '', html, flags=re.IGNORECASE)
    
    return html

