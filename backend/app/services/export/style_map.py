"""
样式映射工具
从模板配置中读取标题和正文样式映射
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def load_heading_style_map(style_config_json: Optional[Dict[str, Any]]) -> Dict[int, str]:
    """
    从 style_config_json 中加载标题样式映射
    
    期望格式：
    {
      "heading_style_map": {
        "1": "标题 1",
        "2": "标题 2",
        "3": "标题 3",
        "4": "标题 4",
        "5": "标题 5"
      }
    }
    
    Args:
        style_config_json: 模板的样式配置 JSON
        
    Returns:
        层级 -> 样式名称的映射（如 {1: "标题 1", 2: "标题 2"}）
    """
    if not style_config_json:
        return {}
    
    heading_map_raw = style_config_json.get("heading_style_map") or {}
    
    out: Dict[int, str] = {}
    for k, v in heading_map_raw.items():
        try:
            # 将字符串 key 转为 int
            level = int(k)
        except (ValueError, TypeError):
            continue
        
        # 验证 value 是有效的样式名称
        if isinstance(v, str) and v.strip():
            out[level] = v.strip()
    
    return out


def load_normal_style(style_config_json: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    从 style_config_json 中加载正文样式名称
    
    期望格式：
    {
      "normal_style": "正文"
    }
    
    Args:
        style_config_json: 模板的样式配置 JSON
        
    Returns:
        正文样式名称，如果未配置则返回 None
    """
    if not style_config_json:
        return None
    
    style = style_config_json.get("normal_style")
    
    if isinstance(style, str) and style.strip():
        return style.strip()
    
    return None


def get_style_config_from_template(template_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    从模板信息中提取 style_config_json
    
    兼容两种存储方式：
    1. style_config (旧字段)
    2. style_config_json (新字段)
    
    Args:
        template_info: 从数据库查询的模板记录
        
    Returns:
        style_config 字典，如果不存在则返回 None
    """
    import json
    
    # 优先使用 style_config_json
    style_config = template_info.get("style_config_json")
    
    # 兼容旧字段 style_config
    if not style_config:
        style_config = template_info.get("style_config")
    
    # 如果是字符串，解析为 JSON
    if isinstance(style_config, str) and style_config.strip():
        try:
            style_config = json.loads(style_config)
        except json.JSONDecodeError:
            return None
    
    # 验证是字典
    if isinstance(style_config, dict):
        return style_config
    
    return None

