"""
附件相关的 Schema
"""
from pydantic import BaseModel, Field
from typing import Optional


class AttachmentUploadResponse(BaseModel):
    """附件上传响应"""
    id: str
    name: str  # original_name
    size: int
    mime: str  # mime_type
    text_length: int
    created_at: Optional[str] = None


class AttachmentDeleteResponse(BaseModel):
    """附件删除响应"""
    success: bool
    message: str
