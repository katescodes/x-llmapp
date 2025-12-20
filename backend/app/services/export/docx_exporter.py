"""
Word 文档导出器
使用模板母版生成包含目录树的 Word 文档
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

from .tree_builder import DirNode
from .docx_template_loader import PageVariant, SectPrototype

logger = logging.getLogger(__name__)


def _get_heading_style_name(
    level: int,
    heading_style_map: Optional[Dict[int, str]] = None
) -> str:
    """
    获取指定层级的标题样式名称
    
    优先使用 heading_style_map 中的样式，如果没有则回退到默认的 Heading {level}
    
    Args:
        level: 层级（1~9）
        heading_style_map: 标题样式映射（level -> style_name），来自模板配置
        
    Returns:
        样式名称
    """
    lv = max(1, min(level, 9))
    
    # 优先使用自定义样式映射
    if heading_style_map and lv in heading_style_map:
        return heading_style_map[lv]
    
    # 回退到默认 Heading 1~9
    return f"Heading {lv}"


def _clear_body_keep_sectpr(doc: Document) -> None:
    """
    清空文档正文内容，但保留最后的 sectPr
    
    这样可以保留文档的最后一节的页面设置和页眉页脚
    
    Args:
        doc: Document 对象（会原地修改）
    """
    body = doc._element.body
    
    # 保存最后的 sectPr
    last_sectpr = None
    for child in list(body):
        if child.tag == qn("w:sectPr"):
            last_sectpr = etree.fromstring(etree.tostring(child))
    
    # 清空所有内容
    for child in list(body):
        body.remove(child)
    
    # 恢复 sectPr
    if last_sectpr is not None:
        body.append(last_sectpr)


def _add_toc_field(doc: Document, levels: str = "1-5") -> None:
    """
    添加目录域（TOC field）
    
    注意：LibreOffice 可能不会自动更新目录，需要在 Word 中打开按 F9 更新
    
    Args:
        doc: Document 对象
        levels: 目录层级范围（如 "1-5"）
    """
    p = doc.add_paragraph()
    
    # 创建 fldSimple 元素
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), f'TOC \\o "{levels}" \\h \\z \\u')
    
    # 添加占位文本
    r = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = "[目录将在 Word 中更新]"
    r.append(t)
    fld.append(r)
    
    p._p.append(fld)


def _add_section_break(doc: Document, sectpr_xml: etree._Element) -> None:
    """
    添加分节符（section break）
    
    Args:
        doc: Document 对象
        sectpr_xml: sectPr XML 元素
    """
    # 添加一个空段落，并在其 pPr 中插入 sectPr
    p = doc.add_paragraph("")
    ppr = p._p.get_or_add_pPr()
    
    # 深拷贝 sectPr（避免多次引用同一个对象）
    sectpr_copy = etree.fromstring(etree.tostring(sectpr_xml))
    ppr.append(sectpr_copy)


def _maybe_prefix_numbering(text: str, numbering: Optional[str], enabled: bool) -> str:
    """
    如果启用了编号前缀，将编号添加到标题前面
    
    Args:
        text: 原始标题文本
        numbering: 编号（如 "1.2.3"）
        enabled: 是否启用
        
    Returns:
        处理后的标题文本
    """
    if not enabled or not numbering:
        return text
    
    # 避免重复：如果 text 本来就以编号开头，则不再添加
    import re
    if re.match(r"^\s*\d+(\.\d+)*\s+", text):
        return text
    
    return f"{numbering} {text}"


def render_directory_tree_to_docx(
    template_path: str,
    output_path: str,
    roots: List[DirNode],
    section_prototypes: Dict[PageVariant, SectPrototype],
    *,
    include_toc: bool = True,
    prefix_numbering_in_text: bool = False,
    heading_style_map: Optional[Dict[int, str]] = None,
    normal_style_name: Optional[str] = None,
    insert_section_body: Optional[callable] = None,
) -> None:
    """
    将目录树渲染为 Word 文档（使用模板母版）
    
    Args:
        template_path: 模板文件路径
        output_path: 输出文件路径
        roots: 根节点列表
        section_prototypes: 页面布局原型映射
        include_toc: 是否包含目录
        prefix_numbering_in_text: 是否在标题前添加编号
        heading_style_map: 标题样式映射（level -> style_name），来自模板配置
        normal_style_name: 正文样式名称，用于 summary 段落
        insert_section_body: 插入节正文的回调函数（node: DirNode, doc: Document）
    """
    logger.info(f"开始渲染文档: template={template_path}, output={output_path}")
    
    # 1. 加载模板（保留页眉页脚）
    doc = Document(template_path)
    
    # 2. 清空正文内容（保留最后的 sectPr）
    _clear_body_keep_sectpr(doc)
    
    # 3. 添加目录页（可选）
    if include_toc:
        toc_title = doc.add_paragraph("目录", style=_get_heading_style_name(1, heading_style_map))
        toc_title.alignment = 1  # 居中
        _add_toc_field(doc, "1-5")
        doc.add_page_break()
    
    # 4. DFS 遍历目录树，写入内容
    def emit_node(node: DirNode, depth: int = 0):
        """递归输出节点"""
        # 4.1 检查是否需要插入分节符（横版/特殊布局）
        page_variant = node.meta_json.get("page_variant")
        if page_variant and page_variant in section_prototypes:
            logger.debug(f"插入分节符: {page_variant} for node {node.title}")
            _add_section_break(doc, section_prototypes[page_variant].sectPr_xml)
        
        # 4.2 添加标题
        title_text = _maybe_prefix_numbering(node.title, node.numbering, prefix_numbering_in_text)
        style_name = _get_heading_style_name(node.level, heading_style_map)
        
        try:
            para = doc.add_paragraph(title_text, style=style_name)
        except Exception as e:
            # 样式不存在时回退到默认 Heading
            logger.warning(f"样式 {style_name} 不存在，使用默认 Heading: {e}")
            h_level = min(max(node.level, 1), 9)
            para = doc.add_heading(title_text, level=h_level)
        
        # 4.3 添加 summary（占位正文）
        if node.summary:
            # 优先使用 normal_style_name，如果未指定则使用默认段落
            if normal_style_name:
                try:
                    doc.add_paragraph(node.summary, style=normal_style_name)
                except Exception as e:
                    logger.warning(f"样式 {normal_style_name} 不存在，使用默认段落: {e}")
                    doc.add_paragraph(node.summary)
            else:
                doc.add_paragraph(node.summary)
        
        # 4.4 插入节正文内容（如果提供了回调）
        if insert_section_body:
            try:
                insert_section_body(node, doc)
            except Exception as e:
                logger.error(f"插入节正文失败: node={node.id}, error={e}", exc_info=True)
                doc.add_paragraph(f"[正文内容加载失败: {str(e)}]")
        
        # 4.5 递归处理子节点
        for child in node.children:
            emit_node(child, depth + 1)
    
    # 遍历所有根节点
    for root in roots:
        emit_node(root)
    
    # 5. 最后切回默认布局（通常是 A4 竖版）
    back_variant = PageVariant.A4_PORTRAIT if PageVariant.A4_PORTRAIT in section_prototypes else PageVariant.DEFAULT
    if back_variant in section_prototypes:
        _add_section_break(doc, section_prototypes[back_variant].sectPr_xml)
    
    # 6. 保存文档
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    doc.save(output_path)
    logger.info(f"文档渲染完成: {output_path}")


def render_simple_outline_to_docx(
    output_path: str,
    roots: List[DirNode],
    *,
    include_toc: bool = True,
    prefix_numbering_in_text: bool = False,
) -> None:
    """
    渲染简单的目录文档（不使用模板）
    
    Args:
        output_path: 输出文件路径
        roots: 根节点列表
        include_toc: 是否包含目录
        prefix_numbering_in_text: 是否在标题前添加编号
    """
    logger.info(f"开始渲染简单文档: output={output_path}")
    
    # 1. 创建新文档
    doc = Document()
    
    # 2. 添加目录页（可选）
    if include_toc:
        doc.add_heading("目录", level=1)
        _add_toc_field(doc, "1-5")
        doc.add_page_break()
    
    # 3. DFS 遍历目录树
    def emit_node(node: DirNode):
        title_text = _maybe_prefix_numbering(node.title, node.numbering, prefix_numbering_in_text)
        h_level = min(max(node.level, 1), 9)
        doc.add_heading(title_text, level=h_level)
        
        if node.summary:
            doc.add_paragraph(node.summary)
        
        for child in node.children:
            emit_node(child)
    
    for root in roots:
        emit_node(root)
    
    # 4. 保存
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    doc.save(output_path)
    logger.info(f"简单文档渲染完成: {output_path}")

