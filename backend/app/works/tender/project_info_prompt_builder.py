"""
项目信息Prompt生成器
用于基于checklist的项目信息提取（6个stage）
"""
import json
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class ProjectInfoPromptBuilder:
    """项目信息Prompt生成器 - 基于Checklist的结构化提取"""
    
    def __init__(self, stage: int, stage_config: Dict[str, Any]):
        """
        初始化Prompt生成器
        
        Args:
            stage: 当前阶段编号（1-6）
            stage_config: 该阶段的配置信息（从YAML加载）
        """
        self.stage = stage
        self.stage_key = stage_config.get("stage_key")
        self.stage_name = stage_config.get("stage_name")
        self.description = stage_config.get("description", "")
        
        # 提取所有字段
        self.fields = self._extract_all_fields(stage_config)
        
        logger.info(
            f"ProjectInfoPromptBuilder initialized: "
            f"stage={stage}, key={self.stage_key}, fields={len(self.fields)}"
        )
    
    def _extract_all_fields(self, stage_config: Dict) -> List[Dict]:
        """提取阶段配置中的所有字段"""
        fields = []
        
        # 遍历所有group
        for key, value in stage_config.items():
            if key in ["stage", "stage_key", "stage_name", "description"]:
                continue
            
            if isinstance(value, dict) and "fields" in value:
                group_name = value.get("group_name", key)
                for field in value["fields"]:
                    field_copy = field.copy()
                    field_copy["group_name"] = group_name
                    fields.append(field_copy)
        
        return fields
    
    def build_p0_prompt(
        self,
        context_text: str,
        context_info: Optional[Dict] = None
    ) -> str:
        """
        构建P0阶段Prompt（基于Checklist的结构化提取）
        
        Args:
            context_text: 招标文档上下文（带segment ID标记）
            context_info: 前序stage的结果（用于后续stage）
        
        Returns:
            完整的Prompt文本
        """
        # 构建字段列表（保持英文key，添加中文说明）
        type_name_map = {
            "text": "文本",
            "number": "数值",
            "list": "列表",
            "boolean": "布尔值"
        }
        
        fields_json = []
        for field in self.fields:
            field_item = {
                "id": field["id"],
                "field_name": field["field_name"],  # ✅ 这是返回JSON时必须使用的key
                "question": field["question"],
                "type": field["type"],
                "type_cn": type_name_map.get(field["type"], field["type"]),  # 中文类型说明
                "is_required": field.get("is_required", False),
                "description": field.get("description", "")
            }
            
            # 如果是list类型，添加item_schema
            if field["type"] == "list" and "item_schema" in field:
                field_item["item_schema"] = field["item_schema"]
            
            fields_json.append(field_item)
        
        # 构建上下文信息部分
        context_section = ""
        if context_info and isinstance(context_info, dict):
            context_section = f"""
## 前序阶段信息

以下是之前阶段提取的信息，可作为参考：

```json
{json.dumps(context_info, ensure_ascii=False, indent=2)}
```
"""
        
        prompt = f"""# 角色与任务

你是一位资深的招投标文件分析专家。你的任务是：从招标文档中提取**{self.stage_name}**相关的结构化信息。

## 当前阶段：Stage {self.stage} - {self.stage_name}

{self.description}

---

# 招标文档片段

以下是招标文档的相关片段，每个片段用 [SEG:segment_id] 标记：

{context_text}

---
{context_section}
---

# 提取字段清单

请根据上述招标文档，提取以下字段的信息：

```json
{json.dumps(fields_json, ensure_ascii=False, indent=2)}
```

---

# 提取要求

## 1. 准确性优先
- 仅提取文档中明确出现的信息，不要推测或编造
- 如果文档中没有某个字段的信息，该字段应为null或空值
- 保持原文的准确性，不要过度概括或改写

## 2. 完整性
- 尽可能完整地提取每个字段的信息
- 对于list类型的字段，提取所有相关项
- 对于text类型的字段，可以适当整合多处信息

## 3. 证据追溯
- 为每个提取的信息记录来源的segment_id
- 将segment_id列表记录在 evidence_segment_ids 字段中
- 如果信息来自多个segment，记录所有相关的segment_id

## 4. 类型匹配
- type="text" (文本类型)：字符串，可以是句子或段落
- type="number" (数值类型)：数字（提取数字部分）
- type="list" (列表类型)：数组，按照item_schema的结构提取多个项
- type="boolean" (布尔值类型)：true/false

## 5. 必填字段
- is_required=true 的字段应优先提取
- 如果必填字段确实不存在，也可以为null

---

# 输出格式

返回JSON对象，结构如下：

```json
{{
  "field_name_1": "提取的值",
  "field_name_2": {{
    "value": "提取的值",
    "evidence_segment_ids": ["seg_id_1", "seg_id_2"]
  }},
  "field_name_3": [
    {{"item_key_1": "value1", "item_key_2": "value2"}},
    {{"item_key_1": "value3", "item_key_2": "value4"}}
  ],
  "_metadata": {{
    "stage": {self.stage},
    "stage_key": "{self.stage_key}",
    "extraction_method": "checklist_p0"
  }}
}}
```

**重要说明**：
1. ⚠️ JSON的key必须使用上面字段清单中的field_name（如project_name、owner_name等），不要使用中文key
2. 对于简单的文本/数值字段，可以直接返回值：`"project_name": "XX工程"`
3. 对于需要记录证据的字段，可以返回对象格式：`"project_name": {{"value": "XX工程", "evidence_segment_ids": ["seg_001"]}}`
4. 对于列表字段（type="list"），返回数组，每个元素按照item_schema的结构
5. 所有提取的值都用中文表述
6. 不存在的信息应为null，不要返回空字符串""

---

# 示例

假设字段清单中有：
- field_name: "project_name" (项目名称)
- field_name: "owner_name" (采购人)
- field_name: "budget" (预算金额)

在文档中找到 "[SEG:seg_001] XX市政道路改造工程招标公告，采购人：XX市交通局，预算500万元"

则返回（注意key必须是field_name）：

```json
{{
  "project_name": "XX市政道路改造工程",
  "owner_name": "XX市交通局",
  "budget": "500万元",
  "_metadata": {{
    "stage": {self.stage},
    "stage_key": "{self.stage_key}",
    "extraction_method": "checklist_p0"
  }}
}}
```

或带证据的格式：

```json
{{
  "project_name": {{
    "value": "XX市政道路改造工程",
    "evidence_segment_ids": ["seg_001"]
  }},
  "owner_name": {{
    "value": "XX市交通局",
    "evidence_segment_ids": ["seg_001"]
  }},
  "budget": {{
    "value": "500万元",
    "evidence_segment_ids": ["seg_001"]
  }},
  "_metadata": {{
    "stage": {self.stage},
    "stage_key": "{self.stage_key}",
    "extraction_method": "checklist_p0"
  }}
}}
```

---

请开始提取，返回完整的JSON对象。记住：JSON的key必须是field_name（英文），值用中文。
"""
        
        return prompt
    
    def build_p1_prompt(
        self,
        context_text: str,
        p0_result: Dict[str, Any],
        context_info: Optional[Dict] = None
    ) -> str:
        """
        构建P1阶段Prompt（补充扫描）
        
        Args:
            context_text: 招标文档上下文
            p0_result: P0阶段的提取结果
            context_info: 前序stage的结果
        
        Returns:
            P1补充扫描的Prompt
        """
        prompt = f"""# 角色与任务

你是一位资深的招投标文件分析专家。你的任务是：对已提取的**{self.stage_name}**信息进行补充和完善。

## 当前阶段：Stage {self.stage} - {self.stage_name} (P1补充扫描)

{self.description}

---

# 已提取的信息（P0阶段）

以下是基于标准清单已经提取的信息：

```json
{json.dumps(p0_result, ensure_ascii=False, indent=2)}
```

---

# 招标文档片段

{context_text}

---

# 补充任务

请分析招标文档，补充P0阶段**遗漏或不完整**的信息：

## 1. 检查必填字段
- 检查所有标记为必填的字段是否已填写
- 如果必填字段为空，尝试从文档中补充

## 2. 扩展已有字段
- 对于已有信息，检查是否可以补充更多细节
- 例如：如果只有项目名称，可以补充项目编号

## 3. 发现新信息
- 寻找P0清单中未涵盖但重要的信息
- 例如：特殊说明、备注、附加要求等

## 4. 完善证据
- 为缺少证据segment_id的字段补充证据

---

# 输出格式

返回JSON对象，仅包含**需要补充或修改**的字段：

```json
{{
  "field_name_to_supplement": {{
    "value": "补充的值",
    "evidence_segment_ids": ["seg_id"],
    "supplement_reason": "补充原因说明"
  }},
  "new_field_name": {{
    "value": "新发现的信息",
    "evidence_segment_ids": ["seg_id"],
    "supplement_reason": "P0未覆盖的重要信息"
  }},
  "_metadata": {{
    "stage": {self.stage},
    "stage_key": "{self.stage_key}",
    "extraction_method": "checklist_p1",
    "supplements_count": 2
  }}
}}
```

**重要说明**：
1. 如果P0阶段的提取已经很完整，可以返回空对象 {{}}
2. 只返回需要补充或修改的字段，不要重复返回P0已有的完整信息
3. ⚠️ JSON的key必须使用英文字段名（如project_name、owner_name等），与P0阶段一致
4. 每个补充项必须用中文说明补充原因（supplement_reason字段）
5. 所有补充的值都必须用中文表述
6. 必须提供证据segment_id

---

请开始补充扫描，返回JSON对象。记住：key用英文field_name，值用中文。
"""
        
        return prompt
    
    def _extract_json_from_llm_output(self, llm_output: str) -> str:
        """
        从LLM输出中提取JSON内容
        
        处理以下情况：
        1. 纯JSON
        2. Markdown代码块包裹的JSON: ```json\n{...}\n```
        3. 带有额外文本说明的JSON
        """
        if not llm_output or not llm_output.strip():
            logger.warning("LLM输出为空")
            return "{}"
        
        # 去除首尾空白
        content = llm_output.strip()
        
        # 情况1：尝试直接解析
        if content.startswith('{') or content.startswith('['):
            return content
        
        # 情况2：提取Markdown代码块中的JSON
        import re
        # 匹配 ```json 或 ``` 包裹的内容
        code_block_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
        matches = re.findall(code_block_pattern, content, re.DOTALL)
        if matches:
            # 返回第一个代码块的内容
            extracted = matches[0].strip()
            logger.debug(f"从markdown代码块提取JSON (长度={len(extracted)})")
            return extracted
        
        # 情况3：查找第一个 { 到最后一个 } 之间的内容
        first_brace = content.find('{')
        last_brace = content.rfind('}')
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            extracted = content[first_brace:last_brace+1]
            logger.debug(f"从花括号提取JSON (长度={len(extracted)})")
            return extracted
        
        # 如果都失败，记录警告并返回原内容
        logger.warning(f"无法提取JSON，返回原内容 (长度={len(content)}, 前100字符={content[:100]})")
        return content
    
    def parse_p0_response(self, llm_output: str) -> Dict[str, Any]:
        """
        解析P0阶段的LLM响应
        
        Args:
            llm_output: LLM返回的JSON字符串
        
        Returns:
            解析后的数据结构
        """
        try:
            # 先提取JSON内容
            json_content = self._extract_json_from_llm_output(llm_output)
            data = json.loads(json_content)
            
            # 验证数据结构
            if not isinstance(data, dict):
                raise ValueError(f"Expected dict, got {type(data)}")
            
            # 提取metadata
            metadata = data.pop("_metadata", {})
            
            # 标准化字段格式
            standardized = {}
            evidence_map = {}
            
            for field_name, value in data.items():
                # 如果value是对象且包含value和evidence_segment_ids
                if isinstance(value, dict) and "value" in value:
                    standardized[field_name] = value["value"]
                    evidence_map[field_name] = value.get("evidence_segment_ids", [])
                else:
                    standardized[field_name] = value
                    evidence_map[field_name] = []
            
            logger.info(
                f"P0响应已解析: stage={self.stage}, "
                f"提取字段数={len(standardized)}, 含证据字段数={len([e for e in evidence_map.values() if e])}"
            )
            
            return {
                "data": standardized,
                "evidence_map": evidence_map,
                "metadata": metadata
            }
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse P0 response as JSON: {e}")
            logger.error(f"JSON content (first 500 chars): {json_content[:500]}")
            # 返回空数据而不是抛出异常
            return {
                "data": {},
                "evidence_map": {},
                "metadata": {"parse_error": str(e)}
            }
        except Exception as e:
            logger.error(f"Failed to parse P0 response: {e}")
            # 返回空数据而不是抛出异常
            return {
                "data": {},
                "evidence_map": {},
                "metadata": {"parse_error": str(e)}
            }
    
    def parse_p1_response(self, llm_output: str) -> Dict[str, Any]:
        """
        解析P1阶段的LLM响应
        
        Args:
            llm_output: LLM返回的JSON字符串
        
        Returns:
            补充的数据结构
        """
        try:
            # 先提取JSON内容
            json_content = self._extract_json_from_llm_output(llm_output)
            data = json.loads(json_content)
            
            if not isinstance(data, dict):
                raise ValueError(f"Expected dict, got {type(data)}")
            
            # 提取metadata
            metadata = data.pop("_metadata", {})
            
            # 标准化补充字段
            supplements = {}
            evidence_map = {}
            reasons = {}
            
            for field_name, value in data.items():
                if isinstance(value, dict):
                    supplements[field_name] = value.get("value")
                    evidence_map[field_name] = value.get("evidence_segment_ids", [])
                    reasons[field_name] = value.get("supplement_reason", "")
                else:
                    supplements[field_name] = value
                    evidence_map[field_name] = []
                    reasons[field_name] = ""
            
            logger.info(
                f"P1响应已解析: stage={self.stage}, "
                f"补充字段数={len(supplements)}"
            )
            
            return {
                "supplements": supplements,
                "evidence_map": evidence_map,
                "reasons": reasons,
                "metadata": metadata
            }
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse P1 response as JSON: {e}")
            logger.error(f"JSON content (first 500 chars): {json_content[:500]}")
            # 返回空补充
            return {
                "supplements": {},
                "evidence_map": {},
                "reasons": {},
                "metadata": {"parse_error": str(e)}
            }
        except Exception as e:
            logger.error(f"Failed to parse P1 response: {e}")
            # 返回空补充
            return {
                "supplements": {},
                "evidence_map": {},
                "reasons": {},
                "metadata": {"parse_error": str(e)}
            }
        except Exception as e:
            logger.error(f"Failed to parse P1 response: {e}")
            return {
                "supplements": {},
                "evidence_map": {},
                "reasons": {},
                "metadata": {}
            }
    
    def merge_p0_p1(
        self,
        p0_result: Dict[str, Any],
        p1_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        合并P0和P1的结果
        
        Args:
            p0_result: P0阶段的解析结果
            p1_result: P1阶段的解析结果
        
        Returns:
            合并后的最终数据
        """
        # 复制P0的数据
        merged_data = p0_result["data"].copy()
        merged_evidence = p0_result["evidence_map"].copy()
        
        # 应用P1的补充
        supplements = p1_result.get("supplements", {})
        p1_evidence = p1_result.get("evidence_map", {})
        
        for field_name, value in supplements.items():
            if value is not None:
                # P1补充的值覆盖或扩展P0的值
                if field_name in merged_data and isinstance(merged_data[field_name], list):
                    # 如果是列表，追加
                    if isinstance(value, list):
                        merged_data[field_name].extend(value)
                    else:
                        merged_data[field_name].append(value)
                else:
                    # 否则覆盖
                    merged_data[field_name] = value
                
                # 合并证据
                if field_name in p1_evidence and p1_evidence[field_name]:
                    merged_evidence[field_name] = list(set(
                        merged_evidence.get(field_name, []) + p1_evidence[field_name]
                    ))
        
        # 收集所有证据segment_ids
        all_evidence_ids = set()
        for segment_ids in merged_evidence.values():
            if segment_ids:
                all_evidence_ids.update(segment_ids)
        
        logger.info(
            f"P0+P1已合并: stage={self.stage}, "
            f"总字段数={len(merged_data)}, "
            f"证据片段数={len(all_evidence_ids)}, "
            f"P1补充数={len(supplements)}"
        )
        
        return {
            "data": merged_data,
            "evidence_segment_ids": sorted(list(all_evidence_ids)),
            "evidence_map": merged_evidence,
            "p1_supplements_count": len(supplements)
        }
    
    def convert_to_schema(self, merged_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        将合并结果转换为TenderInfoV3 Schema格式
        
        Args:
            merged_result: 合并后的结果
        
        Returns:
            符合Schema的数据结构
        """
        data = merged_result["data"]
        
        # 根据stage_key返回对应的结构
        # 这里已经是按照field_name提取的，直接返回即可
        result = {
            self.stage_key: data,
            "evidence_chunk_ids": merged_result.get("evidence_segment_ids", [])
        }
        
        logger.info(
            f"已转换为Schema格式: stage={self.stage}, key={self.stage_key}, "
            f"字段数={len(data)}"
        )
        
        return result

