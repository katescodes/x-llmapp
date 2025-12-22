"""
Word 文档导出器
使用模板母版生成包含目录树的 Word 文档
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

from .tree_builder import DirNode
from .docx_template_loader import PageVariant, SectPrototype

logger = logging.getLogger(__name__)


# ============================================================================
# 自动生成申报书内容的辅助函数
# ============================================================================

@dataclass
class AutoWriteCfg:
    """自动写作配置：字数越多越好，按标题层级给更高下限"""
    min_words_h1: int = 1200
    min_words_h2: int = 800
    min_words_h3: int = 500
    min_words_h4: int = 300
    max_tokens: int = 1600  # 单次调用上限（避免超时）
    multi_round: bool = True  # 是否分多次生成（字数越多越好的工程化做法）


def _is_empty_or_placeholder(content: Optional[str]) -> bool:
    """
    判断内容是否为空或占位符
    
    Args:
        content: 内容字符串
        
    Returns:
        True 如果为空或占位符
    """
    if not content:
        return True
    
    content = content.strip()
    
    # 检查是否为常见占位符
    placeholders = [
        "【填写】",
        "【待补】",
        "【待填写】",
        "[填写]",
        "[待补]",
        "待填写",
        "待补充",
        "TODO",
        "TBD",
    ]
    
    return content in placeholders or len(content) < 5


def build_project_context_string(project_data: Optional[Dict] = None) -> str:
    """
    构建项目上下文字符串（用于 LLM 生成时提供背景信息）
    
    从项目数据中提取关键信息，拼接成上下文字符串。
    
    Args:
        project_data: 项目数据字典，可能包含：
            - name: 项目名称
            - company: 企业名称
            - summary: 项目摘要
            - patents: 专利清单
            - devices: 设备清单
            - achievements: 成果清单
            - meta_json: 其他元数据
            
    Returns:
        上下文字符串
    """
    if not project_data:
        return ""
    
    lines = []
    
    # 1. 项目名称
    if project_data.get("name"):
        lines.append(f"【项目名称】{project_data['name']}")
    
    # 2. 企业信息
    if project_data.get("company"):
        lines.append(f"【企业名称】{project_data['company']}")
    
    # 3. 项目摘要
    if project_data.get("summary"):
        lines.append(f"【项目摘要】{project_data['summary']}")
    
    # 4. 从 meta_json 中提取信息
    meta = project_data.get("meta_json", {})
    
    if meta.get("industry"):
        lines.append(f"【所属行业】{meta['industry']}")
    
    if meta.get("budget"):
        lines.append(f"【预算金额】{meta['budget']}")
    
    if meta.get("duration"):
        lines.append(f"【建设周期】{meta['duration']}")
    
    # 5. 专利清单（如果有）
    patents = project_data.get("patents", [])
    if patents:
        lines.append(f"【专利数量】{len(patents)} 项")
        # 只列举前 3 个专利名称
        for i, patent in enumerate(patents[:3], 1):
            if isinstance(patent, dict) and patent.get("name"):
                lines.append(f"  {i}. {patent['name']}")
    
    # 6. 设备清单（如果有）
    devices = project_data.get("devices", [])
    if devices:
        lines.append(f"【主要设备】{len(devices)} 项")
    
    # 7. 成果清单（如果有）
    achievements = project_data.get("achievements", [])
    if achievements:
        lines.append(f"【已有成果】{len(achievements)} 项")
    
    # 如果没有任何信息，返回提示
    if not lines:
        return "（暂无项目上下文信息）"
    
    return "\n".join(lines)


def _target_min_words(level: int, cfg: AutoWriteCfg) -> int:
    """根据标题层级返回目标最小字数"""
    if level <= 1:
        return cfg.min_words_h1
    if level == 2:
        return cfg.min_words_h2
    if level == 3:
        return cfg.min_words_h3
    return cfg.min_words_h4


def _infer_section_style(title: str) -> str:
    """根据标题关键词给写作侧重点，提升'像申报书'的命中率。"""
    t = title.strip()
    rules = [
        (r"概况|背景|意义|必要性|总体情况", "写背景现状、政策依据、问题痛点、建设必要性与总体目标。"),
        (r"目标|指标|成效|效益|预期", "写可量化目标指标（效率/质量/成本/能耗/交付/良率等）+对标+预期成效。"),
        (r"建设内容|建设方案|技术方案|总体架构|架构", "写总体架构（业务/数据/应用/安全）+关键系统/集成关系+技术路线。"),
        (r"场景|应用|业务流程|流程", "写典型场景：现状→改造→系统支撑→数据闭环→指标提升。至少5-8个小点。"),
        (r"组织|保障|管理|制度|运维|安全", "写组织架构、制度流程、数据治理、安全与运维保障、风险与应对。"),
        (r"投资|预算|资金|费用", "写投资构成（软硬件/服务/集成/运维）+测算口径+资金来源与使用计划。"),
        (r"进度|计划|里程碑|实施", "写阶段划分、里程碑、交付物、验收与持续改进机制。"),
    ]
    for pattern, hint in rules:
        if re.search(pattern, t):
            return hint
    return "写成标准政府项目申报口径：现状→问题→方案→系统与数据→实施→成效与指标→保障。"


async def generate_section_text_by_title(
    *,
    title: str,
    level: int,
    project_context: str,
    cfg: AutoWriteCfg,
    cache: dict,
    model_id: Optional[str] = None,
) -> str:
    """
    生成申报书某一标题下正文：字数尽量多、分段清晰、口径像申报材料。
    必须：不编造企业具体数字/资质/专利编号（没有就用【待补】占位）。
    
    采用多轮生成策略：避免单次超时，同时实现"字数越多越好"。
    
    Args:
        title: 章节标题
        level: 标题层级
        project_context: 项目上下文（来自已解析/已填充的数据）
        cfg: 自动写作配置
        cache: 缓存字典（避免重复生成）
        model_id: LLM模型ID（可选）
    
    Returns:
        生成的正文内容
    """
    key = f"L{level}:{title.strip()}"
    if key in cache:
        return cache[key]

    min_words = _target_min_words(level, cfg)
    style_hint = _infer_section_style(title)

    try:
        # 使用项目现有的 LLM 调用方式
        from app.services.llm_model_store import get_llm_store
        
        store = get_llm_store()
        model = None
        
        # 如果指定了 model_id，使用指定的模型
        if model_id:
            try:
                model = store.get_model(model_id)
            except Exception as e:
                logger.warning(f"无法获取指定模型 {model_id}，使用默认模型: {e}")
        
        # 否则使用默认模型
        if not model:
            model = store.get_default_model()
        
        if not model:
            logger.error("未找到可用的 LLM 模型")
            return "【错误：未配置 LLM 模型，无法生成内容】"
        
        from app.services.llm_client import generate_answer_with_model
        
        # 根据配置决定是否采用多轮生成
        if cfg.multi_round and min_words >= 800:
            # 多轮生成：分 2-3 次，避免单次超时
            text = await _generate_multi_round(
                title=title,
                level=level,
                project_context=project_context,
                style_hint=style_hint,
                min_words=min_words,
                cfg=cfg,
                model=model,
            )
        else:
            # 单次生成
            text = await _generate_single_round(
                title=title,
                level=level,
                project_context=project_context,
                style_hint=style_hint,
                min_words=min_words,
                cfg=cfg,
                model=model,
            )
        
        text = text.strip()
        
        # 缓存结果
        cache[key] = text
        return text
        
    except Exception as e:
        logger.error(f"生成章节内容失败: title={title}, error={e}", exc_info=True)
        return f"【生成内容失败：{str(e)}】"


async def _generate_single_round(
    *,
    title: str,
    level: int,
    project_context: str,
    style_hint: str,
    min_words: int,
    cfg: AutoWriteCfg,
    model,
) -> str:
    """单次生成"""
    from app.services.llm_client import generate_answer_with_model
    
    system = (
        "你是省级项目/工厂申报材料撰写专家，擅长把标题扩写成规范、正式、可落地的申报书正文。"
        "写作要求：只基于给定上下文，不得虚构企业名称、金额、日期、专利号、检测报告号等；"
        "若缺信息，用【待补：xxx】占位；文风正式、条理清晰，尽量多写。"
    )

    user = f"""
