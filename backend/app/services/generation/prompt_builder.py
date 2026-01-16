"""
统一的Prompt构建器
支持Tender和Declare两种场景的Prompt生成
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from .document_retriever import RetrievalResult
from .template_engine import get_template_engine

logger = logging.getLogger(__name__)


@dataclass
class PromptContext:
    """Prompt构建上下文"""
    document_type: str  # 'tender' or 'declare'
    section_title: str
    section_level: int
    project_info: Dict[str, Any]
    requirements: Optional[Dict[str, Any]] = None
    retrieval_result: Optional[RetrievalResult] = None
    style_preference: Optional[str] = None  # 'formal', 'technical', 'creative'
    section_metadata: Optional[Dict[str, Any]] = None  # 章节元数据（如notes等）


@dataclass
class PromptOutput:
    """Prompt输出"""
    system_prompt: str
    user_prompt: str
    temperature: float
    max_tokens: int


class PromptBuilder:
    """
    统一的Prompt构建器
    
    功能：
    1. 根据文档类型和章节生成System Prompt
    2. 动态注入检索到的资料
    3. 构建结构化的User Prompt
    4. 配置LLM参数（temperature、max_tokens）
    """
    
    # 基础配置
    BASE_TEMPERATURE = 0.7
    BASE_MAX_TOKENS = 2000
    
    # 字数要求映射
    MIN_WORDS_MAP = {
        1: 800,
        2: 500,
        3: 300,
        4: 200
    }
    
    def build(self, context: PromptContext) -> PromptOutput:
        """
        构建Prompt
        
        Args:
            context: Prompt构建上下文
            
        Returns:
            Prompt输出
        """
        if context.document_type == "tender":
            return self._build_tender_prompt(context)
        elif context.document_type == "declare":
            return self._build_declare_prompt(context)
        else:
            raise ValueError(f"Unsupported document_type: {context.document_type}")
    
    def _build_tender_prompt(self, context: PromptContext) -> PromptOutput:
        """构建招投标Prompt"""
        # System Prompt
        system_prompt = self._build_tender_system_prompt(context)
        
        # User Prompt
        user_prompt = self._build_tender_user_prompt(context)
        
        # 参数配置
        temperature = self.BASE_TEMPERATURE
        max_tokens = self.BASE_MAX_TOKENS
        
        # 根据层级调整token数
        if context.section_level == 1:
            max_tokens = 3000
        elif context.section_level >= 4:
            max_tokens = 1500
        
        return PromptOutput(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )
    
    def _build_declare_prompt(self, context: PromptContext) -> PromptOutput:
        """构建申报书Prompt"""
        # System Prompt
        system_prompt = self._build_declare_system_prompt(context)
        
        # User Prompt
        user_prompt = self._build_declare_user_prompt(context)
        
        # 参数配置
        temperature = 0.6  # 申报书更严谨，降低随机性
        max_tokens = 4096  # ✅ 增加到4096，避免内容被截断
        
        return PromptOutput(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )
    
    def _build_tender_system_prompt(self, context: PromptContext) -> str:
        """构建招投标System Prompt（使用模板）"""
        template_engine = get_template_engine()
        has_materials = context.retrieval_result and context.retrieval_result.has_relevant
        
        template_context = {
            "has_materials": has_materials
        }
        
        try:
            return template_engine.render_file("tender_system.md", template_context)
        except Exception as e:
            logger.warning(f"Failed to render template, using fallback: {e}")
            # 降级为硬编码版本
            if has_materials:
                return (
                    "你是专业的投标文件撰写专家，擅长根据招标要求、项目信息和企业资料生成规范、专业的投标书内容。\n"
                    "\n"
                    "写作要求：\n"
                    "1. 优先基于提供的企业资料生成内容，确保真实准确\n"
                    "2. 充分利用企业的实际数据、案例、资质等信息\n"
                    "3. 语言正式、逻辑清晰、结构完整\n"
                    "4. 适当使用列表和分段提高可读性\n"
                    "5. 突出企业优势和竞争力"
                )
            else:
                return (
                    "你是专业的投标文件撰写专家，擅长根据招标要求和项目信息生成规范、专业的投标书内容。\n"
                    "\n"
                    "写作要求：\n"
                    "1. 基于提供的项目信息生成内容\n"
                    "2. 如果信息不足则生成符合行业规范的通用内容\n"
                    "3. 语言正式、逻辑清晰、结构完整\n"
                    "4. 适当使用列表和分段提高可读性"
                )
    
    def _build_declare_system_prompt(self, context: PromptContext) -> str:
        """构建申报书System Prompt（使用模板）"""
        template_engine = get_template_engine()
        has_materials = context.retrieval_result and context.retrieval_result.has_relevant
        
        template_context = {
            "has_materials": has_materials
        }
        
        try:
            return template_engine.render_file("declare_system.md", template_context)
        except Exception as e:
            logger.warning(f"Failed to render template, using fallback: {e}")
            # 降级为硬编码版本
            if has_materials:
                return (
                    "你是资深的项目申报文档撰写专家，精通各类项目申报书的撰写规范和评审标准。\n"
                    "\n"
                    "写作要求：\n"
                    "1. 结合申报要求和用户提供的资料，主动扩展完善内容\n"
                    "2. 必须输出完整、专业、符合评审标准的内容\n"
                    "3. 可以借鉴该类型申报书的典型内容结构\n"
                    "4. 优先使用用户资料，不足部分可基于行业标准和最佳实践补充\n"
                    "5. 确保内容的真实性、专业性和可信度"
                )
            else:
                return (
                    "你是资深的项目申报文档撰写专家，精通各类项目申报书的撰写规范和评审标准。\n"
                    "\n"
                    "写作要求：\n"
                    "1. 结合申报要求，生成符合规范的内容框架\n"
                    "2. 基于行业标准和最佳实践生成合理内容\n"
                    "3. 标注需要用户补充的关键信息点\n"
                    "4. 确保内容的专业性和完整性"
                )
    
    def _build_tender_user_prompt(self, context: PromptContext) -> str:
        """构建招投标User Prompt（使用模板）"""
        template_engine = get_template_engine()
        min_words = self.MIN_WORDS_MAP.get(context.section_level, 200)
        has_materials = context.retrieval_result and context.retrieval_result.has_relevant
        
        materials_text = ""
        if has_materials:
            materials_text = context.retrieval_result.format_for_prompt()
        
        # ✅ 提取用户自定义要求
        custom_requirements = ""
        if context.requirements and "custom_requirements" in context.requirements:
            custom_requirements = context.requirements["custom_requirements"]
        
        # ✅ 提取格式范文信息
        format_snippets = []
        format_snippets_list = ""
        if context.requirements and "format_snippets" in context.requirements:
            format_snippets = context.requirements["format_snippets"]
            # 构建格式范文列表文本
            if format_snippets:
                snippet_lines = []
                for i, snippet in enumerate(format_snippets, 1):
                    snippet_lines.append(f"{i}. **{snippet.get('title', '未命名')}**")
                format_snippets_list = "\n".join(snippet_lines)
        
        template_context = {
            "section_title": context.section_title,
            "section_level": context.section_level,
            "project_info": self._format_project_info(context.project_info),
            "has_materials": has_materials,
            "materials": materials_text,
            "min_words": min_words,
            "custom_requirements": custom_requirements,  # ✅ 传递用户要求
            "format_snippets": len(format_snippets) > 0,  # ✅ 是否有格式范文
            "format_snippets_count": len(format_snippets),  # ✅ 格式范文数量
            "format_snippets_list": format_snippets_list  # ✅ 格式范文列表
        }
        
        try:
            return template_engine.render_file("tender_user.md", template_context)
        except Exception as e:
            logger.warning(f"Failed to render template, using fallback: {e}")
            # 降级为原有逻辑
            parts = [
                f"【章节标题】{context.section_title}",
                f"【标题层级】第{context.section_level}级",
                "",
                "【项目信息】",
                self._format_project_info(context.project_info),
                ""
            ]
            
            if has_materials:
                parts.append(materials_text)
                parts.append("")
                parts.append(
                    "⚠️ **写作指导**\n"
                    "- 请优先使用上述企业资料撰写内容\n"
                    "- 确保内容真实、具体、有说服力\n"
                    "- 可以引用具体数据、案例、资质等\n"
                    "- 突出企业在该领域的实力和优势"
                )
            else:
                parts.append(
                    "⚠️ **写作指导**\n"
                    "- 未检索到相关企业资料\n"
                    "- 请根据章节标题和行业规范生成合理内容\n"
                    "- 标注【待补充】提示用户后续完善"
                )
            
            parts.append("")
            
            # ✅ 如果有格式范文信息，展示给AI
            if context.requirements and "format_snippets" in context.requirements:
                format_snippets = context.requirements["format_snippets"]
                if format_snippets:
                    parts.append(f"【📋 可用格式范文】")
                    parts.append(f"系统已从招标文件中提取了以下 {len(format_snippets)} 个格式范文：")
                    parts.append("")
                    for i, snippet in enumerate(format_snippets, 1):
                        parts.append(f"{i}. {snippet.get('title', '未命名')}")
                    parts.append("")
                    parts.append("⚠️ **使用指导**")
                    parts.append("- 如果当前章节标题与上述格式范文匹配或相似，强烈建议参考相应的格式范文")
                    parts.append("- 格式范文通常包含标准的格式、必要的条款和填写示例")
                    parts.append("- 如适用，请生成符合该格式范文结构的内容")
                    parts.append("")
            
            # ✅ 如果有用户自定义要求，优先展示
            if context.requirements and "custom_requirements" in context.requirements:
                custom_req = context.requirements["custom_requirements"]
                parts.append("【🎯 用户特殊要求】")
                parts.append(custom_req)
                parts.append("")
                parts.append("⚠️ **重要提示**")
                parts.append("- 请严格按照上述用户要求生成内容")
                parts.append("- 如果要求生成表格，必须使用HTML <table>、<tr>、<td> 标签")
                parts.append("- 如果要求某种格式，必须完全遵循该格式要求")
                parts.append("")
            
            parts.append("【输出要求】")
            parts.append("1. 输出HTML格式的章节内容（使用<p>、<ul>、<li>、<table>等标签）")
            parts.append(f"2. 内容至少{min_words}字，分为3-6段")
            parts.append("3. 根据标题类型生成合适内容：")
            parts.append("   - 如果是「投标函」「授权书」等格式类章节，生成对应的格式范本")
            parts.append("   - 如果是技术方案类章节，详细描述技术路线、方法、保障措施等")
            parts.append("   - 如果是商务类章节，说明报价依据、优惠措施、付款方式等")
            parts.append("   - 如果是公司/业绩类章节，充分利用企业资料展示实力")
            parts.append("   - 如果用户要求表格格式，必须生成标准HTML表格（<table>标签）")
            parts.append("4. 不要输出章节标题，只输出正文内容")
            
            return "\n".join(parts)
    
    def _build_declare_user_prompt(self, context: PromptContext) -> str:
        """构建申报书User Prompt（使用模板）"""
        template_engine = get_template_engine()
        has_requirements = context.requirements is not None
        has_materials = context.retrieval_result and context.retrieval_result.has_relevant
        
        # 🔍 DEBUG: 检查检索结果
        logger.info(f"[PromptBuilder DEBUG] has_materials={has_materials}")
        if context.retrieval_result:
            logger.info(f"[PromptBuilder DEBUG] chunks数量={len(context.retrieval_result.chunks)}")
            logger.info(f"[PromptBuilder DEBUG] has_relevant={context.retrieval_result.has_relevant}")
        
        # 提取章节说明（notes）
        section_notes = ""
        if context.section_metadata and isinstance(context.section_metadata, dict):
            section_notes = context.section_metadata.get("notes", "")
        
        requirements_text = ""
        if has_requirements:
            requirements_text = self._format_requirements(context.requirements)
        
        materials_text = ""
        if has_materials:
            materials_text = context.retrieval_result.format_for_prompt()
            # 🔍 DEBUG: 检查格式化后的内容
            logger.info(f"[PromptBuilder DEBUG] materials_text长度={len(materials_text)}")
            logger.info(f"[PromptBuilder DEBUG] materials_text预览={materials_text[:300]}")
        
        # 检测是否有图片信息
        has_images = False
        if has_materials and context.retrieval_result.chunks:
            for chunk in context.retrieval_result.chunks:
                metadata = chunk.get("metadata", {})
                if metadata.get("asset_type") == "image" or "图片" in chunk.get("text", ""):
                    has_images = True
                    break
        
        # ✅ 提取用户自定义要求
        custom_requirements = ""
        if context.requirements and "custom_requirements" in context.requirements:
            custom_requirements = context.requirements["custom_requirements"]
        
        template_context = {
            "section_title": context.section_title,
            "section_notes": section_notes,  # ✅ 新增
            "custom_requirements": custom_requirements,  # ✅ 传递用户要求
            "has_requirements": has_requirements,
            "requirements": requirements_text,
            "has_materials": has_materials,
            "materials": materials_text,
            "has_images": has_images,
            "example_confidence": "HIGH/MEDIUM/LOW"
        }
        
        try:
            return template_engine.render_file("declare_user.md", template_context)
        except Exception as e:
            logger.warning(f"Failed to render template, using fallback: {e}")
            # 降级为原有逻辑
            parts = [
                f"【章节标题】{context.section_title}",
                ""
            ]
            
            if section_notes:  # ✅ 新增
                parts.append("【章节说明】")
                parts.append(section_notes)
                parts.append("")
            
            if has_requirements:
                parts.append("【申报要求】")
                parts.append(requirements_text)
                parts.append("")
            
            if has_materials:
                parts.append(materials_text)
                parts.append("")
                parts.append(
                    "⚠️ **写作指导**\n"
                    "- 结合申报要求和用户资料，主动扩展完善内容\n"
                    "- 必须输出完整、专业的申报书内容\n"
                    "- 优先使用用户资料，不足部分可基于行业标准补充\n"
                    "- 如果用户资料包含图片，请在合适位置插入 {image:图片文件名}"
                )
            else:
                parts.append(
                    "⚠️ **写作指导**\n"
                    "- 未检索到相关用户资料\n"
                    "- 请基于申报要求和行业标准生成内容框架\n"
                    "- 标注关键信息点需要用户补充"
                )
            
            parts.append("")
            parts.append("【输出要求】")
            parts.append("1. 输出完整的申报书章节内容（HTML格式）")
            parts.append("2. 内容必须完整、专业、符合评审标准")
            parts.append("3. 结构清晰，逻辑严密，语言规范")
            parts.append("4. 不要输出章节标题，只输出正文内容")
            parts.append("5. 输出置信度：")
            parts.append("   - HIGH: 基于详细的用户资料生成")
            parts.append("   - MEDIUM: 部分基于用户资料，部分基于行业标准扩展")
            parts.append("   - LOW: 主要基于行业标准和最佳实践生成")
            
            return "\n".join(parts)
    
    def _format_project_info(self, project_info: Dict[str, Any]) -> str:
        """
        格式化项目信息 - 完整版
        
        ✅ 确保所有客户信息都被提取和展示
        """
        lines = []
        
        # ===== 核心项目信息 =====
        core_fields = {
            "project_name": "项目名称",
            "project_number": "项目编号",
            "procurement_method": "采购方式",
            "budget": "预算金额",
            "max_price": "最高限价",
        }
        
        for key, label in core_fields.items():
            value = project_info.get(key)
            if value:
                lines.append(f"**{label}**：{value}")
        
        # ===== 招标人/采购人信息（重要！） =====
        lines.append("")
        lines.append("**📋 招标人/采购人信息**（以下信息来自招标文件，不得编造）")
        
        tenderee_fields = {
            "tenderee": "招标人",
            "owner_name": "采购人名称",
            "agency_name": "代理机构",
            "contact_person": "联系人",
            "contact_phone": "联系电话",
            "contact_email": "联系邮箱",
        }
        
        has_tenderee_info = False
        for key, label in tenderee_fields.items():
            value = project_info.get(key)
            if value:
                lines.append(f"{label}：{value}")
                has_tenderee_info = True
        
        if not has_tenderee_info:
            lines.append("（招标人信息待补充 - 请使用【待补充】标记）")
        
        # ===== 投标/响应信息 =====
        lines.append("")
        lines.append("**📅 投标信息**")
        
        bid_fields = {
            "bid_deadline": "投标截止时间",
            "bid_opening_time": "开标时间",
            "bid_opening_location": "开标地点",
            "submission_address": "文件递交地址",
            "bid_bond_amount": "保证金金额",
        }
        
        for key, label in bid_fields.items():
            value = project_info.get(key)
            if value:
                lines.append(f"{label}：{value}")
        
        # ===== 项目范围和要求 =====
        scope_data = project_info.get("project_scope") or project_info.get("project_overview")
        if scope_data:
            lines.append("")
            lines.append("**📝 项目范围**")
            
            # 确保scope是字符串类型
            if isinstance(scope_data, dict):
                # 如果是字典，提取可能的字段
                scope_str = (
                    scope_data.get("project_scope") or 
                    scope_data.get("description") or 
                    scope_data.get("content") or 
                    str(scope_data)
                )
            else:
                scope_str = str(scope_data)
            
            lines.append(scope_str)
        
        # ===== 重要提示 =====
        lines.append("")
        lines.append("⚠️ **重要提示**")
        lines.append("- 以上所有信息均来自真实的招标文件，**严禁编造或臆测**")
        lines.append("- 生成内容时必须使用上述真实信息，如信息不足请标注【待补充】")
        lines.append("- 投标人（我方）的公司信息应从企业资料中获取，不得编造")
        
        # 检查是否有足够的实质性内容（只对字符串类型检查）
        content_lines = [l for l in lines if isinstance(l, str) and l and not l.startswith("**") and not l.startswith("-") and not l.startswith("⚠️")]
        if not lines or len(content_lines) < 3:
            lines.append("（项目信息不足 - 请标注【待补充】并提示用户完善）")
        
        return "\n".join(lines)
    
    def _format_requirements(self, requirements: Dict[str, Any]) -> str:
        """格式化申报要求和用户自定义要求"""
        lines = []
        
        # ✅ 优先处理用户自定义要求（来自AI助手）
        if "custom_requirements" in requirements:
            custom_req = requirements["custom_requirements"]
            lines.append("【🎯 用户特殊要求】")
            lines.append(custom_req)
            lines.append("")
            lines.append("⚠️ **重要提示**")
            lines.append("- 请严格按照上述用户要求生成内容")
            lines.append("- 如果要求生成表格，必须使用HTML <table>、<tr>、<td> 标签")
            lines.append("- 如果要求某种格式，必须完全遵循该格式要求")
            lines.append("")
        
        # 提取申报要求关键字段
        if "summary" in requirements:
            lines.append(requirements["summary"])
        elif "data_json" in requirements and isinstance(requirements["data_json"], dict):
            data = requirements["data_json"]
            if "summary" in data:
                lines.append(data["summary"])
        
        if not lines:
            lines.append("（无具体要求）")
        
        return "\n".join(lines)

