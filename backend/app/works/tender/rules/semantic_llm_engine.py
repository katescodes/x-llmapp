"""
语义LLM规则引擎 (Semantic LLM Rule Engine)

使用LLM进行语义判断的审核规则
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SemanticLLMRuleEngine:
    """语义LLM规则引擎"""
    
    def __init__(self, llm_orchestrator: Any):
        """
        初始化语义LLM规则引擎
        
        Args:
            llm_orchestrator: LLM编排器
        """
        self.llm = llm_orchestrator
    
    async def evaluate_rules(
        self,
        rules: List[Dict[str, Any]],
        requirements: List[Dict[str, Any]],
        responses: List[Dict[str, Any]],
        model_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        评估语义LLM规则
        
        使用LLM进行语义判断，适用于：
        - 技术方案的完整性和可行性
        - 商务条款的合理性
        - 资格证明的有效性（需要人工解读）
        
        Args:
            rules: 语义LLM规则列表
            requirements: 招标要求列表
            responses: 投标响应列表
            model_id: LLM模型ID
        
        Returns:
            审核结果列表
        """
        logger.info(
            f"SemanticLLMEngine: Evaluating {len(rules)} rules, "
            f"{len(requirements)} requirements, {len(responses)} responses"
        )
        
        results = []
        
        # 按维度分组要求和响应
        req_by_dimension = self._group_by_dimension(requirements)
        resp_by_dimension = self._group_by_dimension(responses)
        
        for rule in rules:
            try:
                rule_results = await self._evaluate_single_rule(
                    rule,
                    req_by_dimension,
                    resp_by_dimension,
                    model_id
                )
                results.extend(rule_results)
            except Exception as e:
                logger.error(
                    f"SemanticLLMEngine: Failed to evaluate rule {rule['rule_key']}: {e}",
                    exc_info=True
                )
        
        logger.info(f"SemanticLLMEngine: Generated {len(results)} review results")
        return results
    
    async def _evaluate_single_rule(
        self,
        rule: Dict[str, Any],
        req_by_dimension: Dict[str, List[Dict[str, Any]]],
        resp_by_dimension: Dict[str, List[Dict[str, Any]]],
        model_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        """评估单个语义LLM规则"""
        condition = rule.get("condition_json", {})
        action = rule.get("action_json", {})
        
        # 获取规则适用的维度
        target_dimension = condition.get("dimension", "technical")
        
        reqs = req_by_dimension.get(target_dimension, [])
        resps = resp_by_dimension.get(target_dimension, [])
        
        if not reqs or not resps:
            logger.info(
                f"SemanticLLMEngine: Skipping rule {rule['rule_key']} - "
                f"no requirements or responses for dimension '{target_dimension}'"
            )
            return []
        
        # 构建LLM prompt
        prompt = self._build_semantic_prompt(rule, reqs, resps)
        
        # 调用LLM
        if not self.llm:
            logger.warning("SemanticLLMEngine: No LLM orchestrator available, skipping")
            return []
        
        try:
            # TODO: 实际调用LLM
            # llm_response = await self.llm.chat(
            #     messages=[{"role": "user", "content": prompt}],
            #     model_id=model_id,
            #     temperature=0.0
            # )
            # result_text = llm_response.get("content", "")
            
            # 暂时返回空结果（待集成实际LLM调用）
            logger.info(
                f"SemanticLLMEngine: Would call LLM for rule {rule['rule_key']} "
                f"(prompt length={len(prompt)})"
            )
            return []
        
        except Exception as e:
            logger.error(f"SemanticLLMEngine: LLM call failed: {e}", exc_info=True)
            return []
    
    def _build_semantic_prompt(
        self,
        rule: Dict[str, Any],
        requirements: List[Dict[str, Any]],
        responses: List[Dict[str, Any]],
    ) -> str:
        """构建语义判断prompt"""
        condition = rule.get("condition_json", {})
        
        prompt_parts = [
            f"# 审核规则：{rule['name']}",
            f"规则描述：{rule.get('description', '')}",
            "",
            "## 招标要求",
        ]
        
        for req in requirements[:5]:  # 限制前5个要求
            prompt_parts.append(f"- [{req['requirement_id']}] {req.get('requirement_text', '')[:200]}")
        
        prompt_parts.extend([
            "",
            "## 投标响应",
        ])
        
        for resp in responses[:5]:  # 限制前5个响应
            prompt_parts.append(f"- [{resp.get('response_id', 'N/A')}] {resp.get('response_text', '')[:200]}")
        
        prompt_parts.extend([
            "",
            "## 判断任务",
            condition.get("llm_instruction", "请判断投标响应是否满足招标要求"),
            "",
            "请以JSON格式输出结果：",
            "{",
            '  "result": "PASS" | "FAIL" | "WARN",',
            '  "reason": "判断理由",',
            '  "matched_requirement_ids": ["req_001", ...],',
            '  "matched_response_ids": ["resp_001", ...]',
            "}"
        ])
        
        return "\n".join(prompt_parts)
    
    def _group_by_dimension(self, items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """按维度分组"""
        grouped = {}
        for item in items:
            dimension = item.get("dimension", "other")
            if dimension not in grouped:
                grouped[dimension] = []
            grouped[dimension].append(item)
        return grouped

