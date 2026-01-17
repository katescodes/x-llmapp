"""
范文章节匹配器
将提取的格式范文匹配到投标书目录节点
"""
from __future__ import annotations
import re
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# 同义词组（不断扩充）
SYNONYM_GROUPS = {
    "投标函": ["投标函", "投标函及投标函附录", "响应函", "投标函及承诺", "投标申请函"],
    "授权书": ["授权书", "授权委托书", "法人授权书", "法人授权委托书", "法定代表人授权书", "法定代表人授权委托书"],
    "报价表": ["报价表", "报价一览表", "投标报价表", "报价明细表", "分项报价表", "工程量清单报价表"],
    "营业执照": ["营业执照", "营业执照副本", "企业营业执照"],
    "资质证书": ["资质证书", "企业资质证书", "相关资质证书"],
    "业绩表": ["业绩表", "类似业绩表", "项目业绩表", "近三年业绩", "近年业绩"],
    "承诺书": ["承诺书", "投标承诺书", "质量承诺书", "服务承诺书"],
    "保证金": ["保证金", "投标保证金", "投标保证金承诺"],
}

# 核心关键词提取
CORE_KEYWORDS = [
    "投标函", "授权", "报价", "营业执照", "资质", "业绩",
    "承诺", "保证金", "技术方案", "实施方案", "项目理解"
]


def normalize_title(title: str) -> str:
    """
    标题归一化
    - 去除编号
    - 去除修饰词
    - 去除所有空格
    - 统一格式
    """
    if not title:
        return ""
    
    # 去除前导编号（如 "1."、"1.1"、"（一）"等）
    title = re.sub(r'^[\d一二三四五六七八九十]+[\.)、\s]+', '', title)
    title = re.sub(r'^[（\(][一二三四五六七八九十\d]+[）\)]\s*', '', title)
    
    # 去除常见修饰词
    title = title.replace("格式", "").replace("范本", "").replace("样式", "")
    title = title.replace("附件", "").replace("：", "").replace(":", "")
    
    # 去除括号内容（如 "投标函（格式）" -> "投标函"）
    title = re.sub(r'[（\(].*?[）\)]', '', title)
    
    # ✅ 去除所有空格（解决"投 标 函"与"投标函"匹配问题）
    title = re.sub(r'\s+', '', title)
    
    return title.strip()


def extract_keywords(title: str) -> List[str]:
    """
    从标题中提取关键词
    """
    keywords = []
    normalized = normalize_title(title)
    
    for keyword in CORE_KEYWORDS:
        if keyword in normalized:
            keywords.append(keyword)
    
    return keywords


def find_synonym_group(title: str) -> Optional[str]:
    """
    查找标题所属的同义词组
    返回组的代表词（第一个词）
    """
    normalized = normalize_title(title)
    
    for group_key, synonyms in SYNONYM_GROUPS.items():
        for synonym in synonyms:
            if synonym in normalized or normalized in synonym:
                return group_key
    
    return None


def calculate_similarity(snippet_title: str, node_title: str) -> Tuple[float, str]:
    """
    计算两个标题的相似度
    
    返回: (相似度分数, 匹配类型)
    - 1.0: 精确匹配
    - 0.9: 同义词匹配
    - 0.7: 关键词匹配
    - 0.0: 无匹配
    """
    # 归一化
    snippet_norm = normalize_title(snippet_title)
    node_norm = normalize_title(node_title)
    
    # 精确匹配
    if snippet_norm == node_norm:
        return 1.0, "exact"
    
    # 同义词匹配
    snippet_group = find_synonym_group(snippet_title)
    node_group = find_synonym_group(node_title)
    
    if snippet_group and node_group and snippet_group == node_group:
        return 0.9, "synonym"
    
    # 关键词匹配
    snippet_keywords = set(extract_keywords(snippet_title))
    node_keywords = set(extract_keywords(node_title))
    
    if snippet_keywords and node_keywords:
        common = snippet_keywords & node_keywords
        if common:
            # 计算交集比例
            ratio = len(common) / max(len(snippet_keywords), len(node_keywords))
            if ratio >= 0.5:
                return 0.7 * ratio, "keyword"
    
    # 包含关系
    if snippet_norm in node_norm or node_norm in snippet_norm:
        return 0.6, "contains"
    
    return 0.0, "none"


