"""
LLM Orchestrator Service

实现两段式编排：
1. Extractor Call: 需求抽取 → RequirementJSON
2. Answer Call: 模块化答案生成 → sections
3. Repair Call (可选): 结构修复
"""

import json
import logging
import re
from typing import Any, Callable, Awaitable, List, Optional, Dict

from app.schemas.chat import Message, Source
from app.schemas.orchestrator import (
    RequirementJSON,
    ChatSection,
    OrchestratedResponse,
    DetailLevel,
    IntentType,
    INTENT_BLUEPRINTS,
    MODULE_TITLES,
)
from .prompts import (
    EXTRACTOR_PROMPT,
    MODULAR_SYSTEM_PROMPT,
    REPAIR_PROMPT,
    DETAIL_LEVEL_PARAMS,
)

logger = logging.getLogger(__name__)


class OrchestratorService:
    """LLM 编排服务"""
    
    def __init__(
        self,
        call_llm: Callable[[str, str, List[Message]], Awaitable[str]],
        call_llm_stream: Optional[
            Callable[[str, str, List[Message], Callable[[str], Awaitable[None]]], Awaitable[str]]
        ] = None,
    ):
        """
        初始化编排器
        
        Args:
            call_llm: LLM 调用函数（非流式）
            call_llm_stream: LLM 调用函数（流式，可选）
        """
        self.call_llm = call_llm
        self.call_llm_stream = call_llm_stream
    
    async def extract_requirements(
        self,
        user_message: str,
        history: List[Message],
        ui_detail_level: Optional[str] = None,
    ) -> RequirementJSON:
        """
        步骤1: 需求抽取
        
        Args:
            user_message: 用户输入
            history: 历史对话
            ui_detail_level: UI 设置的详尽度（brief/normal/detailed）
        
        Returns:
            需求理解 JSON
        """
        # 准备历史对话文本
        history_text = self._format_history(history)
        
        # 识别用户文本中的详尽度关键词
        text_detail_level = self._detect_detail_level_from_text(user_message)
        
        # 合并 UI 设置和文本关键词（文本关键词优先）
        final_ui_level = text_detail_level or ui_detail_level or "normal"
        
        # 构建提示词（不使用 .format() 以避免 JSON 示例中的花括号被解析）
        prompt = EXTRACTOR_PROMPT + f"""

用户输入：{user_message}

UI详尽度设置：{final_ui_level}

历史对话：
{history_text}

输出JSON：
"""
        
        # 调用 LLM（非流式，低温度，限制 token）
        try:
            response = await self.call_llm(
                "",  # 无 system prompt，prompt 中已包含指令
                prompt,
                [],  # 无历史，提示词中已包含
            )
            
            # 解析 JSON
            requirements = self._parse_json_response(response, RequirementJSON)
            
            # 如果解析失败，使用默认值
            if requirements is None:
                logger.warning("Failed to parse requirements JSON, using defaults")
                requirements = self._build_default_requirements(
                    user_message, final_ui_level
                )
            
            # 后处理：确保 blueprint_modules 有值
            if not requirements.blueprint_modules:
                requirements.blueprint_modules = self._get_default_blueprint(
                    requirements.intent
                )
            
            logger.info(
                f"Requirements extracted: intent={requirements.intent}, "
                f"detail_level={requirements.detail_level}, "
                f"modules={len(requirements.blueprint_modules)}"
            )
            
            return requirements
            
        except Exception as exc:
            logger.exception("[orchestrator] extractor failed")  # 记录完整堆栈
            logger.error(f"Extract requirements failed: {exc}", exc_info=True)
            return self._build_default_requirements(user_message, final_ui_level)
    
    async def generate_modular_answer(
        self,
        user_message: str,
        requirements: RequirementJSON,
        context: str,
        history: List[Message],
        sources: List[Source],
        on_token: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> str:
        """
        步骤2: 生成模块化答案
        
        Args:
            user_message: 用户输入
            requirements: 需求理解
            context: 检索到的上下文
            history: 历史对话
            sources: 检索源
            on_token: 流式输出回调
        
        Returns:
            模块化答案（Markdown，用 ## 分隔模块）
        """
        # 构建系统提示词
        system_prompt = MODULAR_SYSTEM_PROMPT
        
        # 构建用户提示词（不使用 .format() 避免潜在的花括号问题）
        requirements_json = json.dumps(
            requirements.model_dump(),
            ensure_ascii=False,
            indent=2,
        )
        
        history_text = self._format_history(history)
        
        sources_text = self._format_sources(sources)
        context_with_sources = f"{context}\n\n{sources_text}".strip()
        
        user_prompt = system_prompt + f"""

**用户问题**：{user_message}

**需求分析**：
{requirements_json}

**详尽度级别**：{requirements.detail_level}

**答案模块蓝图**：{", ".join(requirements.blueprint_modules)}

**检索到的上下文**：
{context_with_sources or "[无检索上下文]"}

**历史对话**：
{history_text or "[无历史对话]"}

开始生成模块化答案（使用 ## 标题分隔模块）：
"""
        
        # 调用 LLM（可流式）
        try:
            if on_token and self.call_llm_stream:
                answer = await self.call_llm_stream(
                    "",  # 提示词中已包含所有指令
                    user_prompt,
                    [],
                    on_token,
                )
            else:
                answer = await self.call_llm("", user_prompt, [])
            
            return answer
            
        except Exception as exc:
            logger.error(f"Generate modular answer failed: {exc}", exc_info=True)
            return f"抱歉，生成答案时出错：{str(exc)}"
    
    async def repair_structure(
        self,
        raw_answer: str,
        blueprint_modules: List[str],
    ) -> List[ChatSection]:
        """
        步骤3: 结构修复（可选）
        
        Args:
            raw_answer: 原始答案
            blueprint_modules: 预期模块列表
        
        Returns:
            结构化的 sections
        """
        # 构建修复提示词（不使用 .format() 避免 JSON 中的花括号问题）
        prompt = REPAIR_PROMPT + f"""

**输入**：
原始答案：
{raw_answer}

预期模块蓝图：
{", ".join(blueprint_modules)}

**输出格式**（严格 JSON，无额外文字）：
现在开始修复，输出 JSON：
"""
        
        try:
            response = await self.call_llm("", prompt, [])
            
            # 解析 JSON
            parsed = self._parse_json_response(response, dict)
            
            if parsed and "sections" in parsed:
                sections = [
                    ChatSection(**section)
                    for section in parsed["sections"]
                ]
                logger.info(f"Structure repaired: {len(sections)} sections")
                return sections
            else:
                logger.warning("Repair response missing sections, fallback to parsing")
                return self._parse_sections_from_markdown(raw_answer, blueprint_modules)
                
        except Exception as exc:
            logger.error(f"Repair structure failed: {exc}", exc_info=True)
            return self._parse_sections_from_markdown(raw_answer, blueprint_modules)
    
    def parse_sections_from_answer(
        self,
        answer: str,
        blueprint_modules: List[str],
    ) -> List[ChatSection]:
        """
        从 Markdown 答案中解析 sections
        
        Args:
            answer: Markdown 格式的答案
            blueprint_modules: 预期模块列表
        
        Returns:
            结构化的 sections
        """
        return self._parse_sections_from_markdown(answer, blueprint_modules)
    
    # ==================== 私有辅助方法 ====================
    
    def _detect_detail_level_from_text(self, text: str) -> Optional[str]:
        """从用户文本中检测详尽度关键词
        
        优先级：用户文本关键词 > UI 设置
        - 包含 detailed 关键词 => "detailed"
        - 包含 brief 关键词 => "brief"
        - 无关键词 => None（使用 UI 设置或默认值）
        """
        text_lower = text.lower()
        
        # brief 关键词（简洁优先，优先检查）
        brief_keywords = [
            "简短", "只要结论", "一句话", "不要展开",  # 用户特别要求的关键词
            "别解释", "快速", "概括", "简单说", 
            "不要啰嗦", "直接说", "精简",
        ]
        for kw in brief_keywords:
            if kw in text_lower:
                return "brief"
        
        # detailed 关键词（详细说明）
        detailed_keywords = [
            "详细", "逐条", "每个", "深入", "全面", "展开", "越详细越好",  # 用户特别要求的关键词
            "更细", "多例子", "更完整", "详细解释", 
            "具体说明", "详尽", "更多细节",
        ]
        for kw in detailed_keywords:
            if kw in text_lower:
                return "detailed"
        
        return None
    
    def _format_history(self, history: List[Message]) -> str:
        """格式化历史对话"""
        if not history:
            return ""
        
        lines = []
        for msg in history[-6:]:  # 最近 6 轮
            role_name = {"user": "用户", "assistant": "助手"}.get(msg.role, msg.role)
            content_preview = msg.content[:200] if msg.content else ""
            lines.append(f"{role_name}: {content_preview}")
        
        return "\n".join(lines)
    
    def _format_sources(self, sources: List[Source]) -> str:
        """格式化检索源"""
        if not sources:
            return ""
        
        lines = ["参考来源："]
        for i, src in enumerate(sources[:5], 1):
            lines.append(f"[{i}] {src.title or src.doc_name} - {src.snippet[:100]}...")
        
        return "\n".join(lines)
    
    def _parse_json_response(self, response: str, model_class: type) -> Optional[Any]:
        """解析 LLM 返回的 JSON"""
        # 清理 markdown 代码块
        cleaned = response.strip()
        
        # 移除可能的 ```json ... ``` 包装
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # 移除首尾的 ```
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)
        
        # 尝试解析 JSON
        try:
            data = json.loads(cleaned)
            if model_class == dict:
                return data
            return model_class(**data)
        except json.JSONDecodeError as exc:
            logger.warning(f"JSON parse error: {exc}")
            # 尝试提取 JSON 部分
            json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(0))
                    if model_class == dict:
                        return data
                    return model_class(**data)
                except Exception:
                    pass
            return None
        except Exception as exc:
            logger.warning(f"Model parse error: {exc}")
            return None
    
    def _build_default_requirements(
        self,
        user_message: str,
        detail_level: str,
    ) -> RequirementJSON:
        """构建默认需求（解析失败时的兜底）"""
        return RequirementJSON(
            intent=IntentType.INFORMATION,
            goal=user_message[:100],
            constraints=[],
            preferences=[],
            assumptions=["基于通用场景和最佳实践给出建议"],
            success_criteria=["提供清晰可操作的答案"],
            clarification_questions=[],
            detail_level=DetailLevel(detail_level),
            blueprint_modules=["align_summary", "core_answer", "next_steps"],
        )
    
    def _get_default_blueprint(self, intent: IntentType) -> List[str]:
        """根据意图获取默认蓝图"""
        return INTENT_BLUEPRINTS.get(
            intent,
            ["align_summary", "core_answer", "next_steps"],
        )
    
    def _parse_sections_from_markdown(
        self,
        answer: str,
        blueprint_modules: List[str],
    ) -> List[ChatSection]:
        """从 Markdown 文本中解析 sections"""
        sections: List[ChatSection] = []
        
        # 按 ## 标题分割
        parts = re.split(r'\n## ', answer)
        
        # 第一部分如果没有标题，可能是前言
        if parts and not parts[0].strip().startswith("#"):
            # 如果有内容，作为 align_summary
            content = parts[0].strip()
            if content:
                sections.append(ChatSection(
                    id="align_summary",
                    title="理解确认",
                    markdown=content,
                    collapsed=False,
                ))
            parts = parts[1:]
        
        # 解析其他部分
        for part in parts:
            lines = part.split("\n", 1)
            if not lines:
                continue
            
            title = lines[0].strip()
            content = lines[1].strip() if len(lines) > 1 else ""
            
            if not title or not content:
                continue
            
            # 尝试映射到标准模块 ID
            section_id = self._match_section_id(title, blueprint_modules)
            
            # 判断是否折叠
            collapsed = section_id not in ["align_summary", "core_answer"]
            
            sections.append(ChatSection(
                id=section_id,
                title=title,
                markdown=content,
                collapsed=collapsed,
            ))
        
        # 如果没有解析到 sections，返回单一模块
        if not sections:
            sections.append(ChatSection(
                id="core_answer",
                title="答案",
                markdown=answer,
                collapsed=False,
            ))
        
        return sections
    
    def _match_section_id(self, title: str, blueprint_modules: List[str]) -> str:
        """将标题映射到标准模块 ID"""
        title_lower = title.lower()
        
        # 精确匹配
        for module_id, module_title in MODULE_TITLES.items():
            if module_title in title or title in module_title:
                return module_id
        
        # 关键词匹配
        keyword_map = {
            "理解": "align_summary",
            "确认": "align_summary",
            "核心": "core_answer",
            "答案": "core_answer",
            "时间": "timeline",
            "概念": "concepts",
            "争议": "controversy",
            "例子": "examples",
            "案例": "examples",
            "对比": "comparison",
            "检查": "checklist",
            "步骤": "steps",
            "陷阱": "pitfalls",
            "风险": "pitfalls",
            "下一步": "next_steps",
            "建议": "next_steps",
            "来源": "sources",
            "参考": "sources",
            "核对": "verification",
            "替代": "alternatives",
            "前置": "prerequisites",
            "大纲": "outline",
        }
        
        for keyword, module_id in keyword_map.items():
            if keyword in title:
                return module_id
        
        # 如果在蓝图中找到，使用蓝图的第一个未用 ID
        for module_id in blueprint_modules:
            if not any(s.id == module_id for s in []):  # 简化逻辑
                return module_id
        
        # 默认返回生成的 ID
        return f"section_{len(title)}"

