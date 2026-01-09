"""
范本章节定位器
在招标文件中定位"格式范本"章节，减少LLM处理范围
"""
from __future__ import annotations
import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# 组合匹配方案：文件类型词 + 格式词
FILE_TYPE_KEYWORDS = [
    "投标", "响应", "应答", "磋商", "竞谈", "报价",
    "投标文件", "响应文件", "应答文件", "磋商文件", "竞谈文件"
]

FORMAT_KEYWORDS = [
    "格式", "样式", "范本", "模板"
]

# 备用精确匹配关键词（降级策略）
FALLBACK_KEYWORDS = [
    "第六章",
    "附件",
    "格式附件"
]

# 范本结束标志
FORMAT_CHAPTER_END_KEYWORDS = [
    "第七章",
    "第八章",
    "评分标准",
    "评审办法",
    "合同条款"
]


def _is_format_chapter_title(text: str) -> bool:
    """
    判断文本是否为格式章节标题（组合匹配）
    
    策略：同时包含"文件类型词"和"格式词"
    例如：投标文件格式、磋商响应文件编制要求、报价文件组成
    
    Args:
        text: 待检查的文本
        
    Returns:
        是否为格式章节标题
    """
    # 组合匹配：文件类型 + 格式
    has_file_type = any(keyword in text for keyword in FILE_TYPE_KEYWORDS)
    has_format = any(keyword in text for keyword in FORMAT_KEYWORDS)
    
    if has_file_type and has_format:
        return True
    
    # 降级：备用关键词
    for keyword in FALLBACK_KEYWORDS:
        if keyword in text:
            return True
    
    return False


def locate_format_chapter(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    在 blocks 中定位"格式范本"章节
    
    策略：
    1. 使用组合匹配查找标题：文件类型词 + 格式词
    2. 从该块开始，直到遇到结束标志或文档结尾
    3. 返回范围内的所有 blocks
    
    Args:
        blocks: 完整的文档 blocks
        
    Returns:
        格式章节内的 blocks
    """
    if not blocks:
        logger.warning("blocks 为空，返回空列表")
        return []
    
    logger.info(f"开始定位格式章节（组合匹配），总块数: {len(blocks)}")
    
    # 1. 查找起始位置
    start_idx = None
    for i, block in enumerate(blocks):
        if block["type"] != "p":
            continue
        
        text = block.get("text", "").strip()
        if not text:
            continue
        
        # 检查是否是格式章节标题（标题通常较短）
        if len(text) < 100 and _is_format_chapter_title(text):
            start_idx = i
            logger.info(f"✅ 找到格式章节起始: block[{i}] = '{text[:50]}'")
            break
    
    # 如果没找到，返回全部（降级策略）
    if start_idx is None:
        logger.warning("⚠️ 未找到格式章节标题，返回全部 blocks")
        return blocks
    
    # 2. 查找结束位置
    end_idx = len(blocks)
    for i in range(start_idx + 1, len(blocks)):
        block = blocks[i]
        if block["type"] != "p":
            continue
        
        text = block.get("text", "").strip()
        if not text:
            continue
        
        # 检查是否是结束标志
        for keyword in FORMAT_CHAPTER_END_KEYWORDS:
            if text.startswith(keyword) or keyword in text[:20]:
                end_idx = i
                logger.info(f"找到格式章节结束: block[{i}] = '{text[:50]}'")
                break
        
        if end_idx < len(blocks):
            break
    
    # 3. 返回范围内的 blocks
    chapter_blocks = blocks[start_idx:end_idx]
    logger.info(f"格式章节定位完成: block[{start_idx}:{end_idx}]，共 {len(chapter_blocks)} 个块")
    
    return chapter_blocks


def is_heading_block(block: Dict[str, Any]) -> bool:
    """
    判断一个 block 是否可能是标题
    
    Args:
        block: block 字典
        
    Returns:
        是否是标题
    """
    if block["type"] != "p":
        return False
    
    text = block.get("text", "").strip()
    if not text:
        return False
    
    # 标题特征
    # 1. 较短（<100字符）
    if len(text) > 100:
        return False
    
    # 2. 样式名包含"标题"或"Heading"
    style_name = block.get("styleName", "")
    if style_name and ("标题" in style_name or "Heading" in style_name.lower()):
        return True
    
    # 3. 包含章节编号
    if re.match(r'^[\d一二三四五六七八九十]+[、\.)：]', text):
        return True
    
    # 4. 全是数字或简短标题
    if re.match(r'^\d+\.?\d*$', text):  # 纯数字
        return True
    
    return False


def extract_heading_hierarchy(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    提取文档的标题层级结构（用于辅助定位）
    
    Args:
        blocks: 文档 blocks
        
    Returns:
        标题 blocks 列表（包含索引信息）
    """
    headings = []
    
    for i, block in enumerate(blocks):
        if is_heading_block(block):
            headings.append({
                "index": i,
                "blockId": block["blockId"],
                "text": block.get("text", "").strip(),
                "styleName": block.get("styleName")
            })
    
    logger.debug(f"提取标题层级: {len(headings)} 个标题")
    return headings

