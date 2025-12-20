"""
Context Builder
构建带标记的上下文文本
"""
from typing import Any, Dict, List


def build_marked_context(chunks: List[Dict[str, Any]]) -> str:
    """
    构建带标记的上下文（与旧版格式一致）
    
    Args:
        chunks: 文档块列表，每个块包含 chunk_id 和 text
        
    Returns:
        格式化的上下文字符串，形如：
        [0] <chunk id="xxx">
        文本内容
        </chunk>
        
        [1] <chunk id="yyy">
        文本内容
        </chunk>
    """
    lines = []
    for idx, chunk in enumerate(chunks):
        chunk_id = chunk.get("chunk_id", "")
        text = chunk.get("text", "")
        lines.append(f"[{idx}] <chunk id=\"{chunk_id}\">\n{text}\n</chunk>")
    return "\n\n".join(lines)

