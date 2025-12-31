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
        for i, chunk in enumerate(chunks[:30]):  # 增加到30个chunk
            chunk_id = chunk.get("chunk_id", "")
            content = chunk.get("content", "")
            chunks_text += f"\n[Chunk {i+1} - ID: {chunk_id}]\n{content}\n"
        
        prompt = f"""# 角色与任务

你是一位资深的招投标评审专家。你的任务是：从招标文件中提取**完整的评审规则清单**，这些规则将用于后续审核投标书是否符合要求。

# 文档片段

{chunks_text}

---

# 评审维度说明

评审规则通常包含以下维度（但不限于此）：

1. **一票否决项**：废标条款、实质性要求（如："保证金不足作废标处理"、"未按要求签章的投标文件无效"）
2. **评分标准**：技术评分、商务评分、价格评分等各类评分项（如："项目经验每个2分，最多10分"）
3. **资格条件**：营业执照、资质证书、业绩证明、人员配置、信用记录等
4. **技术规格**：设备参数、性能指标、技术方案要求、兼容性要求等
5. **商务条款**：质保期、售后服务、培训方案、付款方式、交付要求等
6. **文档格式**：装订要求、签字盖章、份数、封装方式等

**请根据文档内容的语义和上下文，自行判断每个要求项属于哪个维度。**

---

# 核心要求

## 1. 完整性优先（宁多勿少）
- 提取所有评审相关的规则和要求，不要遗漏
- 评分表中的每一个评分项都应拆分为独立的要求项
- 不确定是否应提取时，优先选择提取
- 同一维度的多个要求应分别提取（如多个资格要求、多个评分项）

## 2. 准确理解语义
- 识别废标条款的关键表述："作废标处理"、"一票否决"、"投标无效"、"视为不响应"等
- 识别评分项的评分规则和计算方式
- 准确判断强制级别（必须/应该/可选）
- 理解隐含要求（如："技术方案评分" 隐含需要提供技术方案）

## 3. 特别关注带符号的条款 ⚠️
- **▲ 三角形符号**：通常标识实质性要求、废标条款、重要技术指标等，必须重点提取
- **★ 星号符号**：通常标识重要评分项、关键要求等
- **● 圆点符号**：可能标识必须满足的条件
- **※ 特殊符号**：通常标识需要特别注意的内容
- 带有这些符号的条款往往是最重要的评审规则，务必完整提取并在title或content中保留符号标识

## 4. 保留完整上下文
- content字段应包含足够信息，让审核人员能准确判断投标书是否符合
- 包含评分规则、计算方式、证明材料要求、页码位置等关键信息
- 不要过度压缩导致信息丢失

---

# 输出格式

返回JSON数组，每个要求项包含以下字段：

```json
[
  {{
    "req_type": "维度类型（根据理解自行判断，如：MUST_REJECT/TECH_SCORE/BIZ_SCORE/QUALIFICATION/TECH_SPEC/BUSINESS/DOC_FORMAT等）",
    "title": "简短标题",
    "content": "要求内容（保留完整信息，包括评分规则、证明材料、强制表述等）",
    "score_hint": "分值描述（如有，如：10分、每个2分最多10分）",
    "must_level": "MUST/SHOULD/OPTIONAL/UNKNOWN",
    "source_chunk_ids": ["来源chunk ID"],
    "confidence": 0.9
  }}
]
```

---

# 示例（参考理解方式）

**示例1：废标条款（带符号标识）**
```json
{{
  "req_type": "MUST_REJECT",
  "title": "▲保证金不符",
  "content": "▲投标保证金金额不足或缴纳形式不符合要求的，作废标处理。投标保证金应为人民币50万元，以银行转账或保函形式提交。",
  "score_hint": null,
  "must_level": "MUST",
  "source_chunk_ids": ["chunk_001"],
  "confidence": 0.95
}}
```

**示例2：评分项（完整规则）**
```json
{{
  "req_type": "TECH_SCORE",
  "title": "类似业绩",
  "content": "投标人近3年内完成的类似项目业绩，每提供1个有效业绩得2分，最多提供5个，本项最高10分。有效业绩需提供合同复印件及验收证明，合同金额不低于100万元。",
  "score_hint": "最多10分",
  "must_level": "SHOULD",
  "source_chunk_ids": ["chunk_045"],
  "confidence": 0.9
}}
```

**示例3：资格要求**
```json
{{
  "req_type": "QUALIFICATION",
  "title": "建筑资质",
  "content": "投标人须具备建筑工程施工总承包二级及以上资质，资质证书在有效期内，需提供证书复印件并加盖公章。",
  "score_hint": null,
  "must_level": "MUST",
  "source_chunk_ids": ["chunk_012"],
  "confidence": 0.95
}}
```

---

# 最终检查

提取完成后，请自检：
1. ✅ 所有带特殊符号（▲★●※等）的条款都提取了吗？这些往往是最重要的
2. ✅ 所有废标条款、实质性要求都提取了吗？
3. ✅ 评分表中的每个评分项都逐条提取了吗（而非合并）？
4. ✅ 资格要求、技术规格、商务条款都完整提取了吗？
5. ✅ 每条要求的content包含足够信息吗（评分规则、证明材料等）？
6. ✅ 每条要求都关联了source_chunk_ids吗？

---

**只输出JSON数组，不要有任何其他文字。开始提取：**
"""
        
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

