"""
Project Info V2 Schema - Pydantic 模型定义

用于校验 LLM 返回的项目信息 JSON 结构

注意：这个Schema定义仅用于参考，实际存储时不做严格校验（直接存入JSONB）
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class TechnicalParameter(BaseModel):
    """技术参数（契约标准字段+方案D灵活性）"""
    # 契约要求的核心字段
    name: Optional[str] = None  # 参数/功能名称（契约required）
    value: Optional[str] = None  # 参数值/要求描述（契约required）
    
    # 契约optional字段
    category: Optional[str] = None  # 分类
    unit: Optional[str] = None  # 单位
    
    # 方案D补充字段
    remark: Optional[str] = None  # 备注
    description: Optional[str] = None  # 详细描述
    structured: Optional[Dict[str, Any]] = None  # 结构化信息（LLM自定义）
    parameters: Optional[List[Dict[str, Any]]] = None  # 子参数数组（可选）
    
    # 向后兼容旧字段名
    item: Optional[str] = None  # 兼容旧的item（映射到name）
    requirement: Optional[str] = None  # 兼容旧的requirement（映射到value）
    
    # 证据
    evidence_chunk_ids: List[str] = Field(default_factory=list)


class BusinessTerm(BaseModel):
    """商务条款（契约标准字段+方案D灵活性）"""
    # 契约要求的核心字段
    clause_type: Optional[str] = None  # 条款类型（契约required）
    content: Optional[str] = None  # 条款内容（契约required）
    
    # 契约optional字段
    clause_title: Optional[str] = None  # 条款标题
    
    # 方案D补充字段
    description: Optional[str] = None  # 详细描述
    structured: Optional[Dict[str, Any]] = None  # 结构化信息（LLM自定义）
    
    # 向后兼容旧字段名
    term: Optional[str] = None  # 兼容旧的term（映射到clause_type）
    requirement: Optional[str] = None  # 兼容旧的requirement（映射到content）
    
    # 证据
    evidence_chunk_ids: List[str] = Field(default_factory=list)


class ScoringItem(BaseModel):
    """评分项"""
    category: Optional[str] = None
    item: Optional[str] = None
    score: Optional[str] = None  # 改为str以支持"5-10分"、"最高10分"等描述
    rule: Optional[str] = None  # 得分规则（完整复制原文）
    scoring_method: Optional[str] = None
    evidence_chunk_ids: List[str] = Field(default_factory=list)


class ScoringCriteria(BaseModel):
    """评分标准"""
    evaluationMethod: Optional[str] = None  # 评标办法名称（如"综合评分法"）
    items: List[ScoringItem] = Field(default_factory=list)


class ProjectBase(BaseModel):
    """项目基础信息（方案D：支持自定义字段）"""
    # 核心字段（前端依赖）
    projectName: Optional[str] = None
    projectNumber: Optional[str] = None
    ownerName: Optional[str] = None
    agencyName: Optional[str] = None  # 代理机构
    agentName: Optional[str] = None    # 兼容旧字段
    bidDeadline: Optional[str] = None  # 投标截止时间
    bidOpeningTime: Optional[str] = None  # 开标时间
    budget: Optional[str] = None
    maxPrice: Optional[str] = None     # 最高限价
    bidBond: Optional[str] = None      # 投标保证金
    schedule: Optional[str] = None     # 工期要求
    quality: Optional[str] = None      # 质量要求
    location: Optional[str] = None     # 项目地点
    contact: Optional[str] = None      # 联系人
    fundSource: Optional[str] = None
    procurementMethod: Optional[str] = None
    evaluationMethod: Optional[str] = None
    
    # 证据字段（每个字段的来源chunk）
    evidence: Optional[Dict[str, List[str]]] = None
    
    # 允许额外字段（LLM自由添加的基本信息）
    class Config:
        extra = "allow"  # 允许额外的字段


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