【章节标题】{title}
【标题层级】H{level}

【写作侧重点】
{style_hint}

【可用上下文（来自已解析/已填充的数据，可能为空）】
{project_context}

【输出要求】
1) 直接输出正文，不要再写标题。
2) 至少 {min_words} 字（中文），分为 6~12 段，每段 2~5 句；可使用（1）（2）（3）等条目。
3) 若需要数字指标但上下文未给出，用【待补：指标口径/数值】占位。
4) 禁止输出"作为AI/无法"等元话术。
"""

    text = await generate_answer_with_model(
        system_prompt=system,
        user_message=user,
        history=[],
        model=model,
        overrides={
            "max_tokens": cfg.max_tokens,
            "temperature": 0.7,
        }
    )
    
    return text


async def _generate_multi_round(
    *,
    title: str,
    level: int,
    project_context: str,
    style_hint: str,
    min_words: int,
    cfg: AutoWriteCfg,
    model,
) -> str:
    """
    多轮生成：分 2-3 次调用 LLM，最后拼接
    这样可以实现"字数越多越好"，同时避免单次超时
    """
    from app.services.llm_client import generate_answer_with_model
    
    system = (
        "你是省级项目/工厂申报材料撰写专家，擅长把标题扩写成规范、正式、可落地的申报书正文。"
        "写作要求：只基于给定上下文，不得虚构企业名称、金额、日期、专利号、检测报告号等；"
        "若缺信息，用【待补：xxx】占位；文风正式、条理清晰。"
    )
    
    parts = []
    
    # 第 1 轮：主体正文
    user1 = f"""
