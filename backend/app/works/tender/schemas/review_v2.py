"""
审查结果 Schema V2
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator


class ReviewItemV2(BaseModel):
    """审查项 V2"""
    source: str = Field(default="compare", description="来源")
    dimension: str = Field(..., min_length=1, description="审查维度/项")
    requirement_text: str = Field(..., description="要求描述")
    response_text: str = Field(..., description="响应描述")
    result: Literal["pass", "risk", "fail"] = Field(..., description="审查结果")
    rigid: bool = Field(False, description="是否刚性")
    notes: Optional[str] = Field(None, description="备注")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="证据 chunk IDs")
    
    @field_validator('dimension')
    @classmethod
    def dimension_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("dimension 不能为空")
        return v.strip()
    
    def to_dict_exclude_none(self):
        """转为字典，排除 None 值"""
        return self.model_dump(exclude_none=True)


class ReviewDataV2(BaseModel):
    """审查数据 V2"""
    items: List[ReviewItemV2] = Field(..., min_length=1, description="审查项列表")
    
    @field_validator('items')
    @classmethod
    def items_not_empty(cls, v):
        if not v:
            raise ValueError("items 数组不能为空")
        return v


class ReviewResultV2(BaseModel):
    """审查结果 V2"""
    data: ReviewDataV2 = Field(..., description="审查数据")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="全局证据")
    
    def to_dict_exclude_none(self):
        """转为字典，排除 None 值"""
        return self.model_dump(exclude_none=True)

