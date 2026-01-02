"""
统一的内容生成器
支持Tender和Declare两种场景的内容生成
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from .prompt_builder import PromptOutput

logger = logging.getLogger(__name__)


@dataclass
class GenerationContext:
    """生成上下文"""
    document_type: str  # 'tender' or 'declare'
    section_title: str
    prompt: PromptOutput
    model_id: Optional[str] = None


@dataclass
class GenerationResult:
    """生成结果"""
    content: str
    raw_content: str  # 原始LLM输出
    confidence: str  # 'HIGH', 'MEDIUM', 'LOW'
    word_count: int
    has_placeholder: bool  # 是否包含待补充标记
    format_type: str  # 'html' or 'markdown'
    
    def get_quality_indicator(self) -> Dict[str, Any]:
        """获取质量指标"""
        return {
            "confidence": self.confidence,
            "word_count": self.word_count,
            "has_placeholder": self.has_placeholder,
            "completeness_score": self._calculate_completeness()
        }
    
    def _calculate_completeness(self) -> float:
        """计算完整度评分 (0-1)"""
        score = 1.0
        
        # 有待补充标记扣分
        if self.has_placeholder:
            score -= 0.3
        
        # 字数不足扣分
        if self.word_count < 100:
            score -= 0.4
        elif self.word_count < 200:
            score -= 0.2
        
        # 置信度影响
        if self.confidence == "LOW":
            score -= 0.2
        elif self.confidence == "MEDIUM":
            score -= 0.1
        
        return max(score, 0.0)


class ContentGenerator:
    """
    统一的内容生成器
    
    功能：
    1. 调用LLM生成内容
    2. 清理和格式化输出
    3. 提取置信度等元信息
    4. 统一HTML/Markdown格式处理
    """
    
    def __init__(self, llm_orchestrator):
        """
        初始化生成器
        
        Args:
            llm_orchestrator: LLM编排器实例
        """
        self.llm = llm_orchestrator
    
    async def generate(self, context: GenerationContext) -> GenerationResult:
        """
        生成内容
        
        Args:
            context: 生成上下文
            
        Returns:
            生成结果
        """
        try:
            # Step 1: 调用LLM
            raw_content = await self._call_llm(context)
            
            # Step 2: 提取元信息
            confidence = self._extract_confidence(raw_content)
            
            # Step 3: 清理和格式化
            if context.document_type == "tender":
                content = self._format_html_content(raw_content)
                format_type = "html"
            else:
                content = self._format_markdown_content(raw_content)
                format_type = "markdown"
            
            # Step 4: 计算指标
            word_count = len(content)
            has_placeholder = self._has_placeholder(content)
            
            result = GenerationResult(
                content=content,
                raw_content=raw_content,
                confidence=confidence,
                word_count=word_count,
                has_placeholder=has_placeholder,
                format_type=format_type
            )
            
            logger.info(
                f"[ContentGenerator] 生成完成: "
                f"type={context.document_type}, "
                f"section={context.section_title}, "
                f"words={word_count}, "
                f"confidence={confidence}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"[ContentGenerator] 生成失败: {e}", exc_info=True)
            raise
    
    async def _call_llm(self, context: GenerationContext) -> str:
        """调用LLM"""
        if not self.llm:
            raise ValueError("LLM orchestrator 未初始化")
        
        messages = [
            {"role": "system", "content": context.prompt.system_prompt},
            {"role": "user", "content": context.prompt.user_prompt}
        ]
        
        response = await self.llm.achat(
            messages=messages,
            model_id=context.model_id,
            temperature=context.prompt.temperature,
            max_tokens=context.prompt.max_tokens,
        )
        
        # 提取文本内容
        if isinstance(response, dict) and "choices" in response:
            content = response["choices"][0]["message"]["content"]
        elif isinstance(response, str):
            content = response
        else:
            content = str(response)
        
        return content.strip()
    
    def _extract_confidence(self, content: str) -> str:
        """提取置信度"""
        content_upper = content.upper()
        
        if "CONFIDENCE: HIGH" in content_upper or "置信度：HIGH" in content_upper:
            return "HIGH"
        elif "CONFIDENCE: MEDIUM" in content_upper or "置信度：MEDIUM" in content_upper:
            return "MEDIUM"
        elif "CONFIDENCE: LOW" in content_upper or "置信度：LOW" in content_upper:
            return "LOW"
        else:
            # 默认：如果没有待补充标记，认为是HIGH
            if not self._has_placeholder(content):
                return "HIGH"
            else:
                return "MEDIUM"
    
    def _has_placeholder(self, content: str) -> bool:
        """检查是否包含待补充标记"""
        placeholder_patterns = [
            r"【待补充】",
            r"\[待补充\]",
            r"待补充",
            r"TODO",
            r"TBD",
            r"PLACEHOLDER"
        ]
        
        for pattern in placeholder_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False
    
    def _format_html_content(self, raw_content: str) -> str:
        """格式化HTML内容"""
        content = raw_content.strip()
        
        # 移除代码块标记
        if content.startswith("```html"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        
        content = content.strip()
        
        # 确保内容是HTML格式
        if not ("<p>" in content or "<ul>" in content or "<div>" in content or "<h" in content):
            # 如果不是HTML，转换为HTML段落
            paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
            content = "\n".join([f"<p>{p}</p>" for p in paragraphs])
        
        return content
    
    def _format_markdown_content(self, raw_content: str) -> str:
        """格式化Markdown内容"""
        content = raw_content.strip()
        
        # 移除代码块标记
        if content.startswith("```markdown"):
            content = content[11:]
        elif content.startswith("```md"):
            content = content[5:]
        elif content.startswith("```"):
            content = content[3:]
        
        if content.endswith("```"):
            content = content[:-3]
        
        content = content.strip()
        
        # 移除置信度行（如果在末尾）
        lines = content.split("\n")
        if lines and ("置信度" in lines[-1] or "CONFIDENCE" in lines[-1].upper()):
            content = "\n".join(lines[:-1]).strip()
        
        return content

