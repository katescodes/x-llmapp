"""
风险分析聚合接口的 Schema 定义
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RiskRow(BaseModel):
    """废标项/关键硬性要求行"""
    id: str = Field(..., description="记录ID")
    requirement_id: str = Field(..., description="要求ID")
    dimension: str = Field(..., description="维度")
    req_type: str = Field(..., description="要求类型")
    requirement_text: str = Field(..., description="招标要求原文")
    allow_deviation: bool = Field(..., description="是否允许偏离")
    value_schema_json: Optional[Dict[str, Any]] = Field(None, description="值约束")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="证据chunk IDs")
    
    # 派生字段
    consequence: str = Field(..., description="后果: reject|hard_requirement|score_loss")
    severity: str = Field(..., description="严重性: high|medium|low")
    suggestion: str = Field(..., description="建议")


class ChecklistRow(BaseModel):
    """注意事项/得分点行"""
    id: str = Field(..., description="记录ID")
    requirement_id: str = Field(..., description="要求ID")
    dimension: str = Field(..., description="维度")
    req_type: str = Field(..., description="要求类型")
    requirement_text: str = Field(..., description="招标要求原文")
    allow_deviation: bool = Field(..., description="是否允许偏离")
    value_schema_json: Optional[Dict[str, Any]] = Field(None, description="值约束")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="证据chunk IDs")
    
    # 派生字段
    category: str = Field(..., description="类别")
    severity: str = Field(..., description="严重性: high|medium|low")
    title: str = Field(..., description="标题/要点")
    detail: str = Field(..., description="说明")
    suggestion: str = Field(..., description="建议")


class RiskAnalysisStats(BaseModel):
    """统计信息"""
    total_requirements: int = Field(..., description="总要求数")
    must_reject_count: int = Field(..., description="废标项数量")
    checklist_count: int = Field(..., description="注意事项数量")
    high_severity_count: int = Field(..., description="高严重性数量")
    medium_severity_count: int = Field(..., description="中严重性数量")
    low_severity_count: int = Field(..., description="低严重性数量")


class RiskAnalysisResponse(BaseModel):
    """风险分析聚合响应"""
    must_reject_table: List[RiskRow] = Field(..., description="废标项/关键硬性要求表")
    checklist_table: List[ChecklistRow] = Field(..., description="注意事项/得分点表")
    stats: RiskAnalysisStats = Field(..., description="统计信息")

