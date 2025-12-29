"""
招投标应用 - Pydantic Schema 定义
包含所有 API 请求和响应的数据模型
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from .evidence import SpanRef


# 类型定义
TenderAssetKind = Literal["tender", "bid", "template", "custom_rule"]
TenderRunStatus = Literal["pending", "running", "success", "failed"]


# ==================== 项目相关 ====================

class ProjectCreateReq(BaseModel):
    """创建项目请求"""
    name: str = Field(..., min_length=1, description="项目名称")
    description: Optional[str] = Field(None, description="项目描述")


class ProjectOut(BaseModel):
    """项目输出模型"""
    id: str
    kb_id: str
    name: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None


# ==================== 运行任务相关 ====================

class RunOut(BaseModel):
    """任务运行状态输出"""
    id: str
    project_id: Optional[str] = None
    kind: Optional[str] = None  # extract_project_info, extract_risks, generate_directory, extract_rule_set, review
    status: TenderRunStatus
    progress: Optional[float] = None
    message: Optional[str] = None
    result_json: Optional[Any] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ExtractReq(BaseModel):
    """通用抽取请求"""
    model_id: Optional[str] = None


# ==================== 资产相关 ====================

class AssetOut(BaseModel):
    """资产输出模型"""
    id: str
    project_id: str
    kind: TenderAssetKind
    title: Optional[str] = None
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    kb_doc_id: Optional[str] = None  # tender/bid/custom_rule 入库后的文档ID
    storage_path: Optional[str] = None  # template 的磁盘路径
    bidder_name: Optional[str] = None  # bid 时必填
    meta_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


# ==================== Chunk 查询相关 ====================

class ChunkLookupReq(BaseModel):
    """Chunk 查询请求"""
    chunk_ids: List[str] = Field(default_factory=list)


class ChunkOut(BaseModel):
    """Chunk 输出模型"""
    chunk_id: str
    doc_id: str
    title: Optional[str] = None
    url: Optional[str] = None
    position: Optional[int] = None
    content: str


# ==================== 目录相关 ====================

class DirectoryNodeIn(BaseModel):
    """目录节点输入模型"""
    numbering: str = Field(..., description="编号，如 1, 1.1, 1.1.1")
    level: int = Field(..., ge=1, description="层级，1表示顶级")
    title: str = Field(..., min_length=1, description="标题")
    required: bool = Field(True, description="是否必须提供")
    notes: Optional[str] = Field(None, description="备注")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="证据chunk_ids")


class DirectoryNodeOut(BaseModel):
    """目录节点输出模型"""
    numbering: str
    level: int
    title: str
    required: bool = True
    notes: Optional[str] = None
    evidence_chunk_ids: List[str] = Field(default_factory=list)


class DirectorySaveReq(BaseModel):
    """保存目录请求"""
    nodes: List[DirectoryNodeIn] = Field(default_factory=list)


# ==================== 审核相关 ====================

class ReviewRunReq(BaseModel):
    """审核运行请求"""
    model_id: Optional[str] = None
    bidder_name: Optional[str] = Field(None, description="投标人名称（选择投标人）")
    bid_asset_ids: List[str] = Field(default_factory=list, description="投标资产ID列表（精确指定文件）")
    
    # 新字段：规则文件资产 IDs
    custom_rule_asset_ids: List[str] = Field(default_factory=list, description="自定义规则文件资产ID列表")
    
    # 新字段：规则包 IDs
    custom_rule_pack_ids: List[str] = Field(default_factory=list, description="自定义规则包ID列表")
    
    # 新字段：LLM语义审核
    use_llm_semantic: bool = Field(True, description="是否使用LLM语义审核（QA验证，默认True）")
    
    # 旧字段：兼容（前端没升级时也不炸）
    custom_rule_set_ids: Optional[List[str]] = Field(None, description="[已弃用] 兼容旧字段")

    @model_validator(mode="after")
    def _merge_compat(self):
        """兼容旧字段：把 custom_rule_set_ids 合并到 custom_rule_asset_ids"""
        if self.custom_rule_set_ids:
            # 合并去重
            merged = list(dict.fromkeys([*(self.custom_rule_asset_ids or []), *self.custom_rule_set_ids]))
            self.custom_rule_asset_ids = merged
        return self


# ==================== 项目信息相关 ====================

class ProjectInfoOut(BaseModel):
    """项目信息输出模型"""
    project_id: str
    data_json: Dict[str, Any] = Field(default_factory=dict)
    evidence_chunk_ids: List[str] = Field(default_factory=list)
    evidence_spans: Optional[List[SpanRef]] = Field(None, description="证据片段引用（新字段）")
    updated_at: Optional[datetime] = None


# ==================== 风险相关 ====================

class RiskOut(BaseModel):
    """风险输出模型"""
    id: str
    project_id: str
    risk_type: Literal["mustReject", "other"]
    title: str
    description: Optional[str] = None
    suggestion: Optional[str] = None
    severity: Optional[str] = None  # low, medium, high, critical
    tags: List[str] = Field(default_factory=list)
    evidence_chunk_ids: List[str] = Field(default_factory=list)
    evidence_spans: Optional[List[SpanRef]] = Field(None, description="证据片段引用（新字段）")


# ==================== 审核项相关 ====================

class ReviewItemOut(BaseModel):
    """审核项输出模型（V3版本）"""
    id: str
    project_id: str
    source: str = "v3"  # V3流水线
    dimension: str  # 维度：资格审查、报价审查、技术审查等
    requirement_text: Optional[str] = None  # 招标要求（摘要）
    response_text: Optional[str] = None  # 投标响应（摘要）
    result: str  # pass, risk, fail (旧字段，兼容)
    status: Optional[str] = None  # PASS, WARN, FAIL, PENDING (V3新字段)
    evaluator: Optional[str] = None  # 评估器：deterministic, quant_check, semantic_llm, consistency (V3新字段)
    requirement_id: Optional[str] = None  # 关联的requirement_id (V3新字段)
    matched_response_id: Optional[str] = None  # 匹配的response_id (V3新字段)
    evidence_json: Optional[List[Dict[str, Any]]] = Field(None, description="统一证据结构（V3）")
    rule_trace_json: Optional[Dict[str, Any]] = Field(None, description="规则追踪（V3）")
    computed_trace_json: Optional[Dict[str, Any]] = Field(None, description="计算过程追踪（V3）")
    remark: Optional[str] = None  # 原因/建议/缺失点/冲突点
    rigid: bool = False  # 是否刚性要求
    rule_id: Optional[str] = None  # 规则ID（保留兼容）
    tender_evidence_chunk_ids: List[str] = Field(default_factory=list)
    bid_evidence_chunk_ids: List[str] = Field(default_factory=list)
    tender_evidence_spans: Optional[List[SpanRef]] = Field(None, description="招标证据片段引用（新字段）")
    bid_evidence_spans: Optional[List[SpanRef]] = Field(None, description="投标证据片段引用（新字段）")
