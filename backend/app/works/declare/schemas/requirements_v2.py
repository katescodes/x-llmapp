"""
申报要求 Schema (v2)
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, root_validator


class EligibilityCondition(BaseModel):
    """资格条件"""
    condition: str = Field(..., min_length=1, description="条件描述")
    category: Optional[str] = Field(None, description="条件分类（基本条件/专项条件等）")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="证据chunk IDs")

    def to_dict_exclude_none(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class MaterialRequired(BaseModel):
    """申报材料"""
    material: str = Field(..., min_length=1, description="材料名称")
    required: bool = Field(True, description="是否必须")
    format_requirements: Optional[str] = Field(None, description="格式要求")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="证据chunk IDs")

    def to_dict_exclude_none(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class Deadline(BaseModel):
    """时间节点"""
    event: str = Field(..., min_length=1, description="事件描述")
    date_text: str = Field(..., min_length=1, description="时间文本（如'11月5日前'）")
    notes: Optional[str] = Field(None, description="备注")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="证据chunk IDs")

    def to_dict_exclude_none(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class ContactInfo(BaseModel):
    """咨询方式"""
    contact_type: str = Field(..., description="联系类型（电话/邮箱/地址）")
    contact_value: str = Field(..., description="联系信息")
    notes: Optional[str] = Field(None, description="备注")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="证据chunk IDs")

    def to_dict_exclude_none(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class EvaluationCriterion(BaseModel):
    """评审标准/评分细则"""
    criterion: str = Field(..., min_length=1, description="评审项名称（如'技术创新'）")
    score: Optional[float] = Field(None, description="分值")
    description: Optional[str] = Field(None, description="评分细则说明")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="证据chunk IDs")

    def to_dict_exclude_none(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class FieldDefinition(BaseModel):
    """申报书字段定义"""
    field_name: str = Field(..., min_length=1, description="字段名称（如'enterprise_name'）")
    field_label: str = Field(..., min_length=1, description="字段标签（如'企业全称'）")
    is_required: bool = Field(True, description="是否必填")
    field_type: Optional[str] = Field(None, description="字段类型（text/number/date/file等）")
    constraints: Optional[str] = Field(None, description="填写要求或约束说明")
    max_length: Optional[int] = Field(None, description="最大长度")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="证据chunk IDs")

    def to_dict_exclude_none(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class SpecialRequirement(BaseModel):
    """特殊要求/注意事项"""
    requirement: str = Field(..., min_length=1, description="特殊要求内容")
    category: Optional[str] = Field(None, description="要求分类（禁止事项/注意事项等）")
    severity: Optional[str] = Field(None, description="严重程度（必须/建议/禁止）")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="证据chunk IDs")

    def to_dict_exclude_none(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class RequirementsDataV2(BaseModel):
    """申报要求数据"""
    eligibility_conditions: List[EligibilityCondition] = Field(
        default_factory=list, description="资格条件列表"
    )
    materials_required: List[MaterialRequired] = Field(default_factory=list, description="材料清单")
    deadlines: List[Deadline] = Field(default_factory=list, description="时间节点")
    contact_info: List[ContactInfo] = Field(default_factory=list, description="咨询方式")
    evaluation_criteria: List[EvaluationCriterion] = Field(
        default_factory=list, description="评审标准/评分细则"
    )
    field_definitions: List[FieldDefinition] = Field(
        default_factory=list, description="申报书字段定义"
    )
    special_requirements: List[SpecialRequirement] = Field(
        default_factory=list, description="特殊要求/注意事项"
    )
    summary: Optional[str] = Field(None, description="申报要求摘要")

    def to_dict_exclude_none(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class RequirementsResultV2(BaseModel):
    """申报要求抽取结果"""
    data: RequirementsDataV2 = Field(..., description="结构化要求数据")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="所有引用的证据chunk IDs")

    @root_validator(pre=True)
    def collect_all_evidence_chunk_ids(cls, values):
        """自动收集所有子项的 evidence_chunk_ids"""
        data = values.get("data")
        if data and isinstance(data, dict):
            all_ids = set()
            # 收集各个列表的 evidence_chunk_ids
            for cond in data.get("eligibility_conditions", []):
                if isinstance(cond, dict):
                    all_ids.update(cond.get("evidence_chunk_ids", []))
            for mat in data.get("materials_required", []):
                if isinstance(mat, dict):
                    all_ids.update(mat.get("evidence_chunk_ids", []))
            for dl in data.get("deadlines", []):
                if isinstance(dl, dict):
                    all_ids.update(dl.get("evidence_chunk_ids", []))
            for ci in data.get("contact_info", []):
                if isinstance(ci, dict):
                    all_ids.update(ci.get("evidence_chunk_ids", []))
            for ec in data.get("evaluation_criteria", []):
                if isinstance(ec, dict):
                    all_ids.update(ec.get("evidence_chunk_ids", []))
            for fd in data.get("field_definitions", []):
                if isinstance(fd, dict):
                    all_ids.update(fd.get("evidence_chunk_ids", []))
            for sr in data.get("special_requirements", []):
                if isinstance(sr, dict):
                    all_ids.update(sr.get("evidence_chunk_ids", []))
            values["evidence_chunk_ids"] = sorted(list(all_ids))
        return values

    def to_dict_exclude_none(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)

