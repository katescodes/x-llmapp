"""
证据链映射工具
用于将 chunk_ids 转换为 SpanRef 证据片段引用
"""
from typing import List, Optional, Dict
from ..schemas.evidence import SpanRef
from ..services.dao import kb_dao


def chunks_to_span_refs(chunk_ids: List[str]) -> List[SpanRef]:
    """
    将 chunk_ids 转换为 SpanRef 列表
    
    当前实现：
    - 从 kb_chunks 表获取 chunk 元数据
    - 尝试从 chunk 的 position 或其他元数据中提取页码信息
    - 如果没有 page 信息，返回空 SpanRef 列表（但不报错）
    
    Args:
        chunk_ids: chunk ID 列表
        
    Returns:
        SpanRef 列表（可能为空）
    """
    if not chunk_ids:
        return []
    
    # 批量获取 chunks
    chunks_map = kb_dao.get_chunks_by_ids(chunk_ids)
    
    span_refs = []
    for chunk_id in chunk_ids:
        chunk = chunks_map.get(chunk_id)
        if not chunk:
            continue
        
        # 尝试提取页码信息
        page_no = _extract_page_no(chunk)
        
        # 如果有页码信息，创建 SpanRef
        if page_no:
            span_ref = SpanRef(
                page_no=page_no,
                # 可以从 chunk 的 content 中提取 quote
                quote=_extract_quote(chunk.get("content", ""))
            )
            span_refs.append(span_ref)
    
    return span_refs


def _extract_page_no(chunk: Dict) -> Optional[int]:
    """
    从 chunk 元数据中提取页码
    
    尝试多种方式：
    1. chunk 的 url 或 title 中是否包含页码信息（如 "page_5", "第5页"）
    2. chunk 的 position 字段（如果能映射到页码）
    3. 其他元数据字段
    
    Args:
        chunk: chunk 字典
        
    Returns:
        页码（从1开始），如果无法提取则返回 None
    """
    # 方式1：从 title 中提取（如果 title 格式为 "xxx - 第N页" 或 "page N"）
    title = chunk.get("title", "")
    if title:
        # 尝试匹配 "第N页", "page N", "p.N" 等格式
        import re
        # 匹配 "第N页"
        m = re.search(r"第\s*(\d+)\s*页", title)
        if m:
            return int(m.group(1))
        # 匹配 "page N" 或 "Page N"
        m = re.search(r"page\s+(\d+)", title, re.IGNORECASE)
        if m:
            return int(m.group(1))
        # 匹配 "p.N" 或 "P.N"
        m = re.search(r"p\.?\s*(\d+)", title, re.IGNORECASE)
        if m:
            return int(m.group(1))
    
    # 方式2：从 url 中提取（类似逻辑）
    url = chunk.get("url", "")
    if url:
        import re
        m = re.search(r"page[_-]?(\d+)", url, re.IGNORECASE)
        if m:
            return int(m.group(1))
    
    # 方式3：如果没有 page 信息，返回 None
    # 注意：position 字段表示 chunk 在文档中的顺序，不是页码
    # 除非有明确的映射关系，否则不应该将 position 当作页码
    
    return None


def _extract_quote(content: str, max_length: int = 200) -> str:
    """
    从 chunk 内容中提取引用文本
    
    Args:
        content: chunk 内容
        max_length: 最大长度
        
    Returns:
        引用文本（截断到指定长度）
    """
    if not content:
        return ""
    
    # 去除多余的空白字符
    content = " ".join(content.split())
    
    # 截断到指定长度
    if len(content) > max_length:
        content = content[:max_length] + "..."
    
    return content

