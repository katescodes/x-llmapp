"""
Summary 回填工具
从语义目录节点自动回填 summary 到项目目录节点
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple


def _normalize_title(title: str) -> str:
    """
    标题归一化：去除编号前缀、统一空白、转小写
    
    Args:
        title: 原始标题
        
    Returns:
        归一化后的标题
    """
    s = (title or "").strip()
    
    # 统一空白
    s = re.sub(r"\s+", " ", s)
    
    # 去除常见编号前缀
    # 1.2.3 章节编号
    s = re.sub(r"^\s*\d+(\.\d+){0,5}\s*", "", s)
    # 中文序号：一、二、三、
    s = re.sub(r"^\s*[一二三四五六七八九十]+、\s*", "", s)
    # 章节：第X章
    s = re.sub(r"^\s*第[一二三四五六七八九十\d]+章\s*", "", s)
    # 节：第X节
    s = re.sub(r"^\s*第[一二三四五六七八九十\d]+节\s*", "", s)
    
    return s.lower()


def _calculate_similarity(str1: str, str2: str) -> float:
    """
    计算两个字符串的相似度（0~1）
    
    Args:
        str1: 字符串1
        str2: 字符串2
        
    Returns:
        相似度（0~1）
    """
    return SequenceMatcher(None, str1, str2).ratio()


def build_semantic_index(
    semantic_rows: List[Dict[str, Any]]
) -> Tuple[Dict[str, str], List[Tuple[str, str]]]:
    """
    构建语义目录索引
    
    Args:
        semantic_rows: 从 tender_semantic_outline_nodes 查询的记录
        
    Returns:
        元组 (by_numbering, title_list)
        - by_numbering: numbering -> summary 映射（用于精确匹配）
        - title_list: [(normalized_title, summary)] 列表（用于相似度匹配）
    """
    by_numbering: Dict[str, str] = {}
    title_list: List[Tuple[str, str]] = []
    
    for row in semantic_rows:
        summary = (row.get("summary") or "").strip()
        if not summary:
            continue
        
        # 构建 numbering 索引（精确匹配）
        numbering = (row.get("numbering") or "").strip()
        if numbering and numbering not in by_numbering:
            by_numbering[numbering] = summary
        
        # 构建 title 索引（相似度匹配）
        title = (row.get("title") or "").strip()
        if title:
            normalized = _normalize_title(title)
            title_list.append((normalized, summary))
    
    return by_numbering, title_list


def backfill_directory_meta_summary(
    directory_rows: List[Dict[str, Any]],
    semantic_rows: List[Dict[str, Any]],
    *,
    min_title_similarity: float = 0.86,
    force_overwrite: bool = False,
) -> List[Dict[str, Any]]:
    """
    回填目录节点的 summary
    
    策略：
    1. 如果节点的 meta_json.summary 已存在且 force_overwrite=False，跳过
    2. 优先使用 numbering 精确匹配
    3. 如果 numbering 无法匹配，使用 title 相似度匹配（阈值默认 0.86）
    
    Args:
        directory_rows: 从 tender_directory_nodes 查询的记录
        semantic_rows: 从 tender_semantic_outline_nodes 查询的记录
        min_title_similarity: title 相似度阈值（默认 0.86）
        force_overwrite: 是否强制覆盖已有的 summary
        
    Returns:
        需要更新的记录列表，格式: [{"id": node_id, "meta_json": new_meta_json}]
    """
    # 构建语义目录索引
    by_numbering, title_list = build_semantic_index(semantic_rows)
    
    updates: List[Dict[str, Any]] = []
    
    for row in directory_rows:
        # 获取当前 meta_json
        meta = row.get("meta_json") or {}
        if isinstance(meta, str):
            import json
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        
        # 检查是否已有 summary
        current_summary = (meta.get("summary") or "").strip()
        if current_summary and not force_overwrite:
            continue  # 已有 summary 且不强制覆盖，跳过
        
        numbering = (row.get("numbering") or "").strip()
        title = (row.get("title") or "").strip()
        
        new_summary: Optional[str] = None
        match_method: Optional[str] = None
        
        # 策略1: numbering 精确匹配
        if numbering and numbering in by_numbering:
            new_summary = by_numbering[numbering]
            match_method = "numbering_exact"
        
        # 策略2: title 相似度匹配（兜底）
        if not new_summary and title and title_list:
            normalized_title = _normalize_title(title)
            best_score = 0.0
            best_summary = None
            
            for candidate_title, candidate_summary in title_list:
                score = _calculate_similarity(normalized_title, candidate_title)
                if score > best_score:
                    best_score = score
                    best_summary = candidate_summary
            
            if best_summary and best_score >= min_title_similarity:
                new_summary = best_summary
                match_method = f"title_similarity_{best_score:.2f}"
        
        # 如果找到了新的 summary，记录更新
        if new_summary:
            new_meta = dict(meta)
            new_meta["summary"] = new_summary
            new_meta["summary_source"] = "semantic_backfill"
            new_meta["summary_match_method"] = match_method
            
            updates.append({
                "id": row["id"],
                "meta_json": new_meta,
                "old_summary": current_summary,
                "new_summary": new_summary,
                "match_method": match_method,
            })
    
    return updates


def get_backfill_statistics(updates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    统计回填结果
    
    Args:
        updates: backfill_directory_meta_summary 的返回值
        
    Returns:
        统计信息
    """
    total = len(updates)
    by_numbering = sum(1 for u in updates if u.get("match_method") == "numbering_exact")
    by_title = sum(1 for u in updates if u.get("match_method", "").startswith("title_similarity"))
    
    return {
        "total_updated": total,
        "matched_by_numbering": by_numbering,
        "matched_by_title": by_title,
        "updated_node_ids": [u["id"] for u in updates],
    }

