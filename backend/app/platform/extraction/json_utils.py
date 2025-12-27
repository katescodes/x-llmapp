"""
JSON Utilities
JSON 提取与修复工具
"""
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def extract_json(text: str) -> Any:
    """
    从 LLM 输出中提取 JSON
    
    支持以下格式：
    - 纯 JSON
    - ```json ... ```
    - ``` ... ```
    
    Args:
        text: LLM 输出文本
        
    Returns:
        解析后的 Python 对象
        
    Raises:
        json.JSONDecodeError: 如果无法解析
    """
    if not text:
        raise ValueError("Empty text provided to extract_json")
    
    text = text.strip()
    
    # 尝试提取 ```json ... ``` 中的内容
    if "```json" in text:
        start_marker = text.find("```json")
        # 跳过 ```json 和后面的空白字符（包括换行符）
        start = start_marker + 7
        # 查找下一个非空白字符的位置
        while start < len(text) and text[start] in (' ', '\n', '\r', '\t'):
            start += 1
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()
        elif end == -1:
            # 没有找到结束标记，使用从start到结尾的所有内容
            text = text[start:].strip()
    elif "```" in text:
        start = text.find("```") + 3
        # 跳过空白字符
        while start < len(text) and text[start] in (' ', '\n', '\r', '\t'):
            start += 1
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()
        elif end == -1:
            # 没有找到结束标记，使用从start到结尾的所有内容
            text = text[start:].strip()
    
    # 解析 JSON
    return json.loads(text)


def repair_json(text: str) -> Any:
    """
    尝试修复常见的 JSON 格式问题
    
    包括：
    - 单引号替换为双引号
    - 去除首尾空白
    - 提取代码块中的JSON
    - 修复不完整的 JSON（截断的数组/对象）
    
    Args:
        text: 待修复的文本
        
    Returns:
        解析后的 Python 对象
        
    Raises:
        json.JSONDecodeError: 如果修复后仍无法解析
    """
    if not text:
        raise ValueError("Empty text provided to repair_json")
    
    text = text.strip()
    
    # 尝试提取代码块（与extract_json相同的逻辑）
    if "```json" in text:
        start_marker = text.find("```json")
        start = start_marker + 7
        while start < len(text) and text[start] in (' ', '\n', '\r', '\t'):
            start += 1
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()
        elif end == -1:
            text = text[start:].strip()
    elif "```" in text:
        start = text.find("```") + 3
        while start < len(text) and text[start] in (' ', '\n', '\r', '\t'):
            start += 1
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()
        elif end == -1:
            text = text[start:].strip()
    
    # 尝试修复常见问题 - 全局替换单引号为双引号
    if "'" in text:
        text = text.replace("'", '"')
    
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed: {e}, trying to repair incomplete JSON...")
        
        # 尝试修复不完整的 JSON（LLM 输出可能被截断）
        try:
            repaired = _repair_incomplete_json(text)
            if repaired:
                return json.loads(repaired)
        except Exception as repair_err:
            logger.warning(f"Incomplete JSON repair failed: {repair_err}")
        
        logger.error(f"Failed to repair JSON: {e}")
        logger.debug(f"Problematic text: {text[:500]}")
        raise


def _repair_incomplete_json(text: str) -> str:
    """
    尝试修复不完整的 JSON（例如 LLM 输出被截断）
    
    策略：
    1. 查找最后一个完整的对象（在数组中）
    2. 补全数组和对象的结束括号
    
    Args:
        text: 不完整的 JSON 文本
        
    Returns:
        修复后的 JSON 文本
    """
    text = text.strip()
    
    # 如果以逗号结尾，去掉它
    if text.endswith(','):
        text = text[:-1].strip()
    
    # 统计括号配对
    stack = []
    last_complete_pos = -1
    
    for i, char in enumerate(text):
        if char in '{[':
            stack.append((char, i))
        elif char in '}]':
            if stack:
                open_char, _ = stack.pop()
                expected_close = '}' if open_char == '{' else ']'
                if char == expected_close:
                    if not stack:
                        # 找到一个完整的顶层结构
                        last_complete_pos = i
                else:
                    # 括号不匹配，重置
                    stack = []
    
    # 如果有未配对的括号，尝试补全
    if stack:
        logger.info(f"Found {len(stack)} unclosed brackets, attempting to close them")
        
        # 如果有部分完整的结构，截取到最后一个完整对象
        if last_complete_pos > 0:
            # 查找这个位置之前的最后一个逗号
            search_start = max(0, last_complete_pos - 500)
            last_comma = text.rfind(',', search_start, last_complete_pos)
            
            if last_comma > 0:
                # 截取到最后一个完整对象
                text = text[:last_comma].strip()
                logger.info(f"Truncated to last complete object at position {last_comma}")
        
        # 重新统计需要补全的括号
        open_count = {'[': 0, '{': 0}
        for char in text:
            if char in '[{':
                open_count[char] += 1
            elif char == ']':
                open_count['['] = max(0, open_count['['] - 1)
            elif char == '}':
                open_count['{'] = max(0, open_count['{'] - 1)
        
        # 补全括号（先补对象，再补数组）
        for _ in range(open_count['{']):
            text += '\n}'
        for _ in range(open_count['[']):
            text += '\n]'
        
        logger.info(f"Added {open_count['{']} '}}' and {open_count['[']} ']' to close JSON")
    
    return text

