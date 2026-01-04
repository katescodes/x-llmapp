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
        
        template_context = {
            "section_title": context.section_title,
            "section_level": context.section_level,
            "project_info": self._format_project_info(context.project_info),
            "has_materials": has_materials,
            "materials": materials_text,
            "min_words": min_words
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
            parts.append("【输出要求】")
            parts.append("1. 输出HTML格式的章节内容（使用<p>、<ul>、<li>等标签）")
            parts.append(f"2. 内容至少{min_words}字，分为3-6段")
            parts.append("3. 根据标题类型生成合适内容：")
            parts.append("   - 如果是「投标函」「授权书」等格式类章节，生成对应的格式范本")
            parts.append("   - 如果是技术方案类章节，详细描述技术路线、方法、保障措施等")
            parts.append("   - 如果是商务类章节，说明报价依据、优惠措施、付款方式等")
            parts.append("   - 如果是公司/业绩类章节，充分利用企业资料展示实力")
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
        
        template_context = {
            "section_title": context.section_title,
            "section_notes": section_notes,  # ✅ 新增
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
        """格式化项目信息"""
        lines = []
        
        # 常见字段映射
        field_map = {
            "project_name": "项目名称",
            "tenderee": "招标人",
            "budget": "预算金额",
            "project_overview": "项目概况",
            "requirements": "基本要求"
        }
        
        for key, label in field_map.items():
            value = project_info.get(key)
            if value:
                lines.append(f"{label}：{value}")
        
        if not lines:
            lines.append("（项目信息不足）")
        
        return "\n".join(lines)
    
    def _format_requirements(self, requirements: Dict[str, Any]) -> str:
        """格式化申报要求"""
        lines = []
        
        # 提取关键字段
        if "summary" in requirements:
            lines.append(requirements["summary"])
        elif "data_json" in requirements and isinstance(requirements["data_json"], dict):
            data = requirements["data_json"]
            if "summary" in data:
                lines.append(data["summary"])
        
        if not lines:
            lines.append("（无具体要求）")
        
        return "\n".join(lines)

