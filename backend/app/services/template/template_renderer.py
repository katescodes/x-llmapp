"""
模板渲染器 - 基于复制模板的方案
实现：copy(template.docx) → 查找anchor → 清理内容 → 插入目录
"""
from __future__ import annotations
import shutil
import logging
from pathlib import Path

from docx import Document
from docx.enum.text import WD_BREAK

from .docx_ooxml import (
    find_anchor,
    prune_after_anchor,
    insert_paragraph_after,
    find_toc_anchor,
    remove_blocks_between,
    iter_block_items,
    paragraph_text,
    remove_block,
    find_marker_paragraph,
)

logger = logging.getLogger(__name__)

PLACEHOLDER_TEXT = "（本章节暂无正文；点击自动填充范本后会显示对应范本内容）"

# 噪音关键词（用于清理模板示例页）
NOISE_KEYWORDS = [
    "横版A4", "横版 A4", "横版A3", "横版 A3",
    "复制页", "带页码", "目录页码", "示例", "样例"
]


def _paragraph_text(p) -> str:
    """获取段落文本（安全版本）"""
    try:
        return (p.text or "").strip()
    except Exception:
        return ""


def _looks_like_legacy_toc_line(txt: str) -> bool:
    """
    判断是否为旧目录行（带点线+页码）
    典型：一、投标函 .......... 2
    """
    import re
    if not txt:
        return False
    if ("…" in txt or "...." in txt) and re.search(r"\d+\s*$", txt):
        return True
    return False


def _paragraph_text(p) -> str:
    """获取段落文本（安全版本）"""
    try:
        return (p.text or "").strip()
    except Exception:
        return ""


def _looks_like_legacy_toc_line(txt: str) -> bool:
    """判断是否为旧目录行（带点线+页码）"""
    import re
    if not txt:
        return False
    # 典型旧目录： "一、投标函 .......... 2"
    if ("…" in txt or "...." in txt) and re.search(r"\d+\s*$", txt):
        return True
    return False


def outline_nodes_to_flat(nodes: list[dict]) -> list[dict]:
    """
    将目录节点转换为扁平列表（如果需要）
    
    Args:
        nodes: 目录节点（可能是扁平列表或树形结构）
        
    Returns:
        扁平列表（按 order_no 排序）
    """
    # MVP: 假设输入已经是扁平列表
    # 如果需要处理树形结构，这里可以添加递归展开逻辑
    return sorted(nodes, key=lambda x: x.get("order_no", 0))


