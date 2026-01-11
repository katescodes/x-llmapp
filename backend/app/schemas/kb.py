from typing import List, Optional
from pydantic import BaseModel, Field

from .types import KbCategory


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default="", max_length=2000)
    category_id: Optional[str] = Field(default=None, description="知识库分类ID")


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    category_id: Optional[str] = Field(default=None, description="知识库分类ID")


class KnowledgeBaseOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    category_display_name: Optional[str] = None
    category_color: Optional[str] = None
    category_icon: Optional[str] = None
    scope: Optional[str] = 'private'
    owner_id: Optional[str] = None
    organization_id: Optional[str] = None
    created_at: str
    updated_at: str


class DocumentOut(BaseModel):
    id: str
    filename: str
    source: str
    status: str
    created_at: str
    updated_at: str
    meta: dict
    kb_category: KbCategory = "general_doc"


class ImportResult(BaseModel):
    filename: str
    status: str
    doc_id: Optional[str] = None
    chunks: Optional[int] = None
    error: Optional[str] = None


class ImportResponse(BaseModel):
    items: List[ImportResult]

