from typing import Optional
from pydantic import BaseModel, Field


class KbCategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="分类唯一标识")
    display_name: str = Field(..., min_length=1, max_length=100, description="显示名称")
    color: str = Field(default="#6b7280", max_length=20, description="颜色代码")
    icon: str = Field(default="📁", max_length=10, description="图标emoji")
    description: Optional[str] = Field(default="", max_length=500, description="分类描述")


class KbCategoryCreate(KbCategoryBase):
    pass


class KbCategoryUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    color: Optional[str] = Field(None, max_length=20)
    icon: Optional[str] = Field(None, max_length=10)
    description: Optional[str] = Field(None, max_length=500)


class KbCategoryOut(KbCategoryBase):
    id: str
    created_at: str

