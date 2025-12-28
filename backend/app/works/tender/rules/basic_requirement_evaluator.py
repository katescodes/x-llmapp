"""
基础要求评估器 (Basic Requirement Evaluator)

不依赖自定义规则，直接评估招标要求与投标响应的匹配关系
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class BasicRequirementEvaluator:
    """
    基础要求评估器
    
    功能：
    1. 检查每个招标要求是否有对应的投标响应
    2. 对于硬性要求（is_hard=True），没有响应则FAIL
    3. 对于非硬性要求，没有响应则WARN
    4. 有响应的情况下，初步判断响应的完整性
    """
    
    def evaluate_requirements(
        self,
        requirements: List[Dict[str, Any]],
        responses: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        评估招标要求与投标响应的匹配情况
        
        Args:
            requirements: 招标要求列表（来自 tender_requirements）
            responses: 投标响应列表（来自 tender_bid_response_items）
        
        Returns:
            审核结果列表
            [
                {
                    "requirement_id": "business_001",
                    "requirement_text": "不得转包、分包的承诺",
                    "dimension": "business",
                    "is_hard": True,
                    "has_response": True,
                    "response_count": 1,
                    "result": "PASS" | "FAIL" | "WARN",
                    "reason": "已提供响应",
                    "severity": "critical" | "high" | "medium" | "low",
                    "evaluator": "basic_requirement_evaluator"
                }
            ]
        """
        logger.info(
            f"BasicRequirementEvaluator: Evaluating {len(requirements)} requirements "
            f"against {len(responses)} responses"
        )
        
        # 1. 按维度索引响应
        response_by_dimension = self._index_responses_by_dimension(responses)
        
        # 2. 评估每个要求
        results = []
        for req in requirements:
            result = self._evaluate_single_requirement(req, response_by_dimension)
            results.append(result)
        
        # 3. 统计
        pass_count = sum(1 for r in results if r["result"] == "PASS")
        fail_count = sum(1 for r in results if r["result"] == "FAIL")
        warn_count = sum(1 for r in results if r["result"] == "WARN")
        
        logger.info(
            f"BasicRequirementEvaluator: Generated {len(results)} results "
            f"(PASS={pass_count}, FAIL={fail_count}, WARN={warn_count})"
        )
        
        return results
    
    def _index_responses_by_dimension(
        self, responses: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """按维度索引响应"""
        index = {}
        for resp in responses:
            dimension = resp.get("dimension", "unknown")
            if dimension not in index:
                index[dimension] = []
            index[dimension].append(resp)
        return index
    
    def _evaluate_single_requirement(
        self,
        requirement: Dict[str, Any],
        response_by_dimension: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """评估单个招标要求"""
        req_id = requirement.get("requirement_id", "unknown")
        req_text = requirement.get("requirement_text", "")
        dimension = requirement.get("dimension", "unknown")
        is_hard = requirement.get("is_hard", False)
        
        # 查找该维度的响应
        dimension_responses = response_by_dimension.get(dimension, [])
        
        # 基础判断：是否有响应
        has_response = len(dimension_responses) > 0
        response_count = len(dimension_responses)
        
        # 确定结果
        if not has_response:
            # 没有响应
            if is_hard:
                result = "FAIL"
                reason = f"硬性要求未响应：{req_text[:50]}"
                severity = "critical"
            else:
                result = "WARN"
                reason = f"建议性要求未响应：{req_text[:50]}"
                severity = "medium"
        else:
            # 有响应 - 基础检查响应的完整性
            total_response_length = sum(len(r.get("response_text", "")) for r in dimension_responses)
            
            # 简单启发式：响应文本长度 < 10字符，认为响应不完整
            if total_response_length < 10:
                result = "WARN"
                reason = f"响应过于简短（{total_response_length}字符），可能不完整"
                severity = "medium"
            else:
                result = "PASS"
                reason = f"已提供{response_count}条响应，总长度{total_response_length}字符"
                severity = "low"
        
        return {
            "requirement_id": req_id,
            "requirement_text": req_text,
            "dimension": dimension,
            "is_hard": is_hard,
            "has_response": has_response,
            "response_count": response_count,
            "result": result,
            "reason": reason,
            "severity": severity,
            "evaluator": "basic_requirement_evaluator",
            "rule_key": f"basic_req_{dimension}",
            "rule_name": f"基础要求匹配检查 - {dimension}"
        }

