"""
Project Info V2 Schema - Pydantic 模型定义

用于校验 LLM 返回的项目信息 JSON 结构
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class TechnicalParameter(BaseModel):
    """技术参数"""
    category: Optional[str] = None
    name: Optional[str] = None
    requirement: Optional[str] = None
    evidence_chunk_ids: List[str] = Field(default_factory=list)


class BusinessTerm(BaseModel):
    """商务条款"""
    category: Optional[str] = None
    term: Optional[str] = None
    content: Optional[str] = None
    evidence_chunk_ids: List[str] = Field(default_factory=list)


class ScoringItem(BaseModel):
    """评分项"""
    category: Optional[str] = None
    item: Optional[str] = None
    score: Optional[float] = None
    scoring_method: Optional[str] = None
    evidence_chunk_ids: List[str] = Field(default_factory=list)


class ScoringCriteria(BaseModel):
    """评分标准"""
    items: List[ScoringItem] = Field(default_factory=list)


class ProjectBase(BaseModel):
    """项目基础信息"""
    projectName: Optional[str] = None
    projectNumber: Optional[str] = None
    ownerName: Optional[str] = None
    agentName: Optional[str] = None
    budget: Optional[str] = None
    fundSource: Optional[str] = None
    procurementMethod: Optional[str] = None
    evaluationMethod: Optional[str] = None


class ProjectInfoData(BaseModel):
    """项目信息数据（完整结构）"""
    base: ProjectBase = Field(default_factory=ProjectBase)
    technical_parameters: List[TechnicalParameter] = Field(default_factory=list)
    business_terms: List[BusinessTerm] = Field(default_factory=list)
    scoring_criteria: ScoringCriteria = Field(default_factory=ScoringCriteria)


class ProjectInfoV2(BaseModel):
    """
    Project Info V2 顶层模型
    
    约束：
    - 结构必须正确（data 存在且包含 base/technical_parameters/business_terms/scoring_criteria）
    - 允许字段缺失或为空，但类型必须正确
    - technical_parameters/business_terms 必须是 list
    - scoring_criteria.items 必须是 list
    """
    data: ProjectInfoData = Field(default_factory=ProjectInfoData)
    
    def to_dict_exclude_none(self) -> dict:
        """导出为 dict，排除 None 值"""
        return self.model_dump(exclude_none=True, by_alias=True)

