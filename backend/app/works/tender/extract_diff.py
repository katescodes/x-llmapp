"""
抽取结果差异对比工具 - Step 6
用于 SHADOW 模式下对比新旧抽取结果
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def compare_project_info(
    old_result: Dict[str, Any],
    new_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    对比项目信息抽取结果
    
    Returns:
        {
            "keys_diff": {...},
            "values_diff": {...},
            "evidence_diff": {...}
        }
    """
    old_data = old_result.get("data") or {}
    new_data = new_result.get("data") or {}
    
    old_evidence = old_result.get("evidence_chunk_ids") or []
    new_evidence = new_result.get("evidence_chunk_ids") or []
    
    # 1. 对比 key 集合
    old_keys = set(old_data.keys())
    new_keys = set(new_data.keys())
    
    keys_diff = {
        "only_in_old": list(old_keys - new_keys),
        "only_in_new": list(new_keys - old_keys),
        "common": list(old_keys & new_keys)
    }
    
    # 2. 对比关键字段值（忽略空白和格式）
    values_diff = {}
    for key in keys_diff["common"]:
        old_val = str(old_data.get(key, "")).strip()
        new_val = str(new_data.get(key, "")).strip()
        
        if old_val != new_val:
            values_diff[key] = {
                "old": old_val[:100],  # 截断以节省空间
                "new": new_val[:100],
                "length_old": len(old_val),
                "length_new": len(new_val)
            }
    
    # 3. 对比证据
    evidence_diff = {
        "old_count": len(old_evidence),
        "new_count": len(new_evidence),
        "only_in_old": len(set(old_evidence) - set(new_evidence)),
        "only_in_new": len(set(new_evidence) - set(old_evidence)),
        "common": len(set(old_evidence) & set(new_evidence))
    }
    
    return {
        "keys_diff": keys_diff,
        "values_diff": values_diff,
        "evidence_diff": evidence_diff,
        "has_significant_diff": len(values_diff) > 0 or len(keys_diff["only_in_old"]) > 0 or len(keys_diff["only_in_new"]) > 0
    }


def compare_risks(
    old_results: List[Dict[str, Any]],
    new_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    对比风险识别结果
    
    Returns:
        {
            "count_diff": {...},
            "title_diff": {...},
            "severity_diff": {...}
        }
    """
    # 1. 对比数量
    count_diff = {
        "old_count": len(old_results),
        "new_count": len(new_results),
        "diff": len(new_results) - len(old_results)
    }
    
    # 2. 对比 title 集合
    old_titles = set(r.get("title", "").strip() for r in old_results)
    new_titles = set(r.get("title", "").strip() for r in new_results)
    
    title_diff = {
        "only_in_old": list(old_titles - new_titles),
        "only_in_new": list(new_titles - old_titles),
        "common": list(old_titles & new_titles)
    }
    
    # 3. 对比 severity 分布
    old_severity_counts = {}
    for r in old_results:
        sev = r.get("severity", "medium")
        old_severity_counts[sev] = old_severity_counts.get(sev, 0) + 1
    
    new_severity_counts = {}
    for r in new_results:
        sev = r.get("severity", "medium")
        new_severity_counts[sev] = new_severity_counts.get(sev, 0) + 1
    
    severity_diff = {
        "old": old_severity_counts,
        "new": new_severity_counts
    }
    
    # 4. 对比 risk_type 分布
    old_type_counts = {}
    for r in old_results:
        rt = r.get("risk_type", "其他")
        old_type_counts[rt] = old_type_counts.get(rt, 0) + 1
    
    new_type_counts = {}
    for r in new_results:
        rt = r.get("risk_type", "其他")
        new_type_counts[rt] = new_type_counts.get(rt, 0) + 1
    
    type_diff = {
        "old": old_type_counts,
        "new": new_type_counts
    }
    
    return {
        "count_diff": count_diff,
        "title_diff": title_diff,
        "severity_diff": severity_diff,
        "type_diff": type_diff,
        "has_significant_diff": abs(count_diff["diff"]) > 1 or len(title_diff["only_in_old"]) > 2 or len(title_diff["only_in_new"]) > 2
    }

