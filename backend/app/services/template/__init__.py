"""
模板分析服务包
包含模板结构化解析、LLM 理解、规格校验等功能
"""

from .docx_extractor import DocxBlock, DocxExtractResult, DocxBlockExtractor, BlockType
from .template_spec import (
    TemplateSpec,
    BasePolicy,
    BasePolicyMode,
    StyleHints,
    OutlineNode,
    MergePolicy,
    Diagnostics,
    RangeAnchor,
    create_minimal_spec,
)
from .spec_validator import TemplateSpecValidator, SchemaValidationException, get_validator
from .llm_analyzer import TemplateLlmAnalyzer, TemplateAnalysisCache, get_analysis_cache

__all__ = [
    "BlockType",
    "DocxBlock",
    "DocxExtractResult",
    "DocxBlockExtractor",
    "TemplateSpec",
    "BasePolicy",
    "BasePolicyMode",
    "StyleHints",
    "OutlineNode",
    "MergePolicy",
    "Diagnostics",
    "RangeAnchor",
    "create_minimal_spec",
    "TemplateSpecValidator",
    "SchemaValidationException",
    "get_validator",
    "TemplateLlmAnalyzer",
    "TemplateAnalysisCache",
    "get_analysis_cache",
]
