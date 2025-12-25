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
    
    # 硬校验：目录节点不能为空
    if not outline_nodes:
        error_msg = "目录节点为空，无法生成文档"
        logger.error(f"[RENDER_FAIL] {error_msg}")
        raise ValueError(error_msg)
    
    # 校验：role_mapping 缺失则使用默认值
    if not role_mapping:
        logger.warning("[RENDER_WARN] role_mapping 为空，使用默认样式映射")
        role_mapping = {
            "h1": "+标题1",
            "h2": "+标题2",
            "h3": "+标题3",
            "h4": "+标题4",
            "h5": "+标题5",
            "body": "++正文"
        }
    
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
    
    # A) 目录节点过滤：避免把"目录/目 录/TOC"当成正文章节插入
    flat_filtered = []
    for n in flat:
        title = (n.get("title") or "").strip()
        # 去除空白后，完全匹配"目录"相关关键词（大小写不敏感）
        title_normalized = title.replace(" ", "").replace("\u3000", "").lower()
        if title_normalized in ["目录", "目录结构", "toc", "投标文件目录"]:
            logger.info(f"✓ 过滤目录节点: {title}")
            continue
        flat_filtered.append(n)
    
    logger.info(f"✓ 目录节点过滤: {len(flat)} -> {len(flat_filtered)} (过滤了 {len(flat) - len(flat_filtered)} 个)")
    flat = flat_filtered
    
    # 硬校验：过滤后目录节点不能为空
    if not flat:
        error_msg = "过滤后目录节点为空（可能所有节点都是'目录'类节点），无法生成文档"
        logger.error(f"[RENDER_FAIL] {error_msg}")
        raise ValueError(error_msg)
    
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
    
    # B) 修正"目录标题"段落样式（避免出现"一、目录"）
    if toc_anchor is not None:
        try:
            current_style = toc_anchor.style.name
            logger.info(f"目录标题当前样式: {current_style}")
            
            # 如果是带编号的标题样式，改为不带编号的样式
            heading_styles = ["heading 1", "heading1", "+标题1", "标题 1", "标题1", "title"]
            if current_style.lower() in heading_styles or current_style.startswith("+标题"):
                # 优先使用 role_mapping.get("toc_title")
                new_style = role_mapping.get("toc_title")
                if not new_style:
                    # 尝试常见的无编号样式
                    for candidate in ["TOC Heading", "目录标题", "目录", "Normal"]:
                        try:
                            _ = doc.styles[candidate]
                            new_style = candidate
                            break
                        except Exception:
                            continue
                
                if new_style:
                    toc_anchor.style = new_style
                    logger.info(f"✓ 修正目录标题样式: {current_style} -> {new_style}")
        except Exception as e:
            logger.warning(f"修正目录标题样式失败: {e}")
    
    # C) TOC 列表必定生成（兜底保证）
    # 检查 toc_diag 是否显示 TOC 写入行数为 0，如果是则强制走 fallback
    toc_written_lines = (toc_diag or {}).get("toc_written_lines", 0)
    force_fallback = (toc_written_lines == 0)
    
    if force_fallback:
        logger.warning("⚠️ TOC 写入行数为 0，强制走 Fallback 模式")
    
    # 4. 如果两者都存在：先把 TOC 区域清空，然后写入新的 TOC 行（Fallback 模式）
    if toc_anchor is not None and anchor is not None and (content_anchor is None or force_fallback):
        # 删除"目录"到"正文插入点"之间的旧目录内容
        if content_anchor is None:
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
        toc_lines_written = 0
        for n in flat:
            lvl = int(n.get("level") or 1)
            title = (n.get("title") or "").strip()
            if not title:
                continue
            
            # ✅ 清理 title 中自带的编号前缀（目录中只显示标题名称）
            import re
            title_clean = re.sub(r"^\s*\d+(\.\d+)*\s*", "", title).strip()
            title_clean = re.sub(r"^\s*[一二三四五六七八九十]+\s*[、.．]\s*", "", title_clean).strip()
            
            # ✅ TOC 目录行：只用纯标题，不拼接编号（纯文本目录，无页码）
            cur_toc = insert_paragraph_after(cur_toc, title_clean, style_name=toc_style(lvl))
            toc_lines_written += 1
        
        logger.info(f"✓ 重建目录完成，共 {toc_lines_written} 个条目")
        
        # D) 锚点选择更稳：把 anchor 设为 TOC 列表最后一行，避免误删 TOC
        if content_anchor is None and toc_lines_written > 0:
            anchor = cur_toc
            logger.info(f"✓ 更新锚点为 TOC 末尾，避免误删目录")
    
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
    渲染接口 V2（兼容适配器函数）
    
    Args:
        template_path: 模板文件路径
        output_path: 输出文件路径
        outline_tree: 目录树（可能是 DAO rows 或扁平列表）
        analysis_json: 模板分析结果 {"roleMapping"/"role_mapping": ..., "applyAssets"/"apply_assets": ...}
        prefix_numbering: 是否在标题前添加编号
    """
    # a) 兼容读取 roleMapping / role_mapping（两种 key 都支持）
    role_mapping = analysis_json.get("roleMapping") or analysis_json.get("role_mapping") or {}
    if not role_mapping:
        logger.warning("[V2] roleMapping 为空，将使用默认样式映射")
        role_mapping = {
            "h1": "+标题1",
            "h2": "+标题2",
            "h3": "+标题3",
            "h4": "+标题4",
            "h5": "+标题5",
            "body": "++正文"
        }
    
    # b) 兼容读取 applyAssets / apply_assets
    apply_assets = analysis_json.get("applyAssets") or analysis_json.get("apply_assets")
    
    # c) 将 outline_tree 规范化成 renderer 需要的 outline_nodes
    outline_nodes = []
    if outline_tree:
        # 检查是否为 DAO rows（含 level/title/meta_json/parent_id/order_no）
        if isinstance(outline_tree, list) and len(outline_tree) > 0:
            first = outline_tree[0]
            # 如果是 dict 并且包含目录节点的典型字段，直接使用
            if isinstance(first, dict) and ("level" in first or "title" in first):
                outline_nodes = outline_tree
            else:
                logger.warning(f"[V2] outline_tree 格式不符合预期: {type(first)}")
                outline_nodes = outline_tree
        else:
            logger.warning(f"[V2] outline_tree 类型不符合预期: {type(outline_tree)}")
            outline_nodes = outline_tree if isinstance(outline_tree, list) else []
    
    # d) 确保最终 outline_nodes_to_flat(outline_nodes) 非空；若为空，抛出 ValueError
    try:
        flat = outline_nodes_to_flat(outline_nodes)
    except Exception as e:
        logger.error(f"[V2] 扁平化目录节点失败: {e}")
        raise ValueError(f"目录节点扁平化失败: {e}")
    
    if not flat:
        logger.error(f"[V2] outline_nodes 为空或扁平化后为空，无法渲染")
        raise ValueError("outline_nodes empty after normalize - 目录节点为空，无法生成文档")
    
    logger.info(f"[V2] 目录节点校验通过: {len(flat)} 个节点")
    
    # 最终调用现有的 render_outline_with_template
    render_outline_with_template(
        template_docx_path=template_path,
        out_docx_path=output_path,
        outline_nodes=outline_nodes,
        role_mapping=role_mapping,
        prefix_numbering=prefix_numbering,
        use_llm_prune=False,
        apply_assets=apply_assets,
    )
