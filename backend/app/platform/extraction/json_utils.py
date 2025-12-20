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
    text = text.strip()
    
    # 尝试提取 ```json ... ``` 中的内容
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()
    
    # 解析 JSON
    return json.loads(text)


def repair_json(text: str) -> Any:
    """
    尝试修复常见的 JSON 格式问题
    
    包括：
    - 单引号替换为双引号
    - 去除首尾空白
    
    Args:
        text: 待修复的文本
        
    Returns:
        解析后的 Python 对象
        
    Raises:
        json.JSONDecodeError: 如果修复后仍无法解析
    """
    text = text.strip()
    
    # 尝试修复常见问题 - 全局替换单引号为双引号
    if "'" in text:
        text = text.replace("'", '"')
    
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to repair JSON: {e}")
        logger.debug(f"Problematic text: {text[:500]}")
        raise

