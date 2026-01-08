"""
自定义规则管理 - Pydantic Schema 定义
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ==================== 规则包相关 ====================

class CustomRulePackCreateReq(BaseModel):
    """创建自定义规则包请求"""
    project_id: Optional[str] = Field(None, description="项目ID（可选，不传则创建共享规则包）")
    pack_name: str = Field(..., min_length=1, description="规则包名称")
    rule_requirements: str = Field(..., min_length=1, description="规则要求文本（用户输入）")
    model_id: Optional[str] = Field(None, description="使用的模型ID")


class CustomRulePackOut(BaseModel):
    """规则包输出模型"""
    id: str
    pack_name: str
    pack_type: Literal["builtin", "custom"]
    project_id: Optional[str] = None
    priority: int = 0
    is_active: bool = True
    rule_count: Optional[int] = None  # 规则数量
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ==================== 规则相关 ====================

class CustomRuleOut(BaseModel):
    """规则输出模型"""
    id: str
    rule_pack_id: str
    rule_key: str
    rule_name: str
    dimension: str  # qualification/technical/business/price/doc_structure/schedule_quality/other
    evaluator: Literal["deterministic", "semantic_llm"]
    condition_json: Dict[str, Any]
    severity: Literal["low", "medium", "high"]
    is_hard: bool = False
    created_at: Optional[datetime] = None

