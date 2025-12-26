"""
LLMFragmentMatcher - LLM语义匹配器
用于处理规则无法准确匹配的复杂cases
"""
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LLMFragmentMatcher:
    """LLM语义匹配器（兜底策略）"""
    
    def __init__(self, llm_client):
        """
        初始化
        
        Args:
            llm_client: LLM客户端（来自 tender_service.llm）
        """
        self.llm = llm_client
    
    async def match_async(
        self,
        node: Dict[str, Any],
        fragments: List[Dict[str, Any]],
        model_id: str = "gpt-4o-mini"
    ) -> Optional[Dict[str, Any]]:
        """
        使用LLM进行语义匹配
        
        Args:
            node: 目录节点，格式: {id, title, level, notes, ...}
            fragments: 候选格式文档列表
            model_id: LLM模型ID
            
        Returns:
            匹配到的fragment，如果没有匹配则返回 None
        """
        if not fragments:
            return None
        
        try:
            # 构建 Prompt
            prompt = self._build_prompt(node, fragments)
            
            # 调用LLM
            from app.services.llm_client import call_llm
            
            messages = [{"role": "user", "content": prompt}]
            
            response = await call_llm(
                messages=messages,
                llm=self.llm,
                model_id=model_id,
                temperature=0.0,
                max_tokens=500
            )
            
            # 解析结果
            result = self._parse_response(response)
            
            if not result:
                return None
            
            # 验证置信度阈值
            score = result.get("score", 0)
            if score < 80:
                logger.info(f"[LLMFragmentMatcher] Low confidence score: {score}, skipping")
                return None
            
            # 查找匹配的fragment
            best_match_id = result.get("best_match_id")
            matched_fragment = next(
                (f for f in fragments if f.get("id") == best_match_id),
                None
            )
            
            if matched_fragment:
                logger.info(
                    f"[LLMFragmentMatcher] Matched node '{node.get('title')}' "
                    f"to fragment '{matched_fragment.get('title')}' "
                    f"(score: {score}, reason: {result.get('reason')})"
                )
            
            return matched_fragment
            
        except Exception as e:
            logger.error(f"[LLMFragmentMatcher] match_async failed: {type(e).__name__}: {e}")
            return None
    
    def _build_prompt(self, node: Dict[str, Any], fragments: List[Dict[str, Any]]) -> str:
        """
        构建匹配Prompt
        
        Args:
            node: 目录节点
            fragments: 候选格式文档列表
            
        Returns:
            Prompt字符串
        """
        node_title = node.get("title", "")
        node_level = node.get("level", 0)
        node_notes = node.get("notes", "")
        
        # 格式化候选格式文档
        fragments_text = self._format_fragments(fragments)
        
        prompt = f"""你是招投标文档匹配专家。请判断以下格式文档是否与目录节点匹配。

目录节点:
- 标题: {node_title}
- 层级: 第{node_level}级
- 说明: {node_notes or "无"}

候选格式文档列表:
{fragments_text}

请为每个格式文档打分（0-100），并返回匹配度最高的一个。

返回JSON格式:
{{
  "best_match_id": "fragment_id",
  "score": 95,
  "reason": "标题完全匹配"
}}

评分标准:
- 95-100: 完全匹配（标题相同或同义词）
- 80-94: 高度相关（内容高度吻合）
- 60-79: 部分相关（有一定关联）
- 0-59: 不相关或无关

只返回JSON，不要其他内容。
"""
        return prompt
    
    def _format_fragments(self, fragments: List[Dict[str, Any]]) -> str:
        """
        格式化候选格式文档列表
        
        Args:
            fragments: 格式文档列表
            
        Returns:
            格式化后的字符串
        """
        lines = []
        for i, frag in enumerate(fragments[:20], 1):  # 最多显示20个
            frag_id = frag.get("id", "")
            frag_title = frag.get("title", "")
            frag_type = frag.get("fragment_type", "")
            lines.append(f"{i}. ID: {frag_id}, 标题: {frag_title}, 类型: {frag_type}")
        
        if len(fragments) > 20:
            lines.append(f"... (还有 {len(fragments) - 20} 个候选文档)")
        
        return "\n".join(lines)
    
    def _parse_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        解析LLM响应
        
        Args:
            response: LLM返回的文本
            
        Returns:
            解析后的字典，如果解析失败则返回 None
        """
        try:
            # 尝试提取JSON
            import re
            
            # 移除可能的markdown代码块标记
            response = re.sub(r'```json\s*', '', response)
            response = re.sub(r'```\s*', '', response)
            response = response.strip()
            
            # 解析JSON
            result = json.loads(response)
            
            # 验证必需字段
            if "best_match_id" not in result or "score" not in result:
                logger.warning(f"[LLMFragmentMatcher] Invalid response format: {response[:100]}")
                return None
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"[LLMFragmentMatcher] JSON parse error: {e}, response: {response[:200]}")
            return None
        except Exception as e:
            logger.error(f"[LLMFragmentMatcher] Parse error: {type(e).__name__}: {e}")
            return None

