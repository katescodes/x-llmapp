"""
投标文件格式/样表/范本抽取 - 数据模型
从招标书blocks自动抽取投标文件格式，输出结构化结果
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ==================== 枚举类型 ====================

class TemplateKind(str, Enum):
    """投标文件格式/范本类型（覆盖80%常见）"""
    BID_LETTER = "BID_LETTER"                       # 投标函
    LEGAL_AUTHORIZATION = "LEGAL_AUTHORIZATION"     # 法人授权委托书
    PRICE_SCHEDULE = "PRICE_SCHEDULE"               # 报价表/报价文件
    DEVIATION_TABLE = "DEVIATION_TABLE"             # 偏离表（技术/商务）
    COMMITMENT_LETTER = "COMMITMENT_LETTER"         # 承诺书/响应承诺
    PERFORMANCE_TABLE = "PERFORMANCE_TABLE"         # 业绩表
    STAFF_TABLE = "STAFF_TABLE"                     # 人员表/社保
    CREDENTIALS_LIST = "CREDENTIALS_LIST"           # 证书清单
    OTHER = "OTHER"                                 # 兜底


class TemplateExtractStatus(str, Enum):
    """抽取状态"""
    SUCCESS = "SUCCESS"                 # 成功
    NOT_FOUND = "NOT_FOUND"             # 未找到范本块
    NEED_OCR = "NEED_OCR"               # 需要OCR（疑似扫描/图片范本）
    NEED_CONFIRM = "NEED_CONFIRM"       # 需要人工确认
    LOW_COVERAGE = "LOW_COVERAGE"       # 覆盖率不足


class EvidenceType(str, Enum):
    """证据类型"""
    PARAGRAPH = "PARAGRAPH"         # 段落
    TABLE_CELL = "TABLE_CELL"       # 表格单元格
    TEXTBOX = "TEXTBOX"             # 文本框
    IMAGE_ANCHOR = "IMAGE_ANCHOR"   # 图片锚点


class ExtractMode(str, Enum):
    """抽取模式"""
    NORMAL = "NORMAL"       # 正常模式
    ENHANCED = "ENHANCED"   # 增强模式（扩大召回）


# ==================== DTO类 ====================

class TemplateEvidenceDTO(BaseModel):
    """模板证据项（用于可解释预览）"""
    type: EvidenceType = Field(description="证据类型")
    block_id: str = Field(description="块ID")
    order_no: int = Field(description="排序号")
    score: float = Field(ge=0.0, le=1.0, description="得分")
    keywords_hit: List[str] = Field(default_factory=list, description="命中的关键词")
    snippet: str = Field(description="文本片段（200-400字）")
    reason: str = Field(description="命中原因")


class TemplateSpanDTO(BaseModel):
    """模板范围（一个抽取出的范本）"""
    kind: TemplateKind = Field(description="范本类型")
    display_title: str = Field(description="显示标题")
    start_block_id: str = Field(description="起始块ID")
    end_block_id: str = Field(description="结束块ID")
    confidence: float = Field(ge=0.0, le=1.0, description="置信度")
    evidence_block_ids: List[str] = Field(default_factory=list, description="证据块IDs")
    reason: str = Field(description="抽取原因")


class TemplateExtractDiagnostics(BaseModel):
    """抽取诊断信息"""
    recall_hit_count: int = Field(description="召回命中数")
    window_count: int = Field(description="窗口数")
    llm_call_count: int = Field(description="LLM调用次数")
    coverage_ratio: float = Field(ge=0.0, le=1.0, description="覆盖率")
    missing_kinds: List[TemplateKind] = Field(default_factory=list, description="缺失的范本类型")
    total_blocks: int = Field(description="总块数")
    text_density: float = Field(description="文本密度")
    image_anchor_count: int = Field(description="图片锚点数")
    extraction_time_ms: int = Field(description="抽取耗时(ms)")


class TemplateExtractResultDTO(BaseModel):
    """抽取结果"""
    status: TemplateExtractStatus = Field(description="状态")
    templates: List[TemplateSpanDTO] = Field(default_factory=list, description="抽取的范本列表")
    evidences: List[TemplateEvidenceDTO] = Field(default_factory=list, description="证据列表")
    diagnostics: TemplateExtractDiagnostics = Field(description="诊断信息")
    message: Optional[str] = Field(default=None, description="提示消息")


class TemplateConfirmRequest(BaseModel):
    """人工确认请求"""
    kind: TemplateKind = Field(description="范本类型")
    display_title: str = Field(description="显示标题")
    force_start_block_id: str = Field(description="强制起始块ID")
    force_end_block_id: Optional[str] = Field(default=None, description="强制结束块ID（可选）")


# ==================== 内部数据结构 ====================

class CandidateWindow(BaseModel):
    """候选窗口（内部使用）"""
    start_idx: int = Field(description="起始索引")
    end_idx: int = Field(description="结束索引")
    score: float = Field(description="窗口得分")
    hit_blocks: List[str] = Field(default_factory=list, description="命中的块IDs")
    anchor_block_id: Optional[str] = Field(default=None, description="锚点块ID")


class LlmWindowResult(BaseModel):
    """LLM分析窗口结果（内部使用）"""
    is_template: bool = Field(description="是否是范本")
    kind: Optional[TemplateKind] = Field(default=None, description="范本类型")
    display_title: Optional[str] = Field(default=None, description="显示标题")
    start_block_id: Optional[str] = Field(default=None, description="起始块ID")
    end_block_id: Optional[str] = Field(default=None, description="结束块ID")
    confidence: float = Field(ge=0.0, le=1.0, description="置信度")
    evidence_block_ids: List[str] = Field(default_factory=list, description="证据块IDs")
    reason: str = Field(description="判断原因")


class DocumentBlock(BaseModel):
    """文档块（简化模型，与你们现有的block结构对接）"""
    block_id: str
    order_no: int
    block_type: str  # PARAGRAPH, TABLE_CELL, IMAGE_ANCHOR等
    text: str
    style: Optional[str] = None
    
    class Config:
        # 允许额外字段，方便与现有系统对接
        extra = "allow"


# ==================== API响应 ====================

class TemplateExtractResponse(BaseModel):
    """抽取API响应"""
    success: bool
    message: str
    result: Optional[TemplateExtractResultDTO] = None

