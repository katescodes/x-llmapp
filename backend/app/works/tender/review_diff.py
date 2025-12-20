"""
审核结果差异对比工具 - Step 8
用于对比旧审核和 v2 审核的结果差异
"""
from typing import Any, Dict, List


def compare_review_results(old_results: List[Dict[str, Any]], new_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    对比审核结果的差异
    
    比较维度：
    1. 审核项数量
    2. dimension 分布
    3. result (pass/risk/fail) 分布
    4. requirement_text 和 response_text 的相似度（简化为前缀对比）
    
    Args:
        old_results: 旧审核结果列表
        new_results: v2 审核结果列表
    
    Returns:
        差异汇总字典
    """
    diff = {}
    
    # 1. 对比审核项数量
    old_count = len(old_results)
    new_count = len(new_results)
    
    if old_count != new_count:
        diff["count_diff"] = {
            "old": old_count,
            "new": new_count,
            "delta": new_count - old_count
        }
    
    # 2. 对比 dimension 分布
    old_dimensions = {}
    for item in old_results:
        dim = item.get("dimension", "其他")
        old_dimensions[dim] = old_dimensions.get(dim, 0) + 1
    
    new_dimensions = {}
    for item in new_results:
        dim = item.get("dimension", "其他")
        new_dimensions[dim] = new_dimensions.get(dim, 0) + 1
    
    if old_dimensions != new_dimensions:
        diff["dimension_distribution"] = {
            "old": old_dimensions,
            "new": new_dimensions
        }
    
    # 3. 对比 result 分布
    old_results_dist = {}
    for item in old_results:
        result = item.get("result", "unknown")
        old_results_dist[result] = old_results_dist.get(result, 0) + 1
    
    new_results_dist = {}
    for item in new_results:
        result = item.get("result", "unknown")
        new_results_dist[result] = new_results_dist.get(result, 0) + 1
    
    if old_results_dist != new_results_dist:
        diff["result_distribution"] = {
            "old": old_results_dist,
            "new": new_results_dist
        }
    
    # 4. 对比 requirement_text 的文本相似度（简化版：提取所有 requirement 的前50字符做集合对比）
    old_requirements = set()
    for item in old_results:
        req = item.get("requirement_text", "")
        if req:
            # 取前50字符作为 hash（避免完整文本泄露）
            old_requirements.add(req[:50].strip())
    
    new_requirements = set()
    for item in new_results:
        req = item.get("requirement_text", "")
        if req:
            new_requirements.add(req[:50].strip())
    
    # 计算要求覆盖的差异
    req_only_in_old = old_requirements - new_requirements
    req_only_in_new = new_requirements - old_requirements
    
    if req_only_in_old or req_only_in_new:
        diff["requirement_coverage"] = {
            "only_in_old_count": len(req_only_in_old),
            "only_in_new_count": len(req_only_in_new),
            "common_count": len(old_requirements & new_requirements),
            "only_in_old_samples": list(req_only_in_old)[:3],  # 最多3个样例
            "only_in_new_samples": list(req_only_in_new)[:3]
        }
    
    # 5. 计算总体相似度得分（简化版）
    if old_count > 0 and new_count > 0:
        # 维度相似度
        dimension_similarity = _calculate_distribution_similarity(old_dimensions, new_dimensions)
        
        # 结果相似度
        result_similarity = _calculate_distribution_similarity(old_results_dist, new_results_dist)
        
        # 覆盖率相似度
        common_reqs = len(old_requirements & new_requirements)
        total_reqs = len(old_requirements | new_requirements)
        coverage_similarity = common_reqs / total_reqs if total_reqs > 0 else 0
        
        # 综合相似度（加权平均）
        overall_similarity = (
            dimension_similarity * 0.3 +
            result_similarity * 0.4 +
            coverage_similarity * 0.3
        )
        
        diff["similarity_scores"] = {
            "dimension_similarity": round(dimension_similarity, 3),
            "result_similarity": round(result_similarity, 3),
            "coverage_similarity": round(coverage_similarity, 3),
            "overall_similarity": round(overall_similarity, 3)
        }
    
    # 6. 判断是否有显著差异
    has_significant_diff = (
        abs(old_count - new_count) > max(old_count, new_count) * 0.2 or  # 数量差异 > 20%
        (diff.get("similarity_scores", {}).get("overall_similarity", 1.0) < 0.7)  # 相似度 < 70%
    )
    
    diff["has_significant_diff"] = has_significant_diff
    
    return diff


def _calculate_distribution_similarity(dist1: Dict[str, int], dist2: Dict[str, int]) -> float:
    """
    计算两个分布的相似度（使用余弦相似度）
    
    Args:
        dist1: 第一个分布（类别 -> 计数）
        dist2: 第二个分布（类别 -> 计数）
    
    Returns:
        相似度分数 [0, 1]
    """
    if not dist1 or not dist2:
        return 0.0
    
    # 获取所有类别
    all_keys = set(dist1.keys()) | set(dist2.keys())
    
    if not all_keys:
        return 1.0
    
    # 构建向量
    vec1 = [dist1.get(k, 0) for k in all_keys]
    vec2 = [dist2.get(k, 0) for k in all_keys]
    
    # 计算余弦相似度
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = sum(a * a for a in vec1) ** 0.5
    magnitude2 = sum(b * b for b in vec2) ** 0.5
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    
    similarity = dot_product / (magnitude1 * magnitude2)
    
    return max(0.0, min(1.0, similarity))  # 确保在 [0, 1] 范围内

