"""
按维度批量LLM语义审核器

使用LLM进行语义判断，按维度批量处理以提高效率：
- 一次处理一个维度的所有要求和响应
- 减少LLM调用次数（69次 → 3-5次）
- 降低成本和提高速度
"""
import asyncio
import json
import logging
import numpy as np
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class DimensionBatchLLMReviewer:
    """按维度批量LLM审核器"""
    
    def __init__(self, llm_orchestrator: Any = None, embedding_provider: Any = None):
        """
        初始化审核器
        
        Args:
            llm_orchestrator: LLM编排器（用于语义判断）
            embedding_provider: Embedding提供者（用于向量相似度计算）
        """
        self.llm = llm_orchestrator
        self.embedding_provider = embedding_provider
    
    async def review(
        self,
        requirements: List[Dict[str, Any]],
        responses: List[Dict[str, Any]],
        model_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        执行LLM语义审核
        
        Args:
            requirements: 招标要求列表
            responses: 投标响应列表
            model_id: LLM模型ID
            
        Returns:
            审核结果列表
        """
        logger.info(
            f"DimensionBatchLLMReviewer: Starting review with {len(requirements)} requirements "
            f"and {len(responses)} responses"
        )
        
        # 1. 按维度分组
        dimensions = self._group_by_dimension(requirements, responses)
        logger.info(f"DimensionBatchLLMReviewer: Grouped into {len(dimensions)} dimensions")
        
        # 2. 处理每个维度
        all_results = []
        
        for dim_name, dim_data in dimensions.items():
            logger.info(
                f"DimensionBatchLLMReviewer: Processing dimension '{dim_name}' "
                f"({len(dim_data['requirements'])} requirements, {len(dim_data['responses'])} responses)"
            )
            
            if len(dim_data['responses']) == 0:
                # 无响应，快速判断
                results = self._quick_judge_no_response(dim_data)
                logger.info(f"DimensionBatchLLMReviewer: Dimension '{dim_name}' has no responses, quick judged {len(results)} items")
            else:
                # 有响应，使用LLM判断
                try:
                    results = await self._llm_judge_dimension(dim_name, dim_data, model_id)
                    logger.info(f"DimensionBatchLLMReviewer: Dimension '{dim_name}' LLM judged {len(results)} items")
                except Exception as e:
                    logger.error(f"DimensionBatchLLMReviewer: Failed to judge dimension '{dim_name}': {e}", exc_info=True)
                    # 降级到快速判断
                    results = self._fallback_judge(dim_data)
                    logger.warning(f"DimensionBatchLLMReviewer: Dimension '{dim_name}' fallback judged {len(results)} items")
            
            all_results.extend(results)
        
        logger.info(f"DimensionBatchLLMReviewer: Completed review with {len(all_results)} total results")
        return all_results
    
    def _group_by_dimension(
        self,
        requirements: List[Dict[str, Any]],
        responses: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, List]]:
        """按维度分组"""
        dimensions = {}
        
        # 收集所有维度
        all_dims = set()
        for req in requirements:
            all_dims.add(req.get("dimension", "other"))
        for resp in responses:
            all_dims.add(resp.get("dimension", "other"))
        
        # 分组
        for dim in all_dims:
            dimensions[dim] = {
                "requirements": [r for r in requirements if r.get("dimension") == dim],
                "responses": [r for r in responses if r.get("dimension") == dim]
            }
        
        return dimensions
    
    def _quick_judge_no_response(self, dim_data: Dict[str, List]) -> List[Dict[str, Any]]:
        """快速判断无响应的维度"""
        results = []
        
        for req in dim_data['requirements']:
            is_hard = req.get("is_hard", False)
            
            results.append({
                "requirement_id": req.get("requirement_id"),
                "requirement_text": req.get("requirement_text", ""),
                "dimension": req.get("dimension", "other"),
                "is_hard": is_hard,
                "matched_response_id": None,
                "matched_response_text": None,
                "match_score": 0,
                "judgment": "FAIL" if is_hard else "WARN",
                "reason": f"{'硬性要求' if is_hard else '建议性要求'}未提供响应",
                "evidence": None,
                "confidence": 1.0,
                "evaluator": "llm_semantic_no_response"
            })
        
        return results
    
    def _fallback_judge(self, dim_data: Dict[str, List]) -> List[Dict[str, Any]]:
        """降级判断（当LLM失败时）"""
        results = []
        
        for req in dim_data['requirements']:
            is_hard = req.get("is_hard", False)
            has_response = len(dim_data['responses']) > 0
            
            if has_response:
                # 有响应，但无法使用LLM判断，给WARN
                results.append({
                    "requirement_id": req.get("requirement_id"),
                    "requirement_text": req.get("requirement_text", ""),
                    "dimension": req.get("dimension", "other"),
                    "is_hard": is_hard,
                    "matched_response_id": None,
                    "matched_response_text": None,
                    "match_score": 50,
                    "judgment": "WARN",
                    "reason": "该维度有响应，但LLM判断失败，需人工审核",
                    "evidence": None,
                    "confidence": 0.0,
                    "evaluator": "llm_semantic_fallback"
                })
            else:
                # 无响应
                results.append({
                    "requirement_id": req.get("requirement_id"),
                    "requirement_text": req.get("requirement_text", ""),
                    "dimension": req.get("dimension", "other"),
                    "is_hard": is_hard,
                    "matched_response_id": None,
                    "matched_response_text": None,
                    "match_score": 0,
                    "judgment": "FAIL" if is_hard else "WARN",
                    "reason": f"{'硬性要求' if is_hard else '建议性要求'}未提供响应",
                    "evidence": None,
                    "confidence": 1.0,
                    "evaluator": "llm_semantic_fallback"
                })
        
        return results
    
    async def _llm_judge_dimension(
        self,
        dimension: str,
        dim_data: Dict[str, List],
        model_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """使用LLM判断一个维度"""
        requirements = dim_data['requirements']
        responses = dim_data['responses']
        
        # 构建prompt
        prompt = self._build_dimension_prompt(dimension, requirements, responses)
        
        # 调用LLM
        if not self.llm:
            logger.warning("DimensionBatchLLMReviewer: No LLM orchestrator available")
            return self._fallback_judge(dim_data)
        
        try:
            # 使用系统的LLM API
            from app.platform.extraction.llm_adapter import call_llm
            
            messages = [{"role": "user", "content": prompt}]
            
            response_text = await call_llm(
                messages=messages,
                llm_orchestrator=self.llm,
                model_id=model_id,
                temperature=0.0,
                max_tokens=8000  # 批量判断需要更多tokens
            )
            
            # 解析LLM输出
            results = self._parse_llm_response(response_text, requirements)
            
            return results
            
        except Exception as e:
            logger.error(f"DimensionBatchLLMReviewer: LLM call failed for dimension '{dimension}': {e}", exc_info=True)
            raise
    
    def _build_dimension_prompt(
        self,
        dimension: str,
        requirements: List[Dict[str, Any]],
        responses: List[Dict[str, Any]]
    ) -> str:
        """构建维度批量判断prompt"""
        
        # 维度说明
        dimension_descriptions = {
            "business": "商务维度 - 包括商务条款、承诺函、服务承诺等",
            "technical": "技术维度 - 包括技术方案、技术参数、技术指标等",
            "qualification": "资格维度 - 包括资质证书、营业执照、业绩证明等",
            "commercial": "商业维度 - 包括报价、付款方式、质保期等",
            "other": "其他维度"
        }
        dim_desc = dimension_descriptions.get(dimension, "其他维度")
        
        # 构建要求列表
        req_list = []
        for i, req in enumerate(requirements, 1):
            is_hard_str = "硬性要求" if req.get("is_hard", False) else "建议性要求"
            req_list.append(
                f"[R{i}] {req.get('requirement_id', f'req_{i}')}: "
                f"{req.get('requirement_text', '')} ({is_hard_str})"
            )
        
        # 构建响应列表
        resp_list = []
        for i, resp in enumerate(responses, 1):
            resp_list.append(
                f"[A{i}] {resp.get('response_text', '')}"
            )
        
        prompt = f"""# 任务
批量判断该维度下所有招标要求是否被投标响应满足。

# 维度信息
维度名称：{dimension}
维度说明：{dim_desc}

# 招标要求列表（{len(requirements)}个）
{chr(10).join(req_list)}

# 投标响应列表（{len(responses)}条）
{chr(10).join(resp_list)}

# 判断任务
请为每个招标要求：
1. 找到最匹配的投标响应（如果有）
2. 评估匹配质量（0-100分）
3. 给出判断结果（PASS/WARN/FAIL）
4. 提供判断理由

# 判断标准
- PASS (≥85分): 响应完全满足要求，内容准确充分
- WARN (70-84分): 响应基本满足但有小瑕疵或不够详细
- FAIL (<70分): 响应不满足要求、答非所问或无响应

# 输出格式（JSON）
请严格按照以下JSON格式输出，确保可以被程序解析：

{{
  "dimension": "{dimension}",
  "judgments": [
    {{
      "requirement_id": "requirement的ID",
      "matched_response_index": 1,
      "matched_response_text": "匹配的响应文本（前100字）",
      "match_score": 95,
      "judgment": "PASS",
      "reason": "判断理由（一句话说明为什么这样判断）",
      "evidence": "响应中的关键证据（前50字）",
      "confidence": 0.95
    }}
  ]
}}

# 重要提示
1. 必须为每个要求都给出判断，不能遗漏
2. 同一个响应可以匹配多个要求
3. 硬性要求无匹配时必须判FAIL
4. 建议性要求无匹配时判WARN
5. matched_response_index是响应在列表中的序号（1-{len(responses)}），如果无匹配则为null
6. 在判断时要考虑同义表达、不同表述方式
7. 关注实质内容而非表面文字

请直接输出JSON，不要添加任何其他内容，不要使用markdown代码块包裹。
"""
        
        return prompt
    
    def _parse_llm_response(
        self,
        response_text: str,
        requirements: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """解析LLM响应"""
        try:
            # 清理response_text，移除可能的markdown代码块
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            # 解析JSON
            data = json.loads(response_text)
            judgments = data.get("judgments", [])
            
            # 转换为标准格式
            results = []
            for i, req in enumerate(requirements):
                # 查找对应的判断
                judgment = None
                for j in judgments:
                    if j.get("requirement_id") == req.get("requirement_id"):
                        judgment = j
                        break
                
                if not judgment:
                    # LLM漏掉了这个要求，使用降级判断
                    logger.warning(f"LLM missed requirement: {req.get('requirement_id')}")
                    results.append({
                        "requirement_id": req.get("requirement_id"),
                        "requirement_text": req.get("requirement_text", ""),
                        "dimension": req.get("dimension", "other"),
                        "is_hard": req.get("is_hard", False),
                        "matched_response_id": None,
                        "matched_response_text": None,
                        "match_score": 0,
                        "judgment": "WARN",
                        "reason": "LLM未返回判断结果",
                        "evidence": None,
                        "confidence": 0.0,
                        "evaluator": "llm_semantic_missing"
                    })
                else:
                    # 使用LLM的判断
                    results.append({
                        "requirement_id": req.get("requirement_id"),
                        "requirement_text": req.get("requirement_text", ""),
                        "dimension": req.get("dimension", "other"),
                        "is_hard": req.get("is_hard", False),
                        "matched_response_id": judgment.get("matched_response_index"),
                        "matched_response_text": judgment.get("matched_response_text"),
                        "match_score": judgment.get("match_score", 0),
                        "judgment": judgment.get("judgment", "WARN").upper(),
                        "reason": judgment.get("reason", ""),
                        "evidence": judgment.get("evidence"),
                        "confidence": judgment.get("confidence", 0.8),
                        "evaluator": "llm_semantic"
                    })
            
            return results
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Response text (first 500 chars): {response_text[:500]}")
            raise ValueError(f"LLM返回的不是有效的JSON: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}", exc_info=True)
            raise

