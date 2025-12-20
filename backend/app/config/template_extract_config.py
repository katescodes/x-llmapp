"""
投标文件格式抽取 - 配置
默认配置：关键词、阈值、终止规则、覆盖率guard
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class TemplateExtractConfig(BaseModel):
    """模板抽取配置"""
    
    # ==================== 关键词配置 ====================
    
    strong_keywords: List[str] = Field(
        default=[
            "投标文件格式", "格式范本", "投标函", "授权委托书",
            "法定代表人授权", "报价表", "报价文件", "偏离表",
            "技术偏离表", "商务偏离表", "承诺书", "响应承诺",
            "业绩表", "人员表", "社保", "资格审查",
            "证书", "附表", "样表", "投标文件组成",
        ],
        description="强关键词列表（命中加0.2分，最多+0.6）"
    )
    
    weak_keywords: List[str] = Field(
        default=[
            "模板", "表格", "格式", "盖章", "签字",
            "日期", "联系人", "投标人", "被授权人", "授权人",
            "权限", "填写", "按以下格式", "提供以下资料",
        ],
        description="弱关键词列表（命中最多+0.2）"
    )
    
    signature_keywords: List[str] = Field(
        default=[
            "（盖章处）", "签字", "法定代表人", "授权人",
            "被授权人", "日期：", "联系人：", "投标人：",
            "单位公章", "签章", "盖章",
        ],
        description="签章/占位特征（命中加0.15）"
    )
    
    template_marker_keywords: List[str] = Field(
        default=[
            "附表", "表", "格式", "样表", "模板",
            "范本", "请按以下格式", "按下列格式",
        ],
        description="模板标记词（组合命中额外+0.2）"
    )
    
    chapter_switch_patterns: List[str] = Field(
        default=[
            r"第[一二三四五六七八九十\d]+章",
            r"第[一二三四五六七八九十\d]+节",
            "评分标准", "评分办法", "技术要求",
            "商务条款", "资格审查", "投标人须知",
            "技术规格", "商务要求",
        ],
        description="章节切换信号（用于终止规则）"
    )
    
    # ==================== 召回配置 ====================
    
    window_radius: int = Field(
        default=30,
        description="窗口半径（锚点前后各N个块）"
    )
    
    max_windows: int = Field(
        default=20,
        description="最大窗口数"
    )
    
    min_evidence_score: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
        description="最小证据得分（成为锚点的阈值）"
    )
    
    top_evidences_count: int = Field(
        default=50,
        description="返回的top证据数量（用于UI展示）"
    )
    
    # ==================== LLM配置 ====================
    
    llm_min_confidence: float = Field(
        default=0.60,
        ge=0.0,
        le=1.0,
        description="LLM最小置信度（低于此值丢弃）"
    )
    
    llm_max_concurrent: int = Field(
        default=3,
        description="LLM最大并发数"
    )
    
    # ==================== 边界细化配置 ====================
    
    max_span_blocks: int = Field(
        default=260,
        description="单个span最大块数"
    )
    
    max_span_chars: int = Field(
        default=22000,
        description="单个span最大字符数"
    )
    
    refine_lookback_blocks: int = Field(
        default=8,
        description="开始边界回看块数"
    )
    
    refine_tail_trim_blocks: int = Field(
        default=6,
        description="尾部去噪连续空块数"
    )
    
    next_anchor_min_distance: int = Field(
        default=8,
        description="下一个锚点最小距离（用于终止）"
    )
    
    # ==================== 覆盖率guard配置 ====================
    
    coverage_expected_kinds: List[str] = Field(
        default=[
            "BID_LETTER",
            "LEGAL_AUTHORIZATION",
            "PRICE_SCHEDULE",
            "DEVIATION_TABLE",
            "COMMITMENT_LETTER",
        ],
        description="期望覆盖的范本类型"
    )
    
    coverage_min_ratio: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="最小覆盖率"
    )
    
    low_text_density_threshold: float = Field(
        default=0.03,
        description="低文本密度阈值（判断NEED_OCR）"
    )
    
    image_anchor_hit_to_need_ocr: bool = Field(
        default=True,
        description="图片锚点多时判定为NEED_OCR"
    )
    
    # ==================== 增强模式配置 ====================
    
    enhanced_window_radius: int = Field(
        default=45,
        description="增强模式窗口半径"
    )
    
    enhanced_min_evidence_score: float = Field(
        default=0.55,
        ge=0.0,
        le=1.0,
        description="增强模式最小证据得分"
    )
    
    enhanced_max_windows: int = Field(
        default=30,
        description="增强模式最大窗口数"
    )


# 全局配置实例
_template_extract_config: TemplateExtractConfig | None = None


def get_template_extract_config() -> TemplateExtractConfig:
    """获取模板抽取配置（单例）"""
    global _template_extract_config
    if _template_extract_config is None:
        _template_extract_config = TemplateExtractConfig()
    return _template_extract_config


def set_template_extract_config(config: TemplateExtractConfig) -> None:
    """设置模板抽取配置（用于测试或自定义）"""
    global _template_extract_config
    _template_extract_config = config