def render_outline_with_template(
    template_docx_path: str,
    out_docx_path: str,
    outline_nodes: list[dict],
    role_mapping: dict,
    prefix_numbering: bool = True,
    use_llm_prune: bool = False,
    apply_assets: dict | None = None,
):
    """
    使用模板渲染目录树
    
    核心流程：
    1. 复制模板 → out.docx
    2. 查找插入锚点
    3. 清理模板示例内容（默认：删除锚点后所有内容）
    4. 插入目录节点（标题+正文）
    
    Args:
        template_docx_path: 模板文件路径
        out_docx_path: 输出文件路径
        outline_nodes: 目录节点列表（扁平化）
        role_mapping: 样式角色映射 {"h1": "+标题1", "body": "++正文", ...}
        prefix_numbering: 是否在标题前添加编号
        use_llm_prune: 是否使用 LLM 的精细化删除（暂未实现）
        apply_assets: LLM 生成的 applyAssets（可选）
    """
    logger.info(f"开始渲染: template={template_docx_path}, output={out_docx_path}")
    logger.info(f"目录节点数: {len(outline_nodes)}, role_mapping={role_mapping}")
    
    # 1. 复制模板作为底板
    shutil.copyfile(template_docx_path, out_docx_path)
    logger.info("✓ 复制模板完成")
    
    # 2. 打开文档
    doc = Document(out_docx_path)
    
    # 2.1. 清理模板噪音（横版A4/A3复制页、示例页等）
    to_delete = []
    deleting = False
    for kind, blk in iter_block_items(doc):
        if kind != "p":
            if deleting:
                to_delete.append(blk)
            continue

        txt = (paragraph_text(blk) or "").strip()

        # 命中关键词，开启删除模式
        if any(k in txt for k in NOISE_KEYWORDS):
            deleting = True
            to_delete.append(blk)
            continue

        # 删除模式下：遇到锚点就停止（避免误删正文区）
        if deleting:
            if txt == "目录" or "[[CONTENT]]" in txt or "[[TOC]]" in txt:
                deleting = False
            else:
                to_delete.append(blk)

    # 执行删除
    for blk in to_delete:
        remove_block(blk)
    
    if len(to_delete) > 0:
        logger.info(f"✓ 清理模板噪音：删除 {len(to_delete)} 个噪音块")

    # 2.2. 删除旧目录的静态行（带点线+页码那种）
    to_delete = []
    seen_dir = False
    for kind, blk in iter_block_items(doc):
        if kind != "p":
            continue
        txt = (paragraph_text(blk) or "").strip()
        if txt == "目录":
            seen_dir = True
            continue
        if seen_dir:
            if _looks_like_legacy_toc_line(txt):
                to_delete.append(blk)
                continue
            # 遇到非目录行就停止
            if txt:
                break
    
    for blk in to_delete:
        remove_block(blk)
    
    if len(to_delete) > 0:
        logger.info(f"✓ 清理旧目录行：删除 {len(to_delete)} 行旧目录")
    
    # 2.5. 强制替换目录（处理 TOC 在 w:sdt 内容控件里的情况）
    # 使用强化版函数：更硬核，必命中
    from .docx_ooxml import replace_all_toc_sdt_with_plain_toc
    
    # 先扁平化目录节点
    flat = outline_nodes_to_flat(outline_nodes)
    
    toc_diag = replace_all_toc_sdt_with_plain_toc(doc, flat, role_mapping)
    logger.warning(f"[APPLY_FMT] toc_diag={toc_diag}")
    
    # 3. 智能锚点选择（优先级：[[CONTENT]] > TOC 末尾 > fallback）
    content_anchor = None
    try:
        content_anchor = find_marker_paragraph(doc, "[[CONTENT]]")
    except Exception:
        content_anchor = None

    anchor = None
    if content_anchor is not None:
        anchor = content_anchor
        logger.info("✓ 使用 [[CONTENT]] 标记作为锚点")
    else:
        # 尝试使用 TOC 末尾作为锚点
        last_line = (toc_diag or {}).get("toc_last_line_text", "")
        if last_line:
            for p in doc.paragraphs:
                if (p.text or "").strip() == last_line:
                    anchor = p
                    logger.info(f"✓ 使用 TOC 末尾作为锚点: {last_line[:50]}")
                    break
    
    if anchor is None:
        anchor = find_anchor(doc)
        logger.info("✓ 使用 fallback 锚点")
    
    # 3.5. 找 TOC 锚点（用于 Fallback 模式）
    toc_anchor = find_toc_anchor(doc)
    logger.info(f"✓ 锚点状态 - TOC: {toc_anchor is not None}, CONTENT: {anchor is not None}")
    
    # 4. 如果两者都存在：先把 TOC 区域清空，然后写入新的 TOC 行（Fallback 模式）
    if toc_anchor is not None and anchor is not None and content_anchor is None:
        # 删除"目录"到"正文插入点"之间的旧目录内容
        remove_blocks_between(doc, toc_anchor, anchor)
        logger.info("✓ 清理旧目录内容完成")
        
        # 写入新的目录行（纯文本目录：不带页码，保证一定替换成功）
        # 可按模板已有 toc 样式：toc 1~toc 5（没有就用 Normal）
        def toc_style(level: int) -> str:
            level = max(1, min(5, level))
            # 支持 roleMapping 里自定义 toc1..toc5（可选）
            s = role_mapping.get(f"toc{level}")
            if s:
                return s
            # 常见模板样式名
            candidates = [f"toc {level}", f"TOC {level}", f"TOC{level}", f"toc {level}".lower()]
            for name in candidates:
                try:
                    _ = doc.styles[name]
                    return name
                except Exception:
                    continue
            return role_mapping.get("body") or "Normal"
        
        cur_toc = toc_anchor
        flat = outline_nodes_to_flat(outline_nodes)
        for n in flat:
            lvl = int(n.get("level") or 1)
            title = (n.get("title") or "").strip()
            if not title:
                continue
            # ✅ TOC 目录行：只用 title，不拼接编号（纯文本目录，无页码）
            cur_toc = insert_paragraph_after(cur_toc, title, style_name=toc_style(lvl))
        
        logger.info(f"✓ 重建目录完成，共 {len(flat)} 个条目")
    
    # 5. 再清理 anchor 后面的模板示例内容（确保正文是"替换"而不是"追加"）
    prune_after_anchor(doc, anchor)
    logger.info("✓ 清理模板示例内容完成")
    
    # 6. 样式选择函数
    def heading_style(level: int) -> str:
        level = max(1, min(5, level))
        key = f"h{level}"
        style = role_mapping.get(key)
        if style:
            return style
        return f"+标题{level}"
    
    body_style = role_mapping.get("body") or "++正文"
    logger.info(f"使用正文样式: {body_style}")
    
    # 7. 插入目录节点（复用锚点作为第一章标题，避免重复）
    import re
    cur = anchor
    flat = outline_nodes_to_flat(outline_nodes)
    
    # 检查是否需要复用锚点段落作为第一章标题
    start_index = 0
    first_node = flat[0] if flat else None
    if first_node is not None:
        first_title = (first_node.get("title") or "").strip()
        # 清理 title 中的编号前缀
        first_title = re.sub(r"^\s*\d+(\.\d+)*\s*", "", first_title).strip()
        first_title = re.sub(r"^\s*[一二三四五六七八九十]+\s*[、.．]\s*", "", first_title).strip()
        
        try:
            style_name = (anchor.style.name or "")
        except Exception:
            style_name = ""
        
        # 若 anchor 本身就是标题样式，直接复用作为第一章标题
        if style_name.lower() in ["+标题1", "heading 1", "heading1", "标题 1", "title"] or style_name.startswith("+标题"):
            anchor.text = first_title
            logger.info(f"✓ 复用锚点段落作为第一章标题: {first_title[:50]}")
            start_index = 1
        else:
            start_index = 0
    else:
        start_index = 0
    
    # 从 start_index 开始插入节点
    for i in range(start_index, len(flat)):
        n = flat[i]
        lvl = int(n.get("level") or 1)
        lvl = max(1, min(5, lvl))
        title = (n.get("title") or "").strip()
        
        # ✅ 构建标题文本：不手工拼接 numbering，完全交给模板 heading 样式的多级编号自动生成
        text = title
        
        # 顶级标题前分页（除了第一个节点）
        if lvl == 1 and i > start_index:
            # 插入分页符
            p = insert_paragraph_after(cur, "")
            try:
                p.runs[0].add_break(WD_BREAK.PAGE)
            except Exception as e:
                logger.warning(f"添加分页符失败: {e}")
            cur = p
        
        # 插入标题
        h_style = heading_style(lvl)
        cur = insert_paragraph_after(cur, text, style_name=h_style)
        logger.debug(f"插入标题: {text[:50]} (style={h_style})")
        
        # 插入正文内容
        # 优先使用 meta_json.summary，否则使用占位符
        meta = n.get("meta_json") or {}
        summary = (meta.get("summary") or "").strip()
        body_text = summary if summary else PLACEHOLDER_TEXT
        
        cur = insert_paragraph_after(cur, body_text, style_name=body_style)
    
    logger.info(f"✓ 插入 {len(flat)} 个目录节点")
    
    # 8. 保存文档
    doc.save(out_docx_path)
    logger.info(f"✓ 渲染完成: {out_docx_path}")
    
    # 8.5. 保存后自检：读取 document.xml 检查是否仍含 TOC 指令
    import zipfile
    try:
        with zipfile.ZipFile(out_docx_path) as zf:
            xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
            still_has_toc = ("<w:instrText" in xml and "TOC" in xml)
        logger.warning(f"[APPLY_FMT] toc_still_present={still_has_toc}")
        if still_has_toc:
            logger.error("⚠️ 警告：保存后 document.xml 中仍存在 TOC 指令！替换可能未生效！")
    except Exception as e:
        logger.warning(f"[APPLY_FMT] toc_selfcheck_failed: {e}")


def render_outline_with_template_v2(
    template_path: str,
    output_path: str,
    outline_tree: list[dict],
    analysis_json: dict,
    prefix_numbering: bool = True,
):
    """
    渲染接口 V2（兼容旧的调用方式）
    
    Args:
        template_path: 模板文件路径
        output_path: 输出文件路径
        outline_tree: 目录树（扁平列表）
        analysis_json: 模板分析结果 {"roleMapping": ..., "applyAssets": ...}
        prefix_numbering: 是否在标题前添加编号
    """
    role_mapping = analysis_json.get("roleMapping", {})
    apply_assets = analysis_json.get("applyAssets")
    
    render_outline_with_template(
        template_docx_path=template_path,
        out_docx_path=output_path,
        outline_nodes=outline_tree,
        role_mapping=role_mapping,
        prefix_numbering=prefix_numbering,
        use_llm_prune=False,
        apply_assets=apply_assets,
    )
