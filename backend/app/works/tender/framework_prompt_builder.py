"""
框架式招标要求提取 - 系统定框架，LLM自主分析
"""
from typing import List, Dict, Any, Optional
import json


class FrameworkPromptBuilder:
    """
    框架式提取构建器：
    - 系统提供结构化框架（维度、类型、字段）
    - LLM自主识别和提取所有要求
    - 输出结构化结果，便于审核流程对接
    """
    
    def __init__(self):
        # 定义维度框架
        self.dimensions = {
            "price": "价格维度：投标报价、费用明细、价格计算规则等",
            "qualification": "资质维度：企业资质、人员资格、业绩要求等",
            "technical": "技术维度：技术方案、性能参数、质量标准等",
            "commercial": "商务维度：工期、质保、付款方式、违约责任等",
            "scoring": "评分维度：评分标准、打分规则、加分项等",
            "other": "其他维度：废标条件、特殊要求等"
        }
        
        # 定义要求类型
        self.requirement_types = {
            "hard_gate": "硬性门槛：必须满足，否则废标（如资质必备、最高限价）",
            "quantitative": "定量检查：有明确数值或标准，可精确验证（如工期≤90天、资质等级≥二级）",
            "semantic": "语义评估：需理解和判断，无明确标准（如方案合理性、经验丰富度）"
        }
        
        # 定义规范化键（用于审核）
        self.norm_keys = {
            "total_price_cny": "投标总价（元）",
            "duration_days": "工期（天）",
            "warranty_months": "质保期（月）",
            "qualification_level": "资质等级",
            "registered_capital_cny": "注册资本（元）"
        }
    
    def build_prompt(self, tender_context: str) -> str:
        """
        构建框架式提取prompt
        
        Args:
            tender_context: 招标文件上下文（检索到的相关分片）
        
        Returns:
            LLM提示词
        """
        prompt = f"""# 任务：招标要求自主提取

## 目标
从招标文件中**自主识别和提取所有审核要求**，不遗漏任何重要规则。

## 提取框架

### 1. 维度分类（dimension）
{self._format_dict(self.dimensions)}

### 2. 要求类型（requirement_type）
{self._format_dict(self.requirement_types)}

### 3. 规范化键（norm_key）- 用于精确审核
{self._format_dict(self.norm_keys)}
如不在上述范围，填 null

### 4. 输出结构（JSON数组）
```json
[
  {{
    "dimension": "维度标识",
    "requirement_type": "要求类型",
    "title": "要求简短标题",
    "requirement_text": "完整要求描述（原文或准确转述）",
    "norm_key": "规范化键（如适用）",
    "expected_value": "期望值/标准（如适用）",
    "operator": "比较运算符（≥, ≤, =, 范围等，如适用）",
    "is_mandatory": true/false,
    "evidence_text": "原文依据片段"
  }}
]
```

## 提取要求

### ✅ 必须提取
- **所有硬性门槛**：资质必备、最高限价、废标条件等
- **所有定量标准**：工期、质保期、人员数量、业绩金额等明确数值
- **评分规则**：每项评分标准和细则
- **商务条款**：付款方式、违约责任、特殊承诺等
- **技术要求**：性能参数、质量标准、方案要求等

### ❌ 必须排除
- **合同条款**：通用合同条款、法律条款、合同范本等
- **格式范例**：投标文件格式示例、表格模板等

### 📋 提取原则
1. **完整性**：不要遗漏任何审核要点，宁可多提不可漏提
2. **准确性**：原文为准，不要臆测或添加不存在的要求
3. **结构化**：每个要求独立一条，便于后续逐项审核
4. **可审核**：描述要具体，能明确判断投标文件是否满足

## 招标文件内容

{tender_context}

## 输出
请直接输出JSON数组，不要包含其他说明文字。
"""
        return prompt
    
    def _format_dict(self, d: Dict[str, str]) -> str:
        """格式化字典为可读列表"""
        return "\n".join([f"- **{k}**: {v}" for k, v in d.items()])
    
    def parse_llm_response(self, llm_response: str) -> List[Dict[str, Any]]:
        """
        解析LLM返回的JSON数组
        
        Args:
            llm_response: LLM返回的原始文本
        
        Returns:
            解析后的要求列表
        """
        # 清理可能的markdown包裹
        cleaned = llm_response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        
        try:
            requirements = json.loads(cleaned)
            if not isinstance(requirements, list):
                raise ValueError("LLM返回的不是JSON数组")
            return requirements
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM返回无法解析为JSON: {e}\n原始内容:\n{llm_response}")
    
    def convert_to_db_format(
        self,
        llm_requirements: List[Dict[str, Any]],
        project_id: int,
        doc_version_id: int
    ) -> List[Dict[str, Any]]:
        """
        将LLM提取的要求转换为数据库格式
        
        Args:
            llm_requirements: LLM提取的原始要求列表
            project_id: 项目ID
            doc_version_id: 文档版本ID
        
        Returns:
            可直接插入数据库的要求列表
        """
        db_requirements = []
        
        for idx, req in enumerate(llm_requirements, start=1):
            # 基础字段映射
            db_req = {
                "project_id": project_id,
                "doc_version_id": doc_version_id,
                "dimension": req.get("dimension", "other"),
                "item_id": f"auto_{req.get('dimension', 'other')}_{idx:03d}",
                "title": req.get("title", "未命名要求"),
                "requirement_text": req.get("requirement_text", ""),
                "requirement_type": req.get("requirement_type", "semantic"),
                "is_mandatory": req.get("is_mandatory", False),
                "meta_json": {}
            }
            
            # 规范化字段（用于审核）
            norm_key = req.get("norm_key")
            expected_value = req.get("expected_value")
            operator = req.get("operator")
            
            if norm_key:
                db_req["meta_json"]["norm_key"] = norm_key
            if expected_value is not None:
                db_req["meta_json"]["expected_value"] = expected_value
            if operator:
                db_req["meta_json"]["operator"] = operator
            
            # 原文依据
            evidence_text = req.get("evidence_text")
            if evidence_text:
                db_req["meta_json"]["evidence_text"] = evidence_text
            
            # 其他元数据
            for key in ["unit", "threshold", "scoring_rule"]:
                if key in req:
                    db_req["meta_json"][key] = req[key]
            
            db_requirements.append(db_req)
        
        return db_requirements
    
    def validate_requirement(self, req: Dict[str, Any]) -> List[str]:
        """
        验证单个要求的完整性
        
        Args:
            req: 要求字典
        
        Returns:
            错误信息列表（空列表表示验证通过）
        """
        errors = []
        
        # 必填字段检查
        if not req.get("dimension"):
            errors.append("缺少dimension字段")
        elif req["dimension"] not in self.dimensions:
            errors.append(f"无效的dimension: {req['dimension']}")
        
        if not req.get("requirement_type"):
            errors.append("缺少requirement_type字段")
        elif req["requirement_type"] not in self.requirement_types:
            errors.append(f"无效的requirement_type: {req['requirement_type']}")
        
        if not req.get("title"):
            errors.append("缺少title字段")
        
        if not req.get("requirement_text"):
            errors.append("缺少requirement_text字段")
        
        # 定量要求的特殊检查
        if req.get("requirement_type") == "quantitative":
            if not req.get("norm_key"):
                errors.append("定量要求(quantitative)必须指定norm_key")
        
        return errors

