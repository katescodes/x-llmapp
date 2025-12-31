"""
框架式投标响应提取器 - 按维度分组批量提取
"""
from typing import List, Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)


class FrameworkBidResponseExtractor:
    """
    框架式投标响应提取器：
    - 按维度分组招标要求
    - 一次性提取该维度所有响应
    - 支持复杂对应关系（一对多、多对一）
    """
    
    def __init__(self, llm_orchestrator: Any, retriever: Any):
        self.llm = llm_orchestrator
        self.retriever = retriever
    
    def build_extraction_prompt(
        self,
        dimension: str,
        requirements: List[Dict[str, Any]],
        bid_context: str
    ) -> str:
        """
        构建维度级提取prompt
        
        Args:
            dimension: 维度名称
            requirements: 该维度的所有招标要求
            bid_context: 投标文档检索到的相关内容
        
        Returns:
            LLM提示词
        """
        # 维度说明
        dimension_desc = {
            "price": "价格维度 - 投标报价、费用明细、价格计算",
            "qualification": "资质维度 - 企业资质、人员资格、业绩要求",
            "technical": "技术维度 - 技术方案、性能参数、质量标准",
            "commercial": "商务维度 - 工期、质保、付款方式、违约责任",
            "scoring": "评分维度 - 评分标准对应的投标内容",
            "other": "其他维度 - 特殊要求、承诺事项"
        }
        
        dim_desc = dimension_desc.get(dimension, "其他维度")
        
        # 格式化招标要求列表
        req_list = []
        for idx, req in enumerate(requirements, 1):
            req_id = req.get("requirement_id") or req.get("item_id")
            req_text = req.get("requirement_text", "")
            req_type = req.get("requirement_type") or req.get("req_type", "")
            is_mandatory = req.get("is_mandatory") or req.get("is_hard", False)
            
            # 获取规范化字段信息
            meta = req.get("meta_json", {})
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except:
                    meta = {}
            
            norm_key = meta.get("norm_key") or req.get("norm_key")
            expected_value = meta.get("expected_value") or req.get("expected_value")
            operator = meta.get("operator") or req.get("operator")
            
            req_entry = f"[{req_id}] {req_text}"
            if req_type:
                req_entry += f"\n  类型：{req_type}"
            if is_mandatory:
                req_entry += "\n  ⚠️ 必须满足"
            if norm_key:
                req_entry += f"\n  规范化键：{norm_key}"
            if expected_value:
                req_entry += f"\n  期望值：{operator or ''} {expected_value}"
            
            req_list.append(req_entry)
        
        prompt = f"""# 任务：投标响应提取（{dim_desc}）

## 目标
从投标文档中提取**所有对应该维度招标要求的响应内容**。

## 招标要求（共{len(requirements)}条）

{chr(10).join(req_list)}

## 投标文档内容

{bid_context}

## 提取要求

### ✅ 必须做到
1. **逐条对应**：每个招标要求都要尝试找对应的投标响应
2. **精确定位**：记录响应文本和证据位置（segment_id）
3. **规范化提取**：如有norm_key，必须提取规范化值
4. **合规判断**：判断响应是否满足招标要求

### 📋 处理规则
- **找到响应**：提取完整内容，不要截断
- **未找到响应**：标记为null，不要臆造
- **一对多**：一个响应满足多个要求→同一response_text关联多个requirement_id
- **多对一**：多个响应共同满足一个要求→requirement_id对应多个response

### 🔢 规范化提取
- **价格** - 提取纯数字（元），如"980万元" → 9800000
- **工期** - 提取天数，如"6个月" → 180
- **质保期** - 提取月数，如"2年" → 24
- **比例** - 提取百分数，如"30%" → 30

## 输出格式（JSON数组）

```json
[
  {{
    "requirement_id": "要求ID",
    "response_text": "投标文档中的响应内容（如未找到填null）",
    "evidence_segment_ids": [segment_id列表],
    "normalized_fields": {{
      "norm_key": "规范化后的值（如适用）"
    }},
    "is_compliant": true/false,
    "confidence": 0.0-1.0,
    "review_status": "PASS/FAIL/PENDING/MISSING",
    "review_conclusion": "审核结论说明",
    "risk_level": "HIGH/MEDIUM/LOW",
    "notes": "补充说明（可选）"
  }}
]
```

### 审核判断规则
- **PASS**: is_compliant=true, confidence≥0.85
- **FAIL**: is_compliant=false, confidence≥0.85
- **PENDING**: confidence<0.85 (需人工复核)
- **MISSING**: response_text=null (未提供)

## 输出
请直接输出JSON数组，不要包含其他说明文字。
"""
        return prompt
    
    async def extract_responses_by_dimension(
        self,
        project_id: str,
        dimension: str,
        requirements: List[Dict[str, Any]],
        model_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        按维度提取投标响应
        
        Args:
            project_id: 项目ID
            dimension: 维度名称
            requirements: 该维度的招标要求列表
            model_id: 模型ID
        
        Returns:
            响应列表
        """
        if not requirements:
            logger.warning(f"Dimension {dimension} has no requirements, skipping")
            return []
        
        logger.info(f"Extracting bid responses for dimension: {dimension}, {len(requirements)} requirements")
        
        # 1. 构建查询词（从要求中提取关键词）
        query_terms = []
        for req in requirements:
            req_text = req.get("requirement_text", "")
            # 简单提取前50字符作为查询词
            query_terms.append(req_text[:50])
        
        query = " ".join(query_terms[:5])  # 取前5个要求的文本
        
        # 2. 检索投标文档相关内容
        try:
            bid_chunks = await self.retriever.retrieve(
                query=query,
                project_id=project_id,
                doc_types=["bid"],
                top_k=50  # 获取足够多的上下文
            )
            
            logger.info(f"Retrieved {len(bid_chunks)} bid chunks for dimension {dimension}")
        except Exception as e:
            logger.error(f"Failed to retrieve bid chunks: {e}")
            bid_chunks = []
        
        if not bid_chunks:
            logger.warning(f"No bid chunks found for dimension {dimension}")
            # 返回空响应
            return [{
                "requirement_id": req.get("requirement_id") or req.get("item_id"),
                "response_text": None,
                "evidence_segment_ids": [],
                "normalized_fields": {},
                "is_compliant": False,
                "confidence": 0.0,
                "notes": "未检索到相关投标文档内容"
            } for req in requirements]
        
        # 3. 拼接上下文
        bid_context = "\n\n".join([
            f"[SEG:{chunk.chunk_id}] {chunk.text}"
            for chunk in bid_chunks[:30]  # 限制token数
        ])
        
        # 4. 构建prompt
        prompt = self.build_extraction_prompt(dimension, requirements, bid_context)
        
        logger.info(f"Built prompt for dimension {dimension}, length: {len(prompt)} chars")
        
        # 5. 调用LLM
        try:
            messages = [{"role": "user", "content": prompt}]
            llm_response = await self.llm.achat(
                messages=messages,
                model_id=model_id,
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=8000
            )
            
            llm_output = llm_response.get("choices", [{}])[0].get("message", {}).get("content")
            if llm_output is None:
                llm_output = "[]"
                logger.warning(f"LLM returned None for dimension {dimension}")
            
            logger.info(f"Got LLM response for dimension {dimension}, length: {len(llm_output)} chars")
            
        except Exception as e:
            logger.error(f"LLM call failed for dimension {dimension}: {e}")
            return []
        
        # 6. 解析LLM响应
        try:
            responses = self.parse_llm_response(llm_output)
            logger.info(f"Parsed {len(responses)} responses for dimension {dimension}")
            return responses
        except Exception as e:
            logger.error(f"Failed to parse LLM response for dimension {dimension}: {e}")
            logger.error(f"Raw LLM output: {llm_output[:500]}...")
            return []
    
    def parse_llm_response(self, llm_output: str) -> List[Dict[str, Any]]:
        """
        解析LLM返回的JSON数组
        
        Args:
            llm_output: LLM返回的原始文本
        
        Returns:
            响应列表
        """
        # 清理可能的markdown包裹
        cleaned = llm_output.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        
        try:
            responses = json.loads(cleaned)
            if not isinstance(responses, list):
                raise ValueError("LLM返回的不是JSON数组")
            return responses
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM返回无法解析为JSON: {e}\n原始内容:\n{llm_output[:500]}...")
    
    async def extract_all_responses(
        self,
        project_id: str,
        requirements: List[Dict[str, Any]],
        model_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        提取所有维度的投标响应
        
        Args:
            project_id: 项目ID
            requirements: 所有招标要求列表
            model_id: 模型ID
        
        Returns:
            所有响应列表
        """
        # 1. 按维度分组
        dimension_groups = {}
        for req in requirements:
            dim = req.get("dimension", "other")
            if dim not in dimension_groups:
                dimension_groups[dim] = []
            dimension_groups[dim].append(req)
        
        logger.info(f"Grouped {len(requirements)} requirements into {len(dimension_groups)} dimensions")
        for dim, reqs in dimension_groups.items():
            logger.info(f"  - {dim}: {len(reqs)} requirements")
        
        # 2. 并发提取各维度
        import asyncio
        
        tasks = [
            self.extract_responses_by_dimension(project_id, dim, reqs, model_id)
            for dim, reqs in dimension_groups.items()
        ]
        
        dimension_responses = await asyncio.gather(*tasks)
        
        # 3. 合并所有响应
        all_responses = []
        for responses in dimension_responses:
            all_responses.extend(responses)
        
        logger.info(f"Extracted total {len(all_responses)} bid responses")
        
        return all_responses

