"""
项目删除相关的 Pydantic Schema
包含删除计划和删除确认请求
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class DeletePlanItem(BaseModel):
    """删除计划项：单类资源的删除信息"""
    type: str = Field(..., description="资源类型: DOCUMENT/KB/ASSET/RISK/DIRECTORY/REVIEW")
    count: int = Field(..., description="资源数量")
    samples: List[str] = Field(default_factory=list, description="样例名称（前N个）")
    physical_targets: List[str] = Field(default_factory=list, description="物理资源（如文件路径、索引名称）")


class ProjectDeletePlanResponse(BaseModel):
    """项目删除计划响应"""
    project_id: str
    project_name: str
    items: List[DeletePlanItem] = Field(default_factory=list)
    confirm_token: str = Field(..., description="确认令牌（SHA256）")
    warning: str = Field(default="此操作不可逆，请谨慎操作！")


class ProjectDeleteRequest(BaseModel):
    """项目删除确认请求"""
    confirm_text: Optional[str] = Field(None, description="用户输入的确认文本（可选，向后兼容）")
    confirm_token: str = Field(..., description="删除计划的确认令牌")
