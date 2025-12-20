"""
目录生成 Schema V2
"""
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class DirectoryNodeV2(BaseModel):
    """目录节点 V2"""
    title: str = Field(..., min_length=1, description="章节标题")
    level: int = Field(..., ge=1, le=6, description="层级 (1~6)")
    order_no: int = Field(..., ge=1, description="同级顺序号")
    parent_ref: Optional[str] = Field(None, description="父节点标题引用")
    required: bool = Field(True, description="是否必填")
    volume: Optional[str] = Field(None, description="卷号")
    notes: Optional[str] = Field(None, description="备注说明")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="证据 chunk IDs")
    
    @field_validator('title')
    @classmethod
    def title_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("title 不能为空")
        return v.strip()


class DirectoryDataV2(BaseModel):
    """目录数据 V2"""
    nodes: List[DirectoryNodeV2] = Field(..., min_length=1, description="目录节点列表")
    
    @field_validator('nodes')
    @classmethod
    def nodes_not_empty(cls, v):
        if not v:
            raise ValueError("nodes 数组不能为空")
        return v


class DirectoryResultV2(BaseModel):
    """目录生成结果 V2"""
    data: DirectoryDataV2 = Field(..., description="目录数据")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="全局证据 chunk IDs")
    
    def to_dict_exclude_none(self):
        """转为字典，排除 None 值"""
        return self.model_dump(exclude_none=True)

