"""
格式模板 Work 返回类型定义
轻量级的 Pydantic/TypedDict 结构
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


# ==================== 基础类型 ====================

class FormatTemplateOut(BaseModel):
    """格式模板输出结构"""
    id: str
    name: str
    description: Optional[str] = None
    is_public: bool = False
    owner_id: str
    template_storage_path: Optional[str] = None  # 允许为空（兼容旧数据）
    file_sha256: Optional[str] = None
    analysis_json: Optional[Dict[str, Any]] = None
    template_spec_analyzed_at: Optional[str] = None
    created_at: str
    updated_at: str


class FormatTemplateCreateResult(BaseModel):
    """创建格式模板的返回结果"""
    template_id: str
    name: str
    description: Optional[str] = None
    storage_path: str
    analysis_status: str  # "pending" | "completed" | "failed"
    analysis_summary: Optional[Dict[str, Any]] = None


class FormatTemplateSpecOut(BaseModel):
    """格式模板样式规格输出"""
    style_hints: Dict[str, Dict[str, Any]]  # styleName -> style properties
    role_mapping: Optional[Dict[str, str]] = None  # h1, h2, body, etc.
    meta: Optional[Dict[str, Any]] = None


class FormatTemplateAnalysisSummary(BaseModel):
    """格式模板分析摘要"""
    template_id: str
    template_name: str
    confidence: float
    warnings: List[str] = []
    anchors_count: int = 0
    has_content_marker: bool = False
    keep_blocks_count: int = 0
    delete_blocks_count: int = 0
    heading_styles: Dict[str, Any] = {}
    body_style: Optional[str] = None
    blocks_summary: Dict[str, int] = {}


class FormatTemplateParseSummary(BaseModel):
    """格式模板解析摘要"""
    template_id: str
    sections: List[Dict[str, Any]] = []
    variants: List[Dict[str, Any]] = []
    heading_levels: List[Dict[str, Any]] = []
    header_images: List[str] = []
    footer_images: List[str] = []


# ==================== 套用格式结果 ====================

class ApplyFormatTemplateResult(BaseModel):
    """套用格式模板到项目目录的结果"""
    ok: bool
    detail: Optional[str] = None
    nodes: Optional[List[Dict[str, Any]]] = None
    preview_pdf_url: Optional[str] = None
    download_docx_url: Optional[str] = None
    docx_path: Optional[str] = None  # 内部使用，实际文件路径
    pdf_path: Optional[str] = None   # 内部使用，实际文件路径


# ==================== 更新请求 ====================

class FormatTemplateUpdateReq(BaseModel):
    """更新格式模板元数据请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None


# ==================== 预览请求 ====================

class PreviewFormat:
    """预览格式枚举"""
    PDF = "pdf"
    DOCX = "docx"


class PreviewResult(BaseModel):
    """预览结果"""
    ok: bool = True
    error: Optional[str] = None
    docx_path: Optional[str] = None
    pdf_path: Optional[str] = None
    file_path: Optional[str] = None  # 兼容字段
    content_type: Optional[str] = None  # 兼容字段
    file_bytes: Optional[bytes] = None


class ProjectPreviewResult(BaseModel):
    """项目格式预览结果"""
    ok: bool = True
    error: Optional[str] = None
    docx_path: Optional[str] = None
    pdf_path: Optional[str] = None

