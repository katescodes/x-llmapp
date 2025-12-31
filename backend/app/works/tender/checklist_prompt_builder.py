"""
标准清单Prompt生成器
用于生成让LLM填写标准清单的Prompt
"""
import json
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class ChecklistPromptBuilder:
    """标准清单Prompt生成器"""
    
    def build_prompt(
        self,
        checklist_items: List[Dict],
        context_text: str,
        project_name: str = "本项目",
    ) -> str:
        """
        构建标准清单填写Prompt
        
        Args:
            checklist_items: 检查项列表（从ChecklistLoader获取）
            context_text: 招标文件上下文
            project_name: 项目名称
        
        Returns:
            完整的Prompt字符串
        """
        logger.info(f"Building checklist prompt with {len(checklist_items)} items")
        
        # 构建清单结构（JSON Schema）
        checklist_structure = self._build_checklist_structure(checklist_items)
        
        # 构建完整Prompt
        prompt = f"""# 角色与任务

你是一位资深的招投标评审专家。你的任务是：**深入理解招标文件**，提取完整的评审要求，填写标准清单，用于后续审核投标书。

## 招标项目
项目名称：{project_name}

## 招标文件内容
以下是招标文件内容（[SEG:xxx]为段落标记）：

---
{context_text}
---

## 标准清单（共{len(checklist_items)}项）

### 核心原则

**1. 深度理解优先**
- 基于招标文件的语义和上下文进行理解，不是简单的关键词匹配
- 识别明确要求、隐含要求和实质性条款
- 理解评审维度之间的关联（如：资格要求可能影响评分标准）

**2. 特别关注符号标识 ⚠️**
- **▲ 三角形符号**：通常标识实质性要求、废标条款、重要技术指标等，必须重点关注
- **★ 星号符号**：通常标识重要评分项、关键要求等
- **● 圆点符号**：可能标识必须满足的条件
- **※ 特殊符号**：通常标识需要特别注意的内容
- 带符号的条款往往是最重要的评审规则，必须完整提取并在requirement_text中保留符号

**3. 完整性优先（宁多勿少）**
- requirement_text应包含完整的评审要求原文和上下文
- 保留评分规则、计算方式、证明材料要求等关键信息
- 不要过度压缩，保持原文表述
- 如果不确定是否相关，优先提取

**4. 推理能力**
- 推断废标条款："作废标处理"、"一票否决"、"投标无效"、"视为不响应"等表述
- 推断评分规则和计算方式
- 推断强制级别（必须/应该/可选）
- 推断隐含要求（如："技术方案评分" 隐含需要提供技术方案）

### 清单字段说明

- **id**: 检查项唯一标识（保持原值）
- **question**: 检查问题（保持原值）
- **answer**: 结构化回答
  - boolean类型：true/false
  - boolean_with_number类型：{{"exists": true/false, "value": 数值, "unit": "单位"}}
  - boolean_with_text类型：{{"exists": true/false, "description": "描述"}}
  - number类型：{{"value": 数值, "unit": "单位"}}
  - text类型：字符串描述
- **requirement_text**: **【核心】招标书原文要求**
  - 提取与当前问题直接相关的完整段落
  - 保留原文表述，包括符号（▲★●※等）
  - 包含评分规则、证明材料、强制表述等完整信息
  - 如果文档中没有相关内容，填写null
- **evidence_segment_ids**: 证据来源segment ID列表，格式：["seg_xxx", "seg_yyy"]
- **confidence**: 置信度（0-1）
- **dimension**: 维度（保持原值）
- **norm_key**: 标准化键（保持原值）

### 填写指南

1. **深度理解文档内容**，基于语义判断，而非机械匹配关键词
2. **优先关注带符号的条款**（▲★●※等），这些是最重要的评审规则
3. **requirement_text包含足够上下文**，让审核人员能准确判断
4. **只提取与当前问题相关的内容**，避免混入其他主题
5. **如果明确提到**：answer填写对应信息，requirement_text提取完整原文，confidence=0.9-1.0
6. **如果完全没提到**：answer=null/false，requirement_text=null，evidence_segment_ids=[]，confidence=0.9-1.0
7. **如果可推断**：answer填写推断结果，requirement_text提取相关原文，confidence=0.5-0.8

### 输出格式
JSON对象，key为检查项id，value为包含answer、requirement_text、evidence_segment_ids、confidence等字段的对象。

示例：
```json
{{
  "price_001": {{
    "id": "price_001",
    "question": "是否有最高限价（招标控制价）？",
    "answer": {{"exists": true, "value": 5000000, "unit": "元"}},
    "requirement_text": "本项目招标控制价为人民币500万元。投标报价超过招标控制价的投标文件将被拒绝。投标人应合理测算成本，投标报价应包含完成本项目所需的一切费用。",
    "evidence_segment_ids": ["seg_abc123"],
    "confidence": 1.0,
    "dimension": "price",
    "norm_key": "price_upper_limit_cny"
  }},
  "qual_001": {{
    "id": "qual_001",
    "question": "是否要求提供营业执照？",
    "answer": true,
    "requirement_text": "投标人须提供有效的营业执照副本（加盖公章）。营业执照经营范围应包含本项目相关业务内容。",
    "evidence_segment_ids": ["seg_def456"],
    "confidence": 1.0,
    "dimension": "qualification",
    "norm_key": "doc_business_license_present"
  }},
  "business_003": {{
    "id": "business_003",
    "question": "是否有交付或验收标准？",
    "answer": {{"exists": true, "description": "有详细验收标准和流程"}},
    "requirement_text": "验收标准：按照GB/T 19001-2016执行。验收工作应在货物到达现场后7个工作日内完成。验收合格后，采购人应在7个工作日内支付尾款。如验收不合格，中标人应在3个工作日内进行整改，直至验收合格。所有验收文件应由双方签字确认并存档。",
    "evidence_segment_ids": ["seg_ghi789", "seg_jkl012"],
    "confidence": 1.0,
    "dimension": "business"
  }},
  ...
}}
```

**注意**：requirement_text字段包含完整的招标书原文，不是简短引用。

## 开始填写

请按照以上格式和规则，填写以下{len(checklist_items)}个检查项：

{json.dumps(checklist_structure, ensure_ascii=False, indent=2)}

**重要提示**：
- 输出必须是**合法的JSON对象**，不要有额外的文字说明
- 所有{len(checklist_items)}个检查项都必须填写
- confidence字段必须是0-1之间的浮点数
- 数值类型的answer必须包含value和unit字段
"""
        
        return prompt
    
    def _build_checklist_structure(self, checklist_items: List[Dict]) -> Dict[str, Any]:
        """
        构建清单结构（供LLM填写）
        
        Args:
            checklist_items: 检查项列表
        
        Returns:
            清单结构字典
        """
        structure = {}
        
        for item in checklist_items:
            item_id = item.get('id')
            
            # 构建item结构（模板）
            item_template = {
                "id": item_id,
                "question": item.get('question'),
                "type": item.get('type'),
                "dimension": item.get('dimension'),
                "category": item.get('category'),
            }
            
            # 添加norm_key（如果有）
            if item.get('norm_key'):
                item_template["norm_key"] = item.get('norm_key')
            
            # 添加unit（如果有）
            if item.get('unit'):
                item_template["unit"] = item.get('unit')
            
            # 添加eval_method和req_type（供LLM参考）
            item_template["eval_method"] = item.get('eval_method')
            item_template["req_type"] = item.get('req_type')
            item_template["is_hard"] = item.get('is_hard', False)
            
            # 预留填写字段
            item_template["answer"] = None
            item_template["confidence"] = None
            item_template["requirement_text"] = None
            item_template["evidence_segment_ids"] = []
            
            structure[item_id] = item_template
        
        return structure
    
    def parse_llm_response(
        self,
        llm_output: str,
        original_items: List[Dict]
    ) -> Dict[str, Any]:
        """
        解析LLM填写的清单结果
        
        Args:
            llm_output: LLM输出的JSON字符串
            original_items: 原始检查项列表
        
        Returns:
            解析后的结果字典
        
        Raises:
            json.JSONDecodeError: JSON解析失败
        """
        logger.info("Parsing LLM response")
        
        try:
            # 尝试解析JSON
            result = json.loads(llm_output)
            
            logger.info(f"Successfully parsed LLM response, got {len(result)} items")
            
            # 验证结果完整性
            original_ids = {item.get('id') for item in original_items}
            result_ids = set(result.keys())
            
            missing_ids = original_ids - result_ids
            if missing_ids:
                logger.warning(f"LLM response missing {len(missing_ids)} items: {missing_ids}")
            
            extra_ids = result_ids - original_ids
            if extra_ids:
                logger.warning(f"LLM response has {len(extra_ids)} extra items: {extra_ids}")
            
            return result
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"LLM output (first 500 chars): {llm_output[:500]}")
            raise
    
    def convert_to_requirements(
        self,
        filled_checklist: Dict[str, Any],
        project_id: str
    ) -> List[Dict[str, Any]]:
        """
        将填写好的清单转换为requirements格式
        
        Args:
            filled_checklist: LLM填写的清单结果（parsed）
            project_id: 项目ID
        
        Returns:
            requirements列表
        """
        logger.info(f"Converting filled checklist to requirements format for project {project_id}")
        
        requirements = []
        
        for item_id, item_data in filled_checklist.items():
            answer = item_data.get('answer')
            confidence = item_data.get('confidence', 0.5)
            
            # 跳过confidence太低的项
            if confidence < 0.3:
                logger.debug(f"Skipping {item_id} due to low confidence ({confidence})")
                continue
            
            # ✅ 增强过滤逻辑：跳过"无此要求"的项
            # 情况1: answer直接为False或None
            if answer is False or answer is None:
                logger.debug(f"Skipping {item_id}: answer is False/None (no such requirement)")
                continue
            
            # 情况2: answer为字典，且exists=false（表示招标书中无此要求）
            if isinstance(answer, dict):
                exists = answer.get('exists')
                if exists is False:
                    logger.debug(f"Skipping {item_id}: exists=False (no such requirement)")
                    continue
                # 如果exists为null且没有其他有效字段，也跳过
                if exists is None and not any(answer.get(k) for k in ['value', 'description'] if k in answer):
                    logger.debug(f"Skipping {item_id}: exists=None with no valid data")
                    continue
            
            # ✅ 提取LLM生成的完整招标书原文内容
            requirement_text = item_data.get('requirement_text')
            if not requirement_text or requirement_text.strip() == "":
                # Fallback: 如果LLM没有提取原文，使用question作为fallback
                requirement_text = item_data.get('question')
                logger.warning(f"No requirement_text for {item_id}, using question as fallback")
            else:
                # ✅ 清理过长或包含多段的requirement_text
                requirement_text = self._clean_requirement_text(requirement_text, item_id)
            
            # ✅ 特殊处理：评分标准拆分
            if item_id == 'scoring_001' and isinstance(answer, dict):
                scoring_reqs = self._process_scoring_items(item_id, item_data, answer, project_id)
                requirements.extend(scoring_reqs)
                continue
            
            # ✅ 提取证据segment IDs
            evidence_segment_ids = item_data.get('evidence_segment_ids', [])
            if not isinstance(evidence_segment_ids, list):
                evidence_segment_ids = []
            
            # 构建requirement
            req = {
                "project_id": project_id,
                "requirement_id": f"checklist_{item_id}",
                "dimension": item_data.get('dimension', 'other'),
                "req_type": item_data.get('req_type', 'other'),
                "requirement_text": requirement_text,  # ✅ 使用LLM提取的完整原文
                "is_hard": item_data.get('is_hard', False),
                "allow_deviation": not item_data.get('is_hard', False),
                "eval_method": item_data.get('eval_method', 'SEMANTIC'),
                "must_reject": item_data.get('must_reject', False),
                "evidence_chunk_ids": evidence_segment_ids,  # ✅ 保存segment IDs
            }
            
            # 处理answer并构建value_schema_json
            value_schema = self._build_value_schema(item_data, answer)
            if value_schema:
                req["value_schema_json"] = value_schema
            
            # 添加expected_evidence_json（用于展示）
            if evidence_segment_ids:
                req["expected_evidence_json"] = [{
                    "source": "招标文件",
                    "segment_ids": evidence_segment_ids,
                    "quote": requirement_text[:100] + "..." if len(requirement_text) > 100 else requirement_text
                }]
            
            # 添加meta信息
            req["meta_json"] = {
                "checklist_item_id": item_id,
                "checklist_question": item_data.get('question'),  # ✅ 保存原始问题
                "confidence": confidence,
                "category": item_data.get('category'),
                "llm_answer": answer,  # ✅ 保存LLM的结构化答案
            }
            
            requirements.append(req)
        
        logger.info(f"Converted to {len(requirements)} requirements")
        
        return requirements
    
    def _process_scoring_items(
        self,
        item_id: str,
        item_data: Dict,
        answer: Dict,
        project_id: str
    ) -> List[Dict[str, Any]]:
        """
        处理评分标准：将评分项拆分为多个独立的requirement
        
        Args:
            item_id: 清单项ID
            item_data: 清单项数据
            answer: LLM返回的评分标准结构
            project_id: 项目ID
        
        Returns:
            拆分后的requirement列表
        """
        requirements = []
        
        # 检查是否有评分标准
        has_scoring = answer.get('has_scoring', False)
        if not has_scoring:
            logger.info("No scoring criteria found in tender document")
            return requirements
        
        scoring_items = answer.get('scoring_items', [])
        if not scoring_items:
            logger.warning("has_scoring=True but no scoring_items found")
            return requirements
        
        logger.info(f"Processing {len(scoring_items)} scoring items")
        
        # 遍历每个评分项
        for idx, scoring_item in enumerate(scoring_items):
            item_name = scoring_item.get('item_name', f'评分项{idx+1}')
            max_score = scoring_item.get('max_score', 0)
            scoring_rule = scoring_item.get('scoring_rule', '')
            item_requirements = scoring_item.get('requirements', [])
            
            # 拆分：每个具体要求作为独立的requirement
            for req_idx, req_item in enumerate(item_requirements):
                req_text = req_item.get('requirement_text', '')
                if not req_text:
                    continue
                
                evidence_ids = req_item.get('evidence_segment_ids', [])
                if not isinstance(evidence_ids, list):
                    evidence_ids = []
                
                # 构建独立的requirement
                req = {
                    "project_id": project_id,
                    "requirement_id": f"scoring_{idx+1:03d}_{req_idx+1:03d}",
                    "dimension": "other",  # 评分项统一为other或根据内容推断
                    "req_type": "scoring_prerequisite",  # 标记为评分前提要求
                    "requirement_text": req_text,
                    "is_hard": False,  # 评分项通常不是硬性废标
                    "allow_deviation": True,
                    "eval_method": "SEMANTIC",  # 使用LLM判断是否满足
                    "must_reject": False,
                    "evidence_chunk_ids": evidence_ids,
                    "value_schema_json": {
                        "type": "presence",
                        "description": req_text,
                    },
                    "expected_evidence_json": [{
                        "source": "招标文件",
                        "segment_ids": evidence_ids,
                        "quote": req_text[:100] + "..." if len(req_text) > 100 else req_text
                    }] if evidence_ids else [],
                    "meta_json": {
                        "checklist_item_id": item_id,
                        "scoring_item_name": item_name,
                        "scoring_item_index": idx,
                        "requirement_index": req_idx,
                        "max_score": max_score,
                        "scoring_rule": scoring_rule,
                        "category": "评分标准",
                    }
                }
                
                requirements.append(req)
                logger.debug(f"Created scoring requirement: {req['requirement_id']} - {req_text[:50]}...")
        
        logger.info(f"Split scoring items into {len(requirements)} individual requirements")
        return requirements
    
    def _clean_requirement_text(self, text: str, item_id: str) -> str:
        """
        清理requirement_text，去除重复或不相关的内容
        
        【温和策略】只处理明显的多段拼接，不要过度删除内容
        
        Args:
            text: 原始文本
            item_id: 清单项ID
        
        Returns:
            清理后的文本
        """
        if not text or len(text) < 100:
            return text
        
        # 按换行符分割
        lines = text.split('\n')
        
        # 如果只有1-2行，直接返回（不要过度清理）
        if len(lines) <= 2:
            return text
        
        # 如果有多行（3行以上），只保留第一个完整段落
        # 策略：保守截断，只在明确的分段点（句号结尾且长度足够）截断
        cleaned_lines = []
        total_length = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            cleaned_lines.append(line)
            total_length += len(line)
            
            # 只有在以下情况才截断：
            # 1. 当前行以句号结尾
            # 2. 已经超过150字符（比之前的80字符更宽松）
            # 3. 不是第一行（避免截断过早）
            if (line.endswith(('。', '.')) and 
                total_length > 150 and 
                len(cleaned_lines) > 1):
                logger.debug(f"Cleaned requirement_text for {item_id}: kept {len(cleaned_lines)} lines out of {len(lines)}")
                break
            
            # 如果已经超过500字符（比之前的400更宽松），强制截断
            if total_length > 500:
                logger.warning(f"Force truncating requirement_text for {item_id}: {total_length} chars")
                break
        
        result = '\n'.join(cleaned_lines)
        
        # 只有在清理掉很多内容时才记录日志
        if len(result) < len(text) * 0.6:
            logger.info(f"Cleaned requirement_text for {item_id}: {len(text)} -> {len(result)} chars")
        
        return result
    
    def _build_value_schema(self, item_data: Dict, answer: Any) -> Dict[str, Any]:
        """
        根据answer构建value_schema_json
        
        Args:
            item_data: 检查项数据
            answer: LLM填写的answer
        
        Returns:
            value_schema字典
        """
        item_type = item_data.get('type')
        norm_key = item_data.get('norm_key')
        
        schema = {}
        
        if norm_key:
            schema["norm_key"] = norm_key
        
        # 根据类型处理answer
        if item_type == "boolean":
            schema["type"] = "boolean"
            schema["expected"] = bool(answer)
        
        elif item_type == "boolean_with_number":
            if isinstance(answer, dict):
                schema["type"] = "number"
                if answer.get('exists'):
                    schema["value"] = answer.get('value')
                    schema["unit"] = answer.get('unit', item_data.get('unit'))
                    # 添加到normalized_fields
                    if norm_key:
                        schema["_norm_value"] = answer.get('value')
        
        elif item_type == "boolean_with_text":
            if isinstance(answer, dict):
                schema["type"] = "text"
                if answer.get('exists'):
                    schema["description"] = answer.get('description')
        
        elif item_type == "number":
            if isinstance(answer, dict):
                schema["type"] = "number"
                schema["value"] = answer.get('value')
                schema["unit"] = answer.get('unit', item_data.get('unit'))
                if norm_key:
                    schema["_norm_value"] = answer.get('value')
        
        elif item_type == "text":
            schema["type"] = "text"
            schema["value"] = str(answer)
        
        return schema if schema else None

