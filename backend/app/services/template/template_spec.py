"""
TemplateSpec - 模板规格数据模型
定义 LLM 输出的可执行"模板意图"
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Any
import json


class BasePolicyMode(str, Enum):
    """底板策略模式"""
    KEEP_ALL = "KEEP_ALL"  # 保留整份模板作为基底
    KEEP_RANGE = "KEEP_RANGE"  # 保留指定范围作为基底
    REBUILD = "REBUILD"  # 完全重建（不保留模板内容）


@dataclass
class RangeAnchor:
    """范围锚点（用于 KEEP_RANGE 模式）"""
    start_text: Optional[str] = None
    end_text: Optional[str] = None
    start_block_id: Optional[str] = None
    end_block_id: Optional[str] = None


@dataclass
class BasePolicy:
    """底板策略"""
    mode: BasePolicyMode = BasePolicyMode.KEEP_ALL
    range_anchor: Optional[RangeAnchor] = None
    exclude_block_ids: List[str] = field(default_factory=list)  # 要剔除的块ID（如格式说明）
    description: Optional[str] = None


@dataclass
class StyleHints:
    """样式提示（指导导出时应用样式）"""
    heading1_style: Optional[str] = None  # 一级标题样式名
    heading2_style: Optional[str] = None  # 二级标题样式名
    heading3_style: Optional[str] = None  # 三级标题样式名
    heading4_style: Optional[str] = None
    heading5_style: Optional[str] = None
    body_style: Optional[str] = None  # 正文样式名
    table_style: Optional[str] = None  # 表格样式名
    numbering_candidate: Optional[Dict[str, Any]] = None  # 编号候选（numId, ilvl 映射）
    list_style: Optional[str] = None  # 列表样式名
    
    # 页面样式
    page_background: Optional[str] = None  # 页面底色（CSS 颜色值，如 #ffffff）
    font_family: Optional[str] = None  # 字体（如 SimSun, serif）
    font_size: Optional[str] = None  # 字号（如 14px, 12pt）
    line_height: Optional[str] = None  # 行距（如 1.6, 1.5em）
    
    # 目录缩进
    toc_indent_1: Optional[str] = None  # 一级目录缩进（如 0px）
    toc_indent_2: Optional[str] = None  # 二级目录缩进（如 20px）
    toc_indent_3: Optional[str] = None  # 三级目录缩进（如 40px）
    toc_indent_4: Optional[str] = None  # 四级目录缩进（如 60px）


@dataclass
class StyleRule:
    """
    可执行样式规则（由 LLM 或 deterministic fallback 产出）
    target: "heading1"|"heading2"|"heading3"|"body"
    """
    target: str
    font_family: Optional[str] = None
    font_size_pt: Optional[float] = None
    bold: Optional[bool] = None
    color: Optional[str] = None  # "#RRGGBB"
    line_spacing: Optional[str] = None
    first_line_indent_chars: Optional[int] = None
    alignment: Optional[str] = None  # "left|center|right|justify"
    space_before_pt: Optional[float] = None
    space_after_pt: Optional[float] = None


@dataclass
class OutlineNode:
    """大纲节点（模板定义的结构）"""
    id: str
    title: str
    level: int  # 1=卷, 2=章, 3=节...
    order_no: int  # 同级别中的顺序号
    required: bool = True  # 是否必须
    style_hint: Optional[str] = None  # 建议使用的样式
    parent_id: Optional[str] = None
    children: List[OutlineNode] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MergePolicy:
    """目录合并策略"""
    template_defines_structure: bool = True  # 模板定义主结构
    ai_only_fill_missing: bool = True  # AI 只补充缺失项
    preserve_template_order: bool = True  # 保持模板定义的顺序
    ai_cannot_reorder: bool = True  # AI 不能改变顺序
    allow_ai_add_siblings: bool = False  # 允许 AI 添加同级节点
    description: Optional[str] = None


@dataclass
class Diagnostics:
    """诊断信息"""
    confidence: float = 0.0  # 置信度 0-1
    warnings: List[str] = field(default_factory=list)
    ignored_as_instructions_block_ids: List[str] = field(default_factory=list)  # 被识别为说明的块ID
    analysis_duration_ms: Optional[int] = None
    llm_model: Optional[str] = None


@dataclass
class TemplateSpec:
    """模板规格（LLM 分析输出）"""
    version: str = "v1"
    language: str = "zh-CN"
    base_policy: BasePolicy = field(default_factory=lambda: BasePolicy())
    style_hints: StyleHints = field(default_factory=lambda: StyleHints())
    style_rules: List[StyleRule] = field(default_factory=list)
    outline: List[OutlineNode] = field(default_factory=list)
    merge_policy: MergePolicy = field(default_factory=lambda: MergePolicy())
    diagnostics: Diagnostics = field(default_factory=lambda: Diagnostics())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于 JSON 序列化）"""
        return asdict(self)

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TemplateSpec:
        """从字典构造"""
        # 递归构造嵌套对象
        base_policy_data = data.get("base_policy", {})
        range_anchor = None
        if base_policy_data.get("range_anchor"):
            range_anchor = RangeAnchor(**base_policy_data["range_anchor"])
        
        base_policy = BasePolicy(
            mode=BasePolicyMode(base_policy_data.get("mode", "KEEP_ALL")),
            range_anchor=range_anchor,
            exclude_block_ids=base_policy_data.get("exclude_block_ids", []),
            description=base_policy_data.get("description")
        )
        
        style_hints = StyleHints(**data.get("style_hints", {}))
        merge_policy = MergePolicy(**data.get("merge_policy", {}))
        diagnostics = Diagnostics(**data.get("diagnostics", {}))

        # style_rules（可选，兼容老 spec）
        style_rules: List[StyleRule] = []
        try:
            sr = data.get("style_rules", [])
            if isinstance(sr, list):
                for item in sr:
                    if isinstance(item, dict) and item.get("target"):
                        style_rules.append(StyleRule(**item))
        except Exception:
            style_rules = []
        
        # 构造大纲节点
        outline_data = data.get("outline", [])
        outline = [cls._build_outline_node(node_data) for node_data in outline_data]
        
        return cls(
            version=data.get("version", "v1"),
            language=data.get("language", "zh-CN"),
            base_policy=base_policy,
            style_hints=style_hints,
            style_rules=style_rules,
            outline=outline,
            merge_policy=merge_policy,
            diagnostics=diagnostics,
            metadata=data.get("metadata", {})
        )

    @classmethod
    def _build_outline_node(cls, data: Dict[str, Any]) -> OutlineNode:
        """递归构造大纲节点"""
        children_data = data.get("children", [])
        children = [cls._build_outline_node(child) for child in children_data]
        
        return OutlineNode(
            id=data["id"],
            title=data["title"],
            level=data["level"],
            order_no=data["order_no"],
            required=data.get("required", True),
            style_hint=data.get("style_hint"),
            parent_id=data.get("parent_id"),
            children=children,
            metadata=data.get("metadata", {})
        )

    @classmethod
    def from_json(cls, json_str: str) -> TemplateSpec:
        """从 JSON 字符串构造"""
        data = json.loads(json_str)
        return cls.from_dict(data)


def create_minimal_spec(confidence: float = 0.0, error_msg: Optional[str] = None) -> TemplateSpec:
    """创建最小规格（用于分析失败时的 fallback）"""
    spec = TemplateSpec()
    spec.diagnostics.confidence = confidence
    if error_msg:
        spec.diagnostics.warnings.append(error_msg)
    return spec
