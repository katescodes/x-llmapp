"""
确定性规则引擎 (Deterministic Rule Engine)

基于条件表达式的确定性审核规则
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DeterministicRuleEngine:
    """确定性规则引擎"""
    
    def evaluate_rules(
        self,
        rules: List[Dict[str, Any]],
        requirements: List[Dict[str, Any]],
        responses: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        评估确定性规则
        
        Args:
            rules: 确定性规则列表
            requirements: 招标要求列表（来自 tender_requirements）
            responses: 投标响应列表（来自 tender_bid_response_items）
        
        Returns:
            审核结果列表
            [
                {
                    "rule_id": "rule_001",
                    "requirement_id": "qual_001",
                    "result": "FAIL",
                    "reason": "未提供营业执照",
                    "severity": "critical",
                    "evaluator": "deterministic_engine"
                }
            ]
        """
        logger.info(
            f"DeterministicEngine: Evaluating {len(rules)} rules, "
            f"{len(requirements)} requirements, {len(responses)} responses"
        )
        
        results = []
        
        # 构建快速查找索引
        response_by_dimension = self._index_by_dimension(responses)
        requirement_by_id = {r["requirement_id"]: r for r in requirements}
        
        for rule in rules:
            try:
                rule_results = self._evaluate_single_rule(
                    rule,
                    requirements,
                    responses,
                    requirement_by_id,
                    response_by_dimension
                )
                results.extend(rule_results)
            except Exception as e:
                logger.error(
                    f"DeterministicEngine: Failed to evaluate rule {rule['rule_key']}: {e}",
                    exc_info=True
                )
        
        logger.info(f"DeterministicEngine: Generated {len(results)} review results")
        return results
    
    def _evaluate_single_rule(
        self,
        rule: Dict[str, Any],
        requirements: List[Dict[str, Any]],
        responses: List[Dict[str, Any]],
        requirement_by_id: Dict[str, Dict[str, Any]],
        response_by_dimension: Dict[str, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """评估单个规则"""
        condition = rule.get("condition_json", {})
        action = rule.get("action_json", {})
        
        rule_type = condition.get("type", "check_requirement_response")
        
        if rule_type == "check_requirement_response":
            # 检查要求是否有对应的响应
            return self._check_requirement_response(
                rule, requirements, responses, requirement_by_id, response_by_dimension
            )
        elif rule_type == "check_value_threshold":
            # 检查数值是否满足阈值
            return self._check_value_threshold(
                rule, requirements, responses, requirement_by_id, response_by_dimension
            )
        elif rule_type == "check_document_provided":
            # 检查文档是否提供
            return self._check_document_provided(
                rule, requirements, responses, requirement_by_id, response_by_dimension
            )
        else:
            logger.warning(f"DeterministicEngine: Unknown rule type '{rule_type}'")
            return []
    
    def _check_requirement_response(
        self,
        rule: Dict[str, Any],
        requirements: List[Dict[str, Any]],
        responses: List[Dict[str, Any]],
        requirement_by_id: Dict[str, Dict[str, Any]],
        response_by_dimension: Dict[str, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """检查硬性要求是否有对应的响应"""
        condition = rule.get("condition_json", {})
        action = rule.get("action_json", {})
        
        # 只检查硬性要求（is_hard=true）
        hard_requirements = [r for r in requirements if r.get("is_hard", False)]
        
        results = []
        
        for req in hard_requirements:
            dimension = req.get("dimension", "other")
            req_id = req["requirement_id"]
            
            # 查找对应维度的响应
            dim_responses = response_by_dimension.get(dimension, [])
            
            # 简单匹配：如果该维度有任何响应，视为满足
            # （实际应用中可能需要更复杂的匹配逻辑）
            has_response = len(dim_responses) > 0
            
            if not has_response:
                results.append({
                    "rule_id": rule["id"],
                    "rule_key": rule["rule_key"],
                    "requirement_id": req_id,
                    "result": action.get("result", "FAIL"),
                    "reason": f"未找到对应的响应：{req.get('requirement_text', '')[:100]}",
                    "severity": rule.get("severity", "medium"),
                    "evaluator": "deterministic_engine",
                    "dimension": dimension
                })
        
        return results
    
    def _check_value_threshold(
        self,
        rule: Dict[str, Any],
        requirements: List[Dict[str, Any]],
        responses: List[Dict[str, Any]],
        requirement_by_id: Dict[str, Dict[str, Any]],
        response_by_dimension: Dict[str, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """检查数值阈值（如：价格不超过预算）"""
        condition = rule.get("condition_json", {})
        action = rule.get("action_json", {})
        
        # 示例：检查投标价格是否超过招标控制价
        # 这里需要根据实际业务逻辑实现
        # TODO: 实现具体的数值阈值检查逻辑
        
        return []
    
    def _check_document_provided(
        self,
        rule: Dict[str, Any],
        requirements: List[Dict[str, Any]],
        responses: List[Dict[str, Any]],
        requirement_by_id: Dict[str, Dict[str, Any]],
        response_by_dimension: Dict[str, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """检查必须提供的文档是否齐全"""
        condition = rule.get("condition_json", {})
        action = rule.get("action_json", {})
        
        # 查找所有 req_type='must_provide' 的要求
        must_provide_reqs = [r for r in requirements if r.get("req_type") == "must_provide"]
        
        results = []
        
        for req in must_provide_reqs:
            dimension = req.get("dimension", "qualification")
            req_id = req["requirement_id"]
            
            # 查找对应的文档响应
            dim_responses = response_by_dimension.get(dimension, [])
            doc_responses = [r for r in dim_responses if r.get("response_type") == "document_ref"]
            
            # 检查是否有匹配的文档
            # （实际应用中需要更精确的文档名称匹配）
            has_doc = len(doc_responses) > 0
            
            if not has_doc:
                results.append({
                    "rule_id": rule["id"],
                    "rule_key": rule["rule_key"],
                    "requirement_id": req_id,
                    "result": action.get("result", "FAIL"),
                    "reason": f"缺少必须提供的文档：{req.get('requirement_text', '')[:100]}",
                    "severity": rule.get("severity", "high"),
                    "evaluator": "deterministic_engine",
                    "dimension": dimension
                })
        
        return results
    
    def _index_by_dimension(self, responses: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """按维度索引响应"""
        index = {}
        for resp in responses:
            dimension = resp.get("dimension", "other")
            if dimension not in index:
                index[dimension] = []
            index[dimension].append(resp)
        return index

