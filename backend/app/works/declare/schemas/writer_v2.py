"""
文档生成 Schema (v2)
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Claim(BaseModel):
    """声明/主张"""
    text: str = Field(..., min_length=1, description="声明文本")
    grounded: bool = Field(..., description="是否有证据支持")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="证据chunk IDs（grounded=true时必须）")

    def to_dict_exclude_none(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class DocumentContentV2(BaseModel):
    """文档内容"""
    final_content_md: str = Field(..., description="最终内容（Markdown格式）")
    claims: List[Claim] = Field(default_factory=list, description="声明列表")
    summary: Optional[str] = Field(None, description="文档摘要")

    def to_dict_exclude_none(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class DocumentResultV2(BaseModel):
    """文档生成结果"""
    data: DocumentContentV2 = Field(..., description="文档内容数据")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="所有引用的证据chunk IDs")

    def to_dict_exclude_none(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)

