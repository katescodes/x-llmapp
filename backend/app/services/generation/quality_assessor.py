"""
统一的质量评估器
评估生成内容的质量
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List
from dataclasses import dataclass

from .content_generator import GenerationResult
from .document_retriever import RetrievalResult

logger = logging.getLogger(__name__)


@dataclass
class QualityMetrics:
    """质量指标"""
    overall_score: float  # 总体评分 (0-1)
    completeness_score: float  # 完整度 (0-1)
    evidence_score: float  # 证据充分度 (0-1)
    format_score: float  # 格式规范度 (0-1)
    
    # 详细指标
    word_count: int
    has_placeholder: bool
    confidence_level: str
    evidence_count: int
    
    # 问题列表
    issues: List[str]
    
    def get_grade(self) -> str:
        """获取等级评价"""
        if self.overall_score >= 0.9:
            return "优秀"
        elif self.overall_score >= 0.75:
            return "良好"
        elif self.overall_score >= 0.6:
            return "合格"
        else:
            return "待改进"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "overall_score": round(self.overall_score, 2),
            "completeness_score": round(self.completeness_score, 2),
            "evidence_score": round(self.evidence_score, 2),
            "format_score": round(self.format_score, 2),
            "word_count": self.word_count,
            "has_placeholder": self.has_placeholder,
            "confidence_level": self.confidence_level,
            "evidence_count": self.evidence_count,
            "grade": self.get_grade(),
            "issues": self.issues
        }


class QualityAssessor:
    """
    统一的质量评估器
    
    功能：
    1. 评估内容完整度
    2. 评估证据充分度
    3. 评估格式规范度
    4. 生成质量报告
    """
    
    # 评分权重
    WEIGHTS = {
        "completeness": 0.4,  # 完整度权重
        "evidence": 0.3,      # 证据权重
        "format": 0.3         # 格式权重
    }
    
    def assess(
        self,
        generation_result: GenerationResult,
        retrieval_result: RetrievalResult,
        section_level: int
    ) -> QualityMetrics:
        """
        评估生成内容质量
        
        Args:
            generation_result: 生成结果
            retrieval_result: 检索结果
            section_level: 章节层级
            
        Returns:
            质量指标
        """
        issues = []
        
        # 1. 评估完整度
        completeness_score = self._assess_completeness(
            generation_result,
            section_level,
            issues
        )
        
        # 2. 评估证据充分度
        evidence_score = self._assess_evidence(
            retrieval_result,
            issues
        )
        
        # 3. 评估格式规范度
        format_score = self._assess_format(
            generation_result,
            issues
        )
        
        # 4. 计算总体评分
        overall_score = (
            completeness_score * self.WEIGHTS["completeness"] +
            evidence_score * self.WEIGHTS["evidence"] +
            format_score * self.WEIGHTS["format"]
        )
        
        metrics = QualityMetrics(
            overall_score=overall_score,
            completeness_score=completeness_score,
            evidence_score=evidence_score,
            format_score=format_score,
            word_count=generation_result.word_count,
            has_placeholder=generation_result.has_placeholder,
            confidence_level=generation_result.confidence,
            evidence_count=len(retrieval_result.chunks),
            issues=issues
        )
        
        logger.info(
            f"[QualityAssessor] 质量评估: "
            f"总分={overall_score:.2f}, "
            f"等级={metrics.get_grade()}, "
            f"问题数={len(issues)}"
        )
        
        return metrics
    
    def _assess_completeness(
        self,
        result: GenerationResult,
        section_level: int,
        issues: List[str]
    ) -> float:
        """评估完整度"""
        score = 1.0
        
        # 最小字数要求
        min_words_map = {1: 800, 2: 500, 3: 300, 4: 200}
        min_words = min_words_map.get(section_level, 200)
        
        # 字数不足扣分
        if result.word_count < min_words * 0.5:
            score -= 0.5
            issues.append(f"内容过短（{result.word_count}字，建议至少{min_words}字）")
        elif result.word_count < min_words * 0.8:
            score -= 0.2
            issues.append(f"内容略短（{result.word_count}字，建议{min_words}字以上）")
        
        # 有待补充标记扣分
        if result.has_placeholder:
            score -= 0.3
            issues.append("内容包含【待补充】标记，需要用户补充信息")
        
        # 置信度影响
        if result.confidence == "LOW":
            score -= 0.2
            issues.append("内容置信度较低，可能缺乏充分依据")
        elif result.confidence == "MEDIUM":
            score -= 0.1
        
        return max(score, 0.0)
    
    def _assess_evidence(
        self,
        retrieval_result: RetrievalResult,
        issues: List[str]
    ) -> float:
        """评估证据充分度"""
        score = 1.0
        
        # 没有检索到资料
        if not retrieval_result.has_relevant:
            score = 0.3
            issues.append("未检索到相关企业/用户资料，内容缺乏实际依据")
            return score
        
        # 检索质量影响分数
        quality = retrieval_result.quality_score
        score = quality
        
        # 资料数量
        chunk_count = len(retrieval_result.chunks)
        if chunk_count < 2:
            score -= 0.2
            issues.append("相关资料较少，建议补充更多支撑材料")
        
        return max(score, 0.0)
    
    def _assess_format(
        self,
        result: GenerationResult,
        issues: List[str]
    ) -> float:
        """评估格式规范度"""
        score = 1.0
        content = result.content
        
        if result.format_type == "html":
            # HTML格式检查
            if not any(tag in content for tag in ["<p>", "<ul>", "<div>", "<h"]):
                score -= 0.5
                issues.append("HTML格式不规范，缺少基本标签")
            
            # 检查标签是否闭合
            if content.count("<p>") != content.count("</p>"):
                score -= 0.2
                issues.append("HTML标签未正确闭合")
        
        elif result.format_type == "markdown":
            # Markdown格式检查
            # 检查是否有基本的段落结构
            if "\n\n" not in content and len(content) > 200:
                score -= 0.3
                issues.append("Markdown格式需要更好的段落划分")
        
        # 检查是否有明显的格式错误
        if "```" in content:
            score -= 0.2
            issues.append("内容包含未清理的代码块标记")
        
        return max(score, 0.0)

