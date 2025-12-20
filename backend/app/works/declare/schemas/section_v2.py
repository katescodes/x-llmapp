"""
章节自动填充 Schema (v2)
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SectionContentV2(BaseModel):
    """章节内容"""
    content_md: str = Field(..., description="章节内容（Markdown格式）")
    summary: Optional[str] = Field(None, description="内容摘要")
    confidence: Optional[str] = Field(None, description="置信度（high/medium/low）")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="证据chunk IDs")

    def to_dict_exclude_none(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class SectionResultV2(BaseModel):
    """章节填充结果"""
    data: SectionContentV2 = Field(..., description="章节内容数据")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="所有引用的证据chunk IDs")

    def to_dict_exclude_none(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)

