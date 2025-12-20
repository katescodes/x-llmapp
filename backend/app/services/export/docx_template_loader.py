"""
Word 模板加载器
从模板 docx 中提取页面布局原型（SectPr），用于多节文档生成
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict

from docx import Document
from lxml import etree


class PageVariant(str, Enum):
    """页面布局变体"""
    A4_PORTRAIT = "A4_PORTRAIT"      # A4 竖版
    A4_LANDSCAPE = "A4_LANDSCAPE"    # A4 横版
    A3_LANDSCAPE = "A3_LANDSCAPE"    # A3 横版
    DEFAULT = "DEFAULT"              # 默认


@dataclass
class SectPrototype:
    """节原型（包含 sectPr XML 元素）"""
    variant: PageVariant
    sectPr_xml: etree._Element  # lxml Element，可直接插入到段落的 pPr 中
    
    # 页面尺寸信息（twips，仅供参考）
    width_twips: int = 0
    height_twips: int = 0


def _twips_to_mm(twips: int) -> float:
    """将 twips 转换为毫米（1 inch = 1440 twips = 25.4 mm）"""
    return twips * 25.4 / 1440


def _classify_page_variant(width_twips: int, height_twips: int) -> PageVariant:
    """
    根据页面尺寸判断布局变体
    
    常用 twips 尺寸：
    - A4: 11906 x 16838 (210mm x 297mm)
    - A3: 16838 x 23811 (297mm x 420mm)
    """
    def approx(v: int, target: int, tolerance: int = 120) -> bool:
        return abs(v - target) <= tolerance
    
    landscape = width_twips > height_twips
    
    # A4 判断
    is_a4 = (
        (approx(width_twips, 11906) and approx(height_twips, 16838)) or
        (approx(width_twips, 16838) and approx(height_twips, 11906))
    )
    
    # A3 判断
    is_a3 = (
        (approx(width_twips, 16838) and approx(height_twips, 23811)) or
        (approx(width_twips, 23811) and approx(height_twips, 16838))
    )
    
    if is_a4 and not landscape:
        return PageVariant.A4_PORTRAIT
    elif is_a4 and landscape:
        return PageVariant.A4_LANDSCAPE
    elif is_a3 and landscape:
        return PageVariant.A3_LANDSCAPE
    else:
        return PageVariant.DEFAULT


def extract_section_prototypes(template_path: str) -> Dict[PageVariant, SectPrototype]:
    """
    从模板 docx 中提取不同页面布局的 sectPr 原型
    
    这些原型包含：
    - 页面尺寸（pgSz）
    - 页边距（pgMar）
    - 页眉页脚引用（headerReference, footerReference）
    - 列设置（cols）等
    
    Args:
        template_path: 模板文件路径
        
    Returns:
        PageVariant -> SectPrototype 映射
    """
    if not Path(template_path).exists():
        raise FileNotFoundError(f"模板文件不存在: {template_path}")
    
    doc = Document(template_path)
    prototypes: Dict[PageVariant, SectPrototype] = {}
    
    # 遍历所有 section（python-docx 会自动解析多节文档）
    for sect in doc.sections:
        # 获取 sectPr 的 XML
        sectPr_element = sect._sectPr
        
        # 深拷贝 sectPr（避免后续修改影响原文档）
        sectPr_copy = etree.fromstring(etree.tostring(sectPr_element))
        
        # 提取页面尺寸信息
        pgSz = sect.page_width.twips if hasattr(sect, 'page_width') else 11906
        pgSz_h = sect.page_height.twips if hasattr(sect, 'page_height') else 16838
        
        # 更精确的方式：直接从 XML 读取
        try:
            from docx.oxml.ns import qn
            pgSz_elem = sectPr_element.find(qn('w:pgSz'))
            if pgSz_elem is not None:
                w_attr = pgSz_elem.get(qn('w:w'))
                h_attr = pgSz_elem.get(qn('w:h'))
                if w_attr:
                    pgSz = int(w_attr)
                if h_attr:
                    pgSz_h = int(h_attr)
        except Exception:
            pass
        
        # 分类
        variant = _classify_page_variant(pgSz, pgSz_h)
        
        # 只保留第一个匹配的原型（避免重复）
        if variant not in prototypes:
            prototypes[variant] = SectPrototype(
                variant=variant,
                sectPr_xml=sectPr_copy,
                width_twips=pgSz,
                height_twips=pgSz_h,
            )
    
    # 兜底：如果没有找到 DEFAULT，使用文档最后一个 section 的 sectPr
    if PageVariant.DEFAULT not in prototypes and doc.sections:
        last_sect = doc.sections[-1]
        sectPr_copy = etree.fromstring(etree.tostring(last_sect._sectPr))
        prototypes[PageVariant.DEFAULT] = SectPrototype(
            variant=PageVariant.DEFAULT,
            sectPr_xml=sectPr_copy,
            width_twips=11906,
            height_twips=16838,
        )
    
    return prototypes


def load_template_document(template_path: str) -> Document:
    """
    加载模板文档
    
    重要：直接加载模板文档会保留：
    - 页眉页脚（包括图片、域代码如 StyleRef）
    - 样式定义（Heading1~9, Normal 等）
    - 编号定义（如果有）
    - 主题颜色
    
    Args:
        template_path: 模板文件路径
        
    Returns:
        Document 对象
    """
    if not Path(template_path).exists():
        raise FileNotFoundError(f"模板文件不存在: {template_path}")
    
    return Document(template_path)

