"""
用户文档管理 - Pydantic Schema 定义
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ==================== 文档分类相关 ====================

class UserDocCategoryCreateReq(BaseModel):
    """创建文档分类请求"""
    project_id: str = Field(..., description="项目ID")
    category_name: str = Field(..., min_length=1, description="分类名称")
    category_desc: Optional[str] = Field(None, description="分类描述")
    display_order: int = Field(0, description="显示顺序")


class UserDocCategoryUpdateReq(BaseModel):
    """更新文档分类请求"""
    category_name: Optional[str] = Field(None, min_length=1, description="分类名称")
    category_desc: Optional[str] = Field(None, description="分类描述")
    display_order: Optional[int] = Field(None, description="显示顺序")


class UserDocCategoryOut(BaseModel):
    """文档分类输出模型"""
    id: str
    project_id: str
    category_name: str
    category_desc: Optional[str] = None
    display_order: int = 0
    doc_count: Optional[int] = None  # 该分类下的文档数量
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ==================== 用户文档相关 ====================

class UserDocumentCreateReq(BaseModel):
    """创建用户文档请求（通过表单）"""
    project_id: str = Field(..., description="项目ID")
    category_id: Optional[str] = Field(None, description="分类ID")
    doc_name: str = Field(..., min_length=1, description="文档名称")
    description: Optional[str] = Field(None, description="文档描述")
    doc_tags: List[str] = Field(default_factory=list, description="文档标签")


class UserDocumentUpdateReq(BaseModel):
    """更新用户文档请求"""
    doc_name: Optional[str] = Field(None, min_length=1, description="文档名称")
    category_id: Optional[str] = Field(None, description="分类ID")
    description: Optional[str] = Field(None, description="文档描述")
    doc_tags: Optional[List[str]] = Field(None, description="文档标签")


class UserDocumentOut(BaseModel):
    """用户文档输出模型"""
    id: str
    project_id: str
    category_id: Optional[str] = None
    category_name: Optional[str] = None  # 分类名称（关联查询）
    doc_name: str
    filename: str
    file_type: str
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    storage_path: Optional[str] = None
    kb_doc_id: Optional[str] = None
    doc_tags: List[str] = []
    description: Optional[str] = None
    is_analyzed: bool = False
    analysis_json: Dict[str, Any] = {}
    meta_json: Dict[str, Any] = {}
    owner_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserDocumentAnalyzeReq(BaseModel):
    """文档分析请求"""
    model_id: Optional[str] = Field(None, description="使用的模型ID")

