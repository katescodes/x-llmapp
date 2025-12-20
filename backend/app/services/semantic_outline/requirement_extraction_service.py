"""
要求项抽取服务 - 阶段A
从招标文档chunks中抽取结构化要求项
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from app.schemas.semantic_outline import (
    MustLevel,
    RequirementItem,
    RequirementItemLLMOutput,
    RequirementType,
)

logger = logging.getLogger(__name__)


class RequirementExtractionService:
    """要求项抽取服务"""
    
    def __init__(self, llm_orchestrator: Any = None):
        """
        初始化服务
        
        Args:
            llm_orchestrator: LLM编排器（duck typing接口）
        """
        self.llm = llm_orchestrator
    
    def extract_requirements(
        self,
        chunks: List[Dict[str, Any]],
        mode: str = "FAST",
    ) -> List[RequirementItem]:
        """
        从chunks中抽取要求项
        
        Args:
            chunks: chunk列表，每个chunk包含 {chunk_id, content, position, ...}
            mode: 抽取模式 FAST/FULL
            
        Returns:
            要求项列表
        """
        logger.info(f"开始抽取要求项，mode={mode}, chunks数量={len(chunks)}")
        
        # 1. 召回相关chunks（关键词 + 语义）
        relevant_chunks = self._recall_relevant_chunks(chunks, mode)
        logger.info(f"召回相关chunks数量={len(relevant_chunks)}")
        
        if not relevant_chunks:
            logger.warning("未召回到相关chunks")
            return []
        
        # 2. 使用LLM抽取要求项
        requirements = self._extract_with_llm(relevant_chunks, mode)
        logger.info(f"LLM抽取到要求项数量={len(requirements)}")
        
        return requirements
    
    def _recall_relevant_chunks(
        self,
        chunks: List[Dict[str, Any]],
        mode: str,
    ) -> List[Dict[str, Any]]:
        """
        召回相关chunks（关键词匹配）
        
        Args:
            chunks: 所有chunks
            mode: FAST/FULL
            
        Returns:
            相关chunks列表
        """
        # 关键词列表
        keywords = [
            "评分标准", "评分办法", "技术评分", "商务评分",
            "技术要求", "技术参数", "技术规格", "功能要求",
            "验收", "交付", "质保", "售后", "维保", "培训",
            "业绩", "资质", "证书", "人员", "社保",
            "文档格式", "装订要求", "报价", "投标函",
            "分值", "得分", "计分", "评审", "评定",
        ]
        
        relevant_chunks = []
        seen_ids = set()
        
        for chunk in chunks:
            chunk_id = chunk.get("chunk_id", "")
            content = chunk.get("content", "")
            
            if chunk_id in seen_ids:
                continue
            
            # 关键词匹配
            if any(kw in content for kw in keywords):
                relevant_chunks.append(chunk)
                seen_ids.add(chunk_id)
                
                # FAST模式限制数量
                if mode == "FAST" and len(relevant_chunks) >= 20:
                    break
        
        # 按position排序
        relevant_chunks.sort(key=lambda c: c.get("position", 0))
        
        # FULL模式可以返回更多
        if mode == "FULL":
            return relevant_chunks[:50]
        else:
            return relevant_chunks[:20]
    
    def _extract_with_llm(
        self,
        chunks: List[Dict[str, Any]],
        mode: str,
    ) -> List[RequirementItem]:
        """
        使用LLM抽取要求项
        
        Args:
            chunks: 相关chunks
            mode: FAST/FULL
            
        Returns:
            要求项列表
        """
        if not self.llm:
            logger.warning("LLM未配置，返回空列表")
            return []
        
        # 构建prompt
        prompt = self._build_extraction_prompt(chunks, mode)
        
        # 调用LLM
        try:
            messages = [
                {
                    "role": "system",
                    "content": "你是一个专业的招投标文档分析专家，擅长从招标文档中抽取结构化的要求项。",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ]
            
            response = self.llm.chat(messages=messages, model_id=None)
            
            # 解析响应
            content = self._extract_content_from_response(response)
            requirements = self._parse_llm_output(content, chunks)
            
            return requirements
            
        except Exception as e:
            logger.error(f"LLM调用失败: {e}", exc_info=True)
            return []
    
    def _build_extraction_prompt(
        self,
        chunks: List[Dict[str, Any]],
        mode: str,
    ) -> str:
        """构建抽取prompt"""
        # 准备chunks文本
        chunks_text = ""
        for i, chunk in enumerate(chunks[:20]):  # 限制最多20个chunk
            chunk_id = chunk.get("chunk_id", "")
            content = chunk.get("content", "")
            chunks_text += f"\n[Chunk {i+1} - ID: {chunk_id}]\n{content}\n"
        
        prompt = f"""请从以下招标文档片段中，抽取所有的"要求项"（包括评分点、技术要求、资格条件等）。

文档片段：
{chunks_text}

要求项类型（req_type）：
- TECH_SCORE: 技术评分点
- BIZ_SCORE: 商务评分点
- QUALIFICATION: 资格条件
- TECH_SPEC: 技术参数/规格
- DELIVERY_ACCEPTANCE: 交付验收
- SERVICE_WARRANTY: 售后维保
- DOC_FORMAT: 文档格式要求