def match_snippets_to_nodes(
    snippets: List[Dict[str, Any]],
    directory_nodes: List[Dict[str, Any]],
    confidence_threshold: float = 0.7
) -> Dict[str, Any]:
    """
    将范文匹配到目录节点
    
    Args:
        snippets: 范文列表 [{id, title, ...}]
        directory_nodes: 目录节点列表 [{id, title, level, ...}]
        confidence_threshold: 置信度阈值（低于此值不匹配）
    
    Returns:
        {
            matches: [
                {
                    node_id, node_title,
                    snippet_id, snippet_title,
                    confidence, match_type
                }
            ],
            unmatched_nodes: [node_id, ...],
            unmatched_snippets: [snippet_id, ...],
            stats: {...}
        }
    """
    matches = []
    matched_node_ids = set()
    matched_snippet_ids = set()
    
    logger.info(f"开始匹配: {len(snippets)} 个范文 -> {len(directory_nodes)} 个节点")
    
    # 为每个节点找最佳匹配的范文
    for node in directory_nodes:
        node_id = node.get("id")
        node_title = node.get("title", "")
        
        if not node_title:
            continue
        
        best_match = None
        best_score = 0.0
        best_type = "none"
        
        # 尝试匹配所有范文
        for snippet in snippets:
            snippet_id = snippet.get("id")
            snippet_title = snippet.get("title", "")
            
            if not snippet_title:
                continue
            
            # 计算相似度
            score, match_type = calculate_similarity(snippet_title, node_title)
            
            # 更新最佳匹配
            if score > best_score:
                best_score = score
                best_match = snippet
                best_type = match_type
        
        # 如果找到合格的匹配
        if best_match and best_score >= confidence_threshold:
            matches.append({
                "node_id": node_id,
                "node_title": node_title,
                "snippet_id": best_match["id"],
                "snippet_title": best_match["title"],
                "confidence": round(best_score, 2),
                "match_type": best_type
            })
            matched_node_ids.add(node_id)
            matched_snippet_ids.add(best_match["id"])
            
            logger.info(
                f"匹配成功: {node_title} -> {best_match['title']} "
                f"({best_type}, {best_score:.2f})"
            )
    
    # 未匹配的节点和范文
    unmatched_nodes = [
        {"id": n["id"], "title": n.get("title", "")}
        for n in directory_nodes
        if n.get("id") not in matched_node_ids
    ]
    
    unmatched_snippets = [
        {"id": s["id"], "title": s.get("title", "")}
        for s in snippets
        if s.get("id") not in matched_snippet_ids
    ]
    
    # 统计信息
    stats = {
        "total_nodes": len(directory_nodes),
        "total_snippets": len(snippets),
        "matched_count": len(matches),
        "match_rate": round(len(matches) / max(1, len(directory_nodes)), 2),
        "exact_matches": sum(1 for m in matches if m["match_type"] == "exact"),
        "synonym_matches": sum(1 for m in matches if m["match_type"] == "synonym"),
        "keyword_matches": sum(1 for m in matches if m["match_type"] == "keyword"),
    }
    
    logger.info(
        f"匹配完成: {len(matches)} 个匹配 "
        f"(匹配率: {stats['match_rate']*100:.1f}%)"
    )
    
    return {
        "matches": matches,
        "unmatched_nodes": unmatched_nodes,
        "unmatched_snippets": unmatched_snippets,
        "stats": stats
    }


def suggest_manual_matches(
    unmatched_nodes: List[Dict[str, Any]],
    unmatched_snippets: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    为未匹配的节点推荐可能的范文（供用户手动确认）
    
    返回:
    [
        {
            node_id, node_title,
            suggestions: [
                {snippet_id, snippet_title, confidence, reason}
            ]
        }
    ]
    """
    suggestions = []
    
    for node in unmatched_nodes:
        node_id = node.get("id")
        node_title = node.get("title", "")
        
        node_suggestions = []
        
        for snippet in unmatched_snippets:
            snippet_id = snippet.get("id")
            snippet_title = snippet.get("title", "")
            
            # 计算相似度（降低阈值）
            score, match_type = calculate_similarity(snippet_title, node_title)
            
            # 只要有一点相似就推荐（>0.3）
            if score > 0.3:
                node_suggestions.append({
                    "snippet_id": snippet_id,
                    "snippet_title": snippet_title,
                    "confidence": round(score, 2),
                    "reason": match_type
                })
        
        # 按置信度排序
        node_suggestions.sort(key=lambda x: x["confidence"], reverse=True)
        
        # 只保留前3个建议
        if node_suggestions:
            suggestions.append({
                "node_id": node_id,
                "node_title": node_title,
                "suggestions": node_suggestions[:3]
            })
    
    return suggestions


def add_synonym_group(group_key: str, synonyms: List[str]) -> None:
    """
    动态添加同义词组（用于持续优化）
    """
    SYNONYM_GROUPS[group_key] = synonyms
    logger.info(f"添加同义词组: {group_key} = {synonyms}")