【章节标题】{title}
【标题层级】H{level}

【写作侧重点】
{style_hint}

【可用上下文】
{project_context}

【本轮任务】
写该章节的**主体正文**（背景、现状、问题、必要性等核心内容），至少 {min_words // 2} 字，分 4~6 段。
直接输出正文，不要标题，不要"作为AI"等元话术。
"""
    
    try:
        text1 = await generate_answer_with_model(
            system_prompt=system,
            user_message=user1,
            history=[],
            model=model,
            overrides={
                "max_tokens": cfg.max_tokens,
                "temperature": 0.7,
            }
        )
        parts.append(text1.strip())
        logger.debug(f"第 1 轮生成完成: {len(text1)} 字符")
    except Exception as e:
        logger.error(f"第 1 轮生成失败: {e}", exc_info=True)
        parts.append(f"【第 1 轮生成失败】")
    
    # 第 2 轮：实施路径、保障措施
    user2 = f"""
【章节标题】{title}
【标题层级】H{level}

【写作侧重点】
{style_hint}

【可用上下文】
{project_context}

【本轮任务】
补充该章节的**实施路径、保障措施、组织管理**等内容，至少 {min_words // 3} 字，分 3~5 段。
直接输出正文，不要标题，不要重复前面的内容。
"""
    
    try:
        text2 = await generate_answer_with_model(
            system_prompt=system,
            user_message=user2,
            history=[],
            model=model,
            overrides={
                "max_tokens": cfg.max_tokens,
                "temperature": 0.7,
            }
        )
        parts.append(text2.strip())
        logger.debug(f"第 2 轮生成完成: {len(text2)} 字符")
    except Exception as e:
        logger.error(f"第 2 轮生成失败: {e}", exc_info=True)
        parts.append(f"【第 2 轮生成失败】")
    
    # 第 3 轮：指标对标、创新点（仅对重要章节）
    if level <= 2 and min_words >= 1000:
        user3 = f"""
【章节标题】{title}
【标题层级】H{level}

【写作侧重点】
{style_hint}

【可用上下文】
{project_context}

【本轮任务】
补充该章节的**目标指标、对标分析、创新点、预期成效**等内容，至少 {min_words // 4} 字，分 2~4 段。
直接输出正文，不要标题，不要重复前面的内容。
若上下文缺具体指标，用【待补：指标名称/数值】占位。
"""
        
        try:
            text3 = await generate_answer_with_model(
                system_prompt=system,
                user_message=user3,
                history=[],
                model=model,
                overrides={
                    "max_tokens": cfg.max_tokens,
                    "temperature": 0.7,
                }
            )
            parts.append(text3.strip())
            logger.debug(f"第 3 轮生成完成: {len(text3)} 字符")
        except Exception as e:
            logger.error(f"第 3 轮生成失败: {e}", exc_info=True)
            parts.append(f"【第 3 轮生成失败】")
    
    # 拼接所有部分（用双换行分隔）
    full_text = "\n\n".join(p for p in parts if p and not p.startswith("【") and not p.endswith("失败】"))
    
    logger.info(f"多轮生成完成: title={title}, 总字符数={len(full_text)}, 轮数={len(parts)}")
    
    return full_text


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


def _clear_body_keep_sectpr(doc: Document, apply_assets: Optional[Dict[str, Any]] = None) -> None:
    """
    清空文档正文内容，智能保留模板底板（封面、声明页等）
    
    优先级：
    1. 如果有 applyAssets.keepPlan：根据 LLM 分析结果精细化保留/删除
    2. 如果有 [[CONTENT]] 标记：保留标记前的内容
    3. 否则：智能识别内容开始位置（关键词匹配）
    4. 兜底：清空所有内容
    
    Args:
        doc: Document 对象（会原地修改）
        apply_assets: LLM 分析的保留/删除计划，包含：
            - anchors: 内容插入点列表
            - keepPlan.keepBlockIds: 应保留的块ID列表
            - keepPlan.deleteBlockIds: 应删除的块ID列表
    """
    body = doc._element.body
    
    # 保存最后的 sectPr
    last_sectpr = None
    for child in list(body):
        if child.tag == qn("w:sectPr"):
            last_sectpr = etree.fromstring(etree.tostring(child))
    
    # 方案1：使用 LLM 分析的 applyAssets（最智能）
    if apply_assets and isinstance(apply_assets, dict):
        keep_plan = apply_assets.get("keepPlan", {})
        anchors = apply_assets.get("anchors", [])
        
        # 如果有锚点，找到第一个锚点作为内容插入位置
        if anchors:
            first_anchor = anchors[0] if isinstance(anchors, list) else anchors
            anchor_block_id = first_anchor.get("blockId") if isinstance(first_anchor, dict) else None
            
            if anchor_block_id:
                logger.info(f"使用 LLM 分析的锚点: blockId={anchor_block_id}")
                # 找到锚点对应的元素索引（简化版：根据顺序估计）
                # TODO: 完整实现需要给每个元素添加 blockId 属性
                # 这里先使用简化逻辑：根据锚点中的 "reason" 字段查找关键词
                anchor_reason = first_anchor.get("reason", "") if isinstance(first_anchor, dict) else ""
                logger.info(f"锚点原因: {anchor_reason}")
                
                # 尝试从 reason 中提取关键词
                for idx, child in enumerate(list(body)):
                    if child.tag == qn("w:p"):
                        t_elements = child.findall('.//{%s}' % qn('w:t'))
                        paragraph_text = ''.join([t.text for t in t_elements if t.text])
                        
                        # 检查是否包含 [[CONTENT]] 标记
                        if "[[CONTENT]]" in paragraph_text:
                            logger.info(f"通过锚点找到 [[CONTENT]] 标记，位于第 {idx} 个元素")
                            children_to_remove = list(body)[idx:]
                            for child in children_to_remove:
                                body.remove(child)
                            if last_sectpr is not None:
                                body.append(last_sectpr)
                            return
    
    # 方案2：查找 [[CONTENT]] 标记（明确标记）
    content_marker_found = False
    content_marker_index = -1
    
    for idx, child in enumerate(list(body)):
        if child.tag == qn("w:p"):  # 段落
            # 获取段落文本
            t_elements = child.findall('.//{%s}' % qn('w:t'))
            paragraph_text = ''.join([t.text for t in t_elements if t.text])
            
            if "[[CONTENT]]" in paragraph_text:
                content_marker_found = True
                content_marker_index = idx
                logger.info(f"在第 {idx} 个元素中找到 [[CONTENT]] 标记")
                break
    
    if content_marker_found:
        # 删除 [[CONTENT]] 标记及其后的所有内容
        logger.info(f"保留前 {content_marker_index} 个元素（封面等），删除 [[CONTENT]] 及其后的内容")
        children_to_remove = list(body)[content_marker_index:]
        for child in children_to_remove:
            body.remove(child)
        if last_sectpr is not None:
            body.append(last_sectpr)
        return
    
    # 方案3：智能识别内容开始位置（关键词匹配）
    content_start_keywords = ["投标函", "目录", "第一章", "第1章", "一、", "1.", "1、"]
    
    for idx, child in enumerate(list(body)):
        if child.tag == qn("w:p"):  # 段落
            if idx <= 5:  # 至少保留前5个段落（封面信息）
                continue
            
            # 获取段落文本和样式
            t_elements = child.findall('.//{%s}' % qn('w:t'))
            paragraph_text = ''.join([t.text for t in t_elements if t.text])
            
            pPr = child.find(qn('w:pPr'))
            if pPr is not None:
                pStyle = pPr.find(qn('w:pStyle'))
                if pStyle is not None:
                    style_val = pStyle.get(qn('w:val'))
                    # 检查是否是标题样式
                    if style_val and ('标题' in style_val or 'Heading' in style_val):
                        # 检查是否包含内容开始关键词
                        for keyword in content_start_keywords:
                            if keyword in paragraph_text:
                                content_marker_found = True
                                content_marker_index = idx
                                logger.info(f"智能识别内容开始位置：第 {idx} 个元素，标题为「{paragraph_text[:30]}」")
                                break
            if content_marker_found:
                break
    
    if content_marker_found:
        # 删除识别出的内容开始位置及其后的所有内容
        logger.info(f"保留前 {content_marker_index} 个元素（封面等），删除智能识别的内容区")
        children_to_remove = list(body)[content_marker_index:]
        for child in children_to_remove:
            body.remove(child)
        if last_sectpr is not None:
            body.append(last_sectpr)
        return
    
    # 方案4：兜底 - 清空所有内容
    logger.warning("未找到任何内容标记或锚点，清空所有正文内容（保留 sectPr）")
    for child in list(body):
        body.remove(child)
    
    # 恢复 sectPr
    if last_sectpr is not None:
        body.append(last_sectpr)


def _add_toc_field(doc: Document, levels: str = "1-5", include_numbering: bool = False) -> None:
    """
    添加目录域（TOC field）
    
    注意：LibreOffice 可能不会自动更新目录，需要在 Word 中打开按 F9 更新
    
    Args:
        doc: Document 对象
        levels: 目录层级范围（如 "1-5"）
        include_numbering: 是否在目录中包含标题编号（默认 False）
    """
    p = doc.add_paragraph()
    
    # TOC 开关说明：
    # \o "1-5" - 使用大纲级别 1-5
    # \h - 超链接
    # \z - 隐藏页码和制表符
    # \u - 使用段落大纲级别
    # \n - 不包含页码前的编号（新增，用于隐藏标题编号）
    toc_switches = f'TOC \\o "{levels}" \\h \\z \\u'
    if not include_numbering:
        toc_switches += ' \\n'  # 添加 \n 开关，隐藏标题前的编号
    
    # 创建 fldSimple 元素
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), toc_switches)
    
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


async def render_directory_tree_to_docx(
    template_path: str,
    output_path: str,
    roots: List[DirNode],
    section_prototypes: Dict[PageVariant, SectPrototype],
    *,
    include_toc: bool = True,
    prefix_numbering_in_text: bool = False,
    heading_style_map: Optional[Dict[int, str]] = None,
    normal_style_name: Optional[str] = None,
    apply_assets: Optional[Dict[str, Any]] = None,
    insert_section_body: Optional[callable] = None,
    auto_generate_content: bool = False,
    auto_write_cfg: Optional[AutoWriteCfg] = None,
    project_context: str = "",
    model_id: Optional[str] = None,
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
        apply_assets: LLM分析的保留/删除计划（anchors, keepPlan等）
        insert_section_body: 插入节正文的回调函数（node: DirNode, doc: Document）
        auto_generate_content: 是否自动生成内容（当 summary 为空时）
        auto_write_cfg: 自动写作配置（如果未提供则使用默认值）
        project_context: 项目上下文信息（用于自动生成内容）
        model_id: LLM模型ID（用于自动生成内容）
    """
    logger.info(f"开始渲染文档: template={template_path}, output={output_path}, auto_generate={auto_generate_content}")
    
    # 初始化自动写作配置和缓存
    if auto_generate_content and auto_write_cfg is None:
        auto_write_cfg = AutoWriteCfg()
    
    content_cache = {} if auto_generate_content else None
    
    # 1. 加载模板（保留页眉页脚）
    doc = Document(template_path)
    
    # 2. 清空正文内容（保留最后的 sectPr，使用 LLM 分析的保留计划）
    _clear_body_keep_sectpr(doc, apply_assets=apply_assets)
    
    # 3. 添加目录页（可选）
    if include_toc:
        toc_title = doc.add_paragraph("目录", style=_get_heading_style_name(1, heading_style_map))
        toc_title.alignment = 1  # 居中
        _add_toc_field(doc, "1-5", include_numbering=False)  # 目录中不显示标题编号
        doc.add_page_break()
    
    # 4. DFS 遍历目录树，写入内容
    async def emit_node(node: DirNode, depth: int = 0):
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
        
        # 4.3 添加 summary（正文内容）
        content_to_add = node.summary
        
        # 如果启用了自动生成且当前节点没有实质内容（空或占位符），则自动生成
        if auto_generate_content and _is_empty_or_placeholder(content_to_add):
            try:
                logger.info(f"自动生成内容: title={node.title}, level={node.level}")
                generated_text = await generate_section_text_by_title(
                    title=node.title,
                    level=node.level,
                    project_context=project_context,
                    cfg=auto_write_cfg,
                    cache=content_cache,
                    model_id=model_id,
                )
                
                # 将生成的文本按空行分段，写入多个段落
                # 这样保持了 docx 的段落结构，更美观
                paragraphs = [
                    p.strip() 
                    for p in re.split(r"\n{2,}|\r\n{2,}", generated_text) 
                    if p.strip()
                ]
                
                for para in paragraphs:
                    if normal_style_name:
                        try:
                            doc.add_paragraph(para, style=normal_style_name)
                        except Exception as e:
                            logger.warning(f"样式 {normal_style_name} 不存在，使用默认段落: {e}")
                            doc.add_paragraph(para)
                    else:
                        doc.add_paragraph(para)
                
                logger.info(f"自动生成完成: {len(paragraphs)} 个段落, 总字符数 {len(generated_text)}")
                
            except Exception as e:
                logger.error(f"自动生成内容失败: title={node.title}, error={e}", exc_info=True)
                doc.add_paragraph(f"【自动生成内容失败：{str(e)}】")
        
        # 否则，添加原有内容（如果有的话）
        elif content_to_add and not _is_empty_or_placeholder(content_to_add):
            # 优先使用 normal_style_name，如果未指定则使用默认段落
            if normal_style_name:
                try:
                    doc.add_paragraph(content_to_add, style=normal_style_name)
                except Exception as e:
                    logger.warning(f"样式 {normal_style_name} 不存在，使用默认段落: {e}")
                    doc.add_paragraph(content_to_add)
            else:
                doc.add_paragraph(content_to_add)
        
        # 4.4 插入节正文内容（如果提供了回调）
        if insert_section_body:
            try:
                insert_section_body(node, doc)
            except Exception as e:
                logger.error(f"插入节正文失败: node={node.id}, error={e}", exc_info=True)
                doc.add_paragraph(f"[正文内容加载失败: {str(e)}]")
        
        # 4.5 递归处理子节点
        for child in node.children:
            await emit_node(child, depth + 1)
    
    # 遍历所有根节点
    for root in roots:
        await emit_node(root)
    
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