强制级别（must_level）：
- MUST: 必须满足（如"必须"、"不得"、"应当"等）
- SHOULD: 应该满足（如"建议"、"推荐"等）
- OPTIONAL: 可选（如"可以"、"允许"等）
- UNKNOWN: 无法判断

请以JSON数组格式输出，每个要求项包含以下字段：
- req_type: 要求类型（必须从上述类型中选择）
- title: 简短标题（10字以内）
- content: 要求原文（尽量保持简洁，50字以内）
- score_hint: 分值/评分描述（如有）
- must_level: 强制级别
- source_chunk_ids: 来源chunk ID列表（必须从输入中引用）
- confidence: 置信度 0~1

示例输出格式：
```json
[
  {{
    "req_type": "TECH_SCORE",
    "title": "项目经验",
    "content": "投标人近3年内完成过类似项目，每个得2分，最多10分",
    "score_hint": "最多10分",
    "must_level": "SHOULD",
    "source_chunk_ids": ["chunk_abc123"],
    "confidence": 0.9
  }},
  {{
    "req_type": "QUALIFICATION",
    "title": "营业执照",
    "content": "投标人必须具有有效的营业执照",
    "score_hint": null,
    "must_level": "MUST",
    "source_chunk_ids": ["chunk_def456"],
    "confidence": 0.95
  }}
]
```

注意：
1. 只输出JSON数组，不要有其他文字
2. 每个要求项必须关联到至少一个chunk ID
3. 尽量抽取所有有意义的要求项
4. 如果一个要求项跨多个chunk，将所有相关chunk ID都列出
5. content字段尽量简洁，保留核心信息即可

请开始抽取："""
        
        return prompt
    
    def _extract_content_from_response(self, response: Any) -> str:
        """从LLM响应中提取内容"""
        if isinstance(response, str):
            return response
        
        if isinstance(response, dict):
            # 尝试常见的键
            for key in ("content", "text", "output"):
                if key in response and isinstance(response[key], str):
                    return response[key]
            
            # OpenAI-like格式
            if "choices" in response and response["choices"]:
                choice = response["choices"][0]
                if isinstance(choice, dict):
                    message = choice.get("message", {})
                    if isinstance(message, dict) and "content" in message:
                        return message["content"]
        
        return str(response)
    
    def _parse_llm_output(
        self,
        content: str,
        chunks: List[Dict[str, Any]],
    ) -> List[RequirementItem]:
        """
        解析LLM输出
        
        Args:
            content: LLM输出的文本
            chunks: 原始chunks（用于验证chunk ID）
            
        Returns:
            要求项列表
        """
        # 提取JSON部分
        json_str = self._extract_json_from_text(content)
        if not json_str:
            logger.warning("未找到有效的JSON输出")
            return []
        
        try:
            items_raw = json.loads(json_str)
            if not isinstance(items_raw, list):
                logger.warning("JSON输出不是数组")
                return []
            
            # 构建chunk ID集合（用于验证）
            valid_chunk_ids = {c.get("chunk_id", "") for c in chunks}
            
            requirements = []
            for item_data in items_raw:
                try:
                    # 验证chunk IDs
                    source_ids = item_data.get("source_chunk_ids", [])
                    if not source_ids:
                        continue
                    
                    # 过滤无效的chunk IDs
                    valid_source_ids = [cid for cid in source_ids if cid in valid_chunk_ids]
                    if not valid_source_ids:
                        continue
                    
                    # 构建RequirementItem
                    req_id = f"req_{uuid.uuid4().hex[:12]}"
                    
                    # 解析枚举类型
                    req_type_str = item_data.get("req_type", "TECH_SPEC")
                    try:
                        req_type = RequirementType(req_type_str)
                    except ValueError:
                        req_type = RequirementType.TECH_SPEC
                    
                    must_level_str = item_data.get("must_level", "UNKNOWN")
                    try:
                        must_level = MustLevel(must_level_str)
                    except ValueError:
                        must_level = MustLevel.UNKNOWN
                    
                    req = RequirementItem(
                        req_id=req_id,
                        req_type=req_type,
                        title=item_data.get("title", "")[:100],
                        content=item_data.get("content", "")[:500],
                        params=item_data.get("params"),
                        score_hint=item_data.get("score_hint"),
                        must_level=must_level,
                        source_chunk_ids=valid_source_ids,
                        confidence=float(item_data.get("confidence", 0.8)),
                    )
                    
                    requirements.append(req)
                    
                except Exception as e:
                    logger.warning(f"解析要求项失败: {e}")
                    continue
            
            return requirements
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            return []
    
    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """从文本中提取JSON部分"""
        # 尝试提取```json ... ```包裹的内容
        match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text, re.DOTALL)
        if match:
            return match.group(1)
        
        # 尝试直接查找JSON数组
        match = re.search(r"(\[[\s\S]*\])", text, re.DOTALL)
        if match:
            return match.group(1)
        
        return None

