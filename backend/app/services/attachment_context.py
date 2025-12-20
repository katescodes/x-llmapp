"""
附件上下文处理工具
处理附件文本的分块、检索和拼接
"""
import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)


class AttachmentChunk:
    """附件文本块"""
    
    def __init__(self, text: str, filename: str, chunk_index: int, total_chunks: int):
        self.text = text
        self.filename = filename
        self.chunk_index = chunk_index
        self.total_chunks = total_chunks
    
    def get_header(self) -> str:
        """获取块的头部标识"""
        return f"[来源: {self.filename} | chunk {self.chunk_index}/{self.total_chunks}]"


def chunk_attachment_text(
    text: str,
    filename: str,
    chunk_size: int = 4000,
    overlap: int = 200,
) -> List[AttachmentChunk]:
    """
    将附件文本分块
    
    Args:
        text: 附件文本
        filename: 文件名
        chunk_size: 每块大小（字符数）
        overlap: 块之间的重叠（字符数）
    
    Returns:
        文本块列表
    """
    if not text or not text.strip():
        return []
    
    # 按段落分割
    paragraphs = re.split(r'\n\s*\n', text)
    
    chunks = []
    current_chunk = []
    current_size = 0
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        para_size = len(para)
        
        # 如果单个段落超过chunk_size，需要进一步分割
        if para_size > chunk_size:
            # 先保存当前chunk
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_size = 0
            
            # 按句子分割长段落
            sentences = re.split(r'([。！？\.\!\?]+)', para)
            temp_chunk = ""
            for i in range(0, len(sentences), 2):
                sentence = sentences[i]
                if i + 1 < len(sentences):
                    sentence += sentences[i + 1]
                
                if len(temp_chunk) + len(sentence) > chunk_size:
                    if temp_chunk:
                        chunks.append(temp_chunk)
                    temp_chunk = sentence
                else:
                    temp_chunk += sentence
            
            if temp_chunk:
                chunks.append(temp_chunk)
            continue
        
        # 正常情况：累积段落
        if current_size + para_size > chunk_size and current_chunk:
            # 当前chunk已满，保存
            chunks.append("\n\n".join(current_chunk))
            # 保留最后一个段落作为重叠
            if overlap > 0 and current_chunk:
                last_para = current_chunk[-1]
                if len(last_para) <= overlap:
                    current_chunk = [last_para, para]
                    current_size = len(last_para) + para_size
                else:
                    current_chunk = [para]
                    current_size = para_size
            else:
                current_chunk = [para]
                current_size = para_size
        else:
            current_chunk.append(para)
            current_size += para_size
    
    # 保存最后一个chunk
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
    
    # 创建AttachmentChunk对象
    total = len(chunks)
    result = [
        AttachmentChunk(chunk, filename, i + 1, total)
        for i, chunk in enumerate(chunks)
    ]
    
    logger.info(f"Chunked attachment: file={filename} chunks={total} avg_size={sum(len(c.text) for c in result) // total if total > 0 else 0}")
    
    return result


def select_relevant_chunks(
    chunks: List[AttachmentChunk],
    query: str,
    top_k: int = 8,
) -> List[AttachmentChunk]:
    """
    选择与查询相关的文本块（简单的关键词匹配）
    
    Args:
        chunks: 所有文本块
        query: 用户查询
        top_k: 返回前K个
    
    Returns:
        相关的文本块列表
    """
    if not chunks:
        return []
    
    # 提取查询关键词（简单分词）
    query_keywords = set(re.findall(r'[\w\u4e00-\u9fff]+', query.lower()))
    
    if not query_keywords:
        # 如果没有关键词，返回前N个
        return chunks[:top_k]
    
    # 计算每个chunk的相关性得分
    scored_chunks = []
    for chunk in chunks:
        text_lower = chunk.text.lower()
        score = 0
        
        # 关键词匹配得分
        for keyword in query_keywords:
            count = text_lower.count(keyword)
            score += count
        
        scored_chunks.append((score, chunk))
    
    # 按得分排序
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    
    # 返回top_k
    selected = [chunk for score, chunk in scored_chunks[:top_k]]
    
    logger.info(
        f"Selected chunks: query_len={len(query)} total_chunks={len(chunks)} "
        f"selected={len(selected)} top_scores={[s for s, _ in scored_chunks[:3]]}"
    )
    
    return selected


def build_attachment_context(
    chunks: List[AttachmentChunk],
    max_chars: int = 60000,
) -> str:
    """
    构建附件上下文字符串
    
    Args:
        chunks: 选中的文本块
        max_chars: 最大字符数
    
    Returns:
        格式化的附件上下文
    """
    if not chunks:
        return ""
    
    context_parts = []
    current_chars = 0
    
    for chunk in chunks:
        header = chunk.get_header()
        chunk_text = f"{header}\n{chunk.text}"
        chunk_chars = len(chunk_text)
        
        if current_chars + chunk_chars > max_chars:
            # 超出限制，截断
            remaining = max_chars - current_chars
            if remaining > 200:  # 至少保留200字符
                truncated = chunk_text[:remaining] + "\n...[已截断]"
                context_parts.append(truncated)
            break
        
        context_parts.append(chunk_text)
        current_chars += chunk_chars
    
    context = "\n\n".join(context_parts)
    
    logger.info(
        f"Built attachment context: chunks={len(context_parts)} "
        f"chars={len(context)} max={max_chars}"
    )
    
    return context
