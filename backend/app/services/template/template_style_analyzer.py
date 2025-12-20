"""
模板样式分析器
提取样式配置并推断角色映射（优先 +标题1~5 / ++正文）
"""
from __future__ import annotations
import zipfile
import re
import logging
from lxml import etree

logger = logging.getLogger(__name__)

W_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def extract_style_profile(docx_path: str) -> dict:
    """
    提取 DOCX 样式配置
    
    包括：
    - 样式列表（ID、名称、类型、basedOn、outlineLevel）
    - 计算有效 outlineLevel（沿 basedOn 链继承）
    - 编号配置信息
    
    Args:
        docx_path: DOCX 文件路径
        
    Returns:
        样式配置字典
    """
    with zipfile.ZipFile(docx_path) as z:
        styles_xml = z.read("word/styles.xml")
        has_numbering = "word/numbering.xml" in z.namelist()
    
    root = etree.fromstring(styles_xml)
    styles = []
    by_id = {}
    
    # 解析所有样式
    for style in root.xpath("//w:style", namespaces=W_NS):
        style_id = style.get("{%s}styleId" % W_NS["w"])
        style_type = style.get("{%s}type" % W_NS["w"])
        
        name_el = style.find("w:name", namespaces=W_NS)
        name = name_el.get("{%s}val" % W_NS["w"]) if name_el is not None else None
        
        based_on_el = style.find("w:basedOn", namespaces=W_NS)
        based_on = based_on_el.get("{%s}val" % W_NS["w"]) if based_on_el is not None else None
        
        outline_el = style.find(".//w:outlineLvl", namespaces=W_NS)
        outline = outline_el.get("{%s}val" % W_NS["w"]) if outline_el is not None else None
        outline_lvl = int(outline) if outline is not None else None
        
        item = {
            "styleId": style_id,
            "name": name,
            "type": style_type,
            "basedOn": based_on,
            "outlineLevel": outline_lvl,
        }
        styles.append(item)
        if style_id:
            by_id[style_id] = item
    
    # 计算 effectiveOutlineLevel（沿 basedOn 链继承）
    def eff_outline(sid: str) -> int | None:
        seen = set()
        cur = sid
        while cur and cur not in seen:
            seen.add(cur)
            s = by_id.get(cur)
            if not s:
                return None
            if s.get("outlineLevel") is not None:
                lvl = s["outlineLevel"]
                return lvl if 0 <= lvl <= 8 else None
            cur = s.get("basedOn")
        return None
    
    for s in styles:
        if s["type"] == "paragraph" and s.get("styleId"):
            s["effectiveOutlineLevel"] = eff_outline(s["styleId"])
        else:
            s["effectiveOutlineLevel"] = None
    
    logger.info(f"提取样式配置: {len(styles)} 个样式, hasNumbering={has_numbering}")
    
    return {
        "styles": styles,
        "hasNumbering": has_numbering
    }


def infer_role_mapping(profile: dict) -> dict:
    """
    推断样式角色映射
    
    优先级：
    1. +标题1~9 → h1~h9
    2. effectiveOutlineLevel → h1~h9
    3. ++正文 / Normal → body
    4. Table Grid / Normal Table → table
    
    Args:
        profile: 样式配置（from extract_style_profile）
        
    Returns:
        角色映射 {"h1": "+标题1", "h2": "+标题2", "body": "++正文", ...}
    """
    styles = profile["styles"]
    ps = [s for s in styles if s["type"] == "paragraph" and s.get("name")]
    ts = [s for s in styles if s["type"] == "table" and s.get("name")]
    
    rm = {}
    
    # 1) 优先 +标题X（中文）
    for s in ps:
        m = re.match(r"^\+标题([1-9])$", s["name"].strip())
        if m:
            idx = int(m.group(1))
            rm[f"h{idx}"] = s["name"]
            logger.debug(f"找到自定义标题样式: h{idx} = {s['name']}")
    
    # 2) 再用 effectiveOutlineLevel 补齐（fallback）
    for s in ps:
        lvl = s.get("effectiveOutlineLevel")
        if lvl is None:
            continue
        key = f"h{lvl + 1}"
        if key not in rm:  # 不覆盖已有的 +标题X
            rm[key] = s["name"]
            logger.debug(f"通过 outlineLevel 映射: {key} = {s['name']} (outlineLevel={lvl})")
    
    # 3) body 优先 ++正文
    names = {s["name"] for s in ps}
    if "++正文" in names:
        rm["body"] = "++正文"
        logger.info("使用自定义正文样式: ++正文")
    elif "正文" in names:
        rm["body"] = "正文"
        logger.info("使用正文样式: 正文")
    elif "Normal" in names:
        rm["body"] = "Normal"
        logger.info("使用默认正文样式: Normal")
    
    # 4) table 优先 Table Grid
    tnames = {s["name"] for s in ts}
    if "Table Grid" in tnames:
        rm["table"] = "Table Grid"
    elif "Normal Table" in tnames:
        rm["table"] = "Normal Table"
    
    logger.info(f"推断角色映射: {rm}")
    
    return rm


def get_fallback_role_mapping() -> dict:
    """
    获取默认的角色映射（当模板分析失败时使用）
    
    Returns:
        默认映射
    """
    return {
        "h1": "+标题1",
        "h2": "+标题2",
        "h3": "+标题3",
        "h4": "+标题4",
        "h5": "+标题5",
        "body": "++正文",
        "table": "Table Grid"
    }
