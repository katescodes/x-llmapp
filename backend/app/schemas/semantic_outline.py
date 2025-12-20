"""
语义目录生成 - Pydantic 模型
支持从评分/要求推导多级目录 + 证据链
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ==================== 枚举类型 ====================

class RequirementType(str, Enum):
    """要求项类型"""
    TECH_SCORE = "TECH_SCORE"              # 技术评分点
    BIZ_SCORE = "BIZ_SCORE"                # 商务评分点
    QUALIFICATION = "QUALIFICATION"         # 资格条件
    TECH_SPEC = "TECH_SPEC"                # 技术参数/规格
    DELIVERY_ACCEPTANCE = "DELIVERY_ACCEPTANCE"  # 交付验收
    SERVICE_WARRANTY = "SERVICE_WARRANTY"   # 售后维保
    DOC_FORMAT = "DOC_FORMAT"              # 文档格式要求


class MustLevel(str, Enum):
    """要求强制级别"""
    MUST = "MUST"           # 必须满足
    SHOULD = "SHOULD"       # 应该满足
    OPTIONAL = "OPTIONAL"   # 可选
    UNKNOWN = "UNKNOWN"     # 未知


class OutlineMode(str, Enum):
    """语义目录生成模式"""
    FAST = "FAST"    # 快速模式：较少的LLM调用，适合预览
    FULL = "FULL"    # 完整模式：多轮LLM调用，覆盖度更高


class OutlineStatus(str, Enum):
    """语义目录生成状态"""
    SUCCESS = "SUCCESS"            # 成功
    LOW_COVERAGE = "LOW_COVERAGE"  # 覆盖率低但完成
    FAILED = "FAILED"              # 失败


# ==================== 要求项相关 ====================

class RequirementItem(BaseModel):
    """结构化要求项"""
    req_id: str = Field(description="要求项ID")
    req_type: RequirementType = Field(description="要求类型")
    title: str = Field(description="短标题（LLM生成）")
    content: str = Field(description="要求原文")
    params: Optional[Dict[str, Any]] = Field(default=None, description="结构化参数（KV）")
    score_hint: Optional[str] = Field(default=None, description="分值/评分描述")
    must_level: MustLevel = Field(default=MustLevel.UNKNOWN, description="强制级别")
    source_chunk_ids: List[str] = Field(default_factory=list, description="来源chunk IDs")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度")


class RequirementItemDB(RequirementItem):
    """数据库中的要求项（包含关联信息）"""
    project_id: str
    outline_id: str
    created_at: datetime
    updated_at: datetime


# ==================== 语义目录节点相关 ====================

class SemanticOutlineNode(BaseModel):
    """语义目录节点"""
    node_id: str = Field(description="节点ID")
    level: int = Field(ge=1, le=5, description="层级 1~5")
    numbering: Optional[str] = Field(default=None, description="编号如 1.2.3")
    title: str = Field(description="标题")
    summary: Optional[str] = Field(default=None, description="一句话说明（<=40字）")
    tags: List[str] = Field(default_factory=list, description="标签")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="证据chunk IDs")
    covered_req_ids: List[str] = Field(default_factory=list, description="覆盖的要求项IDs")
    children: List[SemanticOutlineNode] = Field(default_factory=list, description="子节点")


class SemanticOutlineNodeFlat(BaseModel):
    """扁平化的语义目录节点（用于数据库存储）"""
    node_id: str
    outline_id: str
    project_id: str
    parent_id: Optional[str] = None
    level: int
    order_no: int
    numbering: Optional[str] = None
    title: str
    summary: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    evidence_chunk_ids: List[str] = Field(default_factory=list)
    covered_req_ids: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ==================== 语义目录生成结果 ====================

class SemanticOutlineDiagnostics(BaseModel):
    """语义目录诊断信息"""
    total_req_count: int = Field(description="总要求项数")
    covered_req_count: int = Field(description="被覆盖的要求项数")
    coverage_rate: float = Field(ge=0.0, le=1.0, description="覆盖率")
    req_type_counts: Dict[str, int] = Field(default_factory=dict, description="各类型要求数量")
    total_nodes: int = Field(description="总节点数")
    l1_nodes: int = Field(description="一级节点数")
    max_depth: int = Field(description="实际最大深度")
    extraction_time_ms: Optional[int] = Field(default=None, description="要求抽取耗时(ms)")
    synthesis_time_ms: Optional[int] = Field(default=None, description="目录合成耗时(ms)")
    total_time_ms: Optional[int] = Field(default=None, description="总耗时(ms)")


class SemanticOutlineResult(BaseModel):
    """语义目录生成结果"""
    outline_id: str = Field(description="目录ID")
    project_id: str = Field(description="项目ID")
    status: OutlineStatus = Field(description="状态")
    outline: List[SemanticOutlineNode] = Field(default_factory=list, description="目录树")
    requirements: List[RequirementItem] = Field(default_factory=list, description="要求项列表")
    diagnostics: SemanticOutlineDiagnostics = Field(description="诊断信息")
    created_at: Optional[datetime] = None


# ==================== API 请求/响应 ====================

class SemanticOutlineGenerateRequest(BaseModel):
    """语义目录生成请求"""
    mode: OutlineMode = Field(default=OutlineMode.FAST, description="生成模式")
    max_depth: int = Field(default=5, ge=1, le=5, description="最大层级")


class SemanticOutlineGenerateResponse(BaseModel):
    """语义目录生成响应"""
    success: bool
    message: str
    result: Optional[SemanticOutlineResult] = None


class SemanticOutlineListResponse(BaseModel):
    """语义目录列表响应"""
    outlines: List[Dict[str, Any]] = Field(description="目录摘要列表")


# ==================== LLM 输出格式（内部使用） ====================

class RequirementItemLLMOutput(BaseModel):
    """LLM输出的要求项格式（用于解析）"""
    req_type: str
    title: str
    content: str
    params: Optional[Dict[str, Any]] = None
    score_hint: Optional[str] = None
    must_level: str = "UNKNOWN"
    source_chunk_ids: List[str]
    confidence: Optional[float] = 0.8


class OutlineNodeLLMOutput(BaseModel):
    """LLM输出的目录节点格式（用于解析）"""
    level: int
    title: str
    summary: Optional[str] = None
    tags: Optional[List[str]] = None
    covered_req_ids: List[str]
    children: Optional[List[OutlineNodeLLMOutput]] = None


# 允许递归引用
OutlineNodeLLMOutput.model_rebuild()
SemanticOutlineNode.model_rebuild()

