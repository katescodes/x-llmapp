"""
证据链相关的公共数据模型
用于多文档、多业务系统的证据追溯
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class SpanRef(BaseModel):
    """
    证据片段引用（Span Reference）
    用于精确定位证据在文档中的位置，支持页码、边界框、文本偏移等
    
    目标：为多文档、多业务系统、审核可追溯提供统一的证据链模型
    """
    
    # 文档版本ID（可选，用于关联 DocStore 的 document_versions）
    doc_version_id: Optional[str] = Field(None, description="文档版本ID")
    
    # 页码（至少要有）
    page_no: Optional[int] = Field(None, ge=1, description="页码（从1开始）")
    
    # 边界框坐标（可选，用于 PDF 等格式的精确定位）
    # [x0, y0, x1, y1] 左上角和右下角坐标
    bbox: Optional[List[float]] = Field(None, description="边界框坐标 [x0, y0, x1, y1]")
    
    # 文本偏移（可选，用于纯文本文档的字符级定位）
    text_offset: Optional[dict] = Field(None, description="文本偏移 {start: int, end: int}")
    
    # 引用文本（可选，短引用，用于展示和去重）
    quote: Optional[str] = Field(None, max_length=200, description="引用文本片段（<=200字）")
    
    # 引用文本哈希（可选，用于去重）
    quote_hash: Optional[str] = Field(None, description="引用文本的哈希值")
    
    class Config:
        # 允许任意类型（为未来扩展保留）
        extra = "allow"

