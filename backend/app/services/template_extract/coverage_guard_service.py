"""
覆盖率Guard服务 - 避免"只抽到几条"
自动判断状态和触发增强重试
"""
from __future__ import annotations

import logging
from typing import List

from app.config.template_extract_config import TemplateExtractConfig, get_template_extract_config
from app.schemas.template_extract import (
    DocumentBlock,
    TemplateEvidenceDTO,
    TemplateExtractStatus,
    TemplateKind,
    TemplateSpanDTO,
)

logger = logging.getLogger(__name__)


class TemplateCoverageGuard:
    """覆盖率守护服务"""
    
    def __init__(self, config: TemplateExtractConfig | None = None):
        """
        初始化服务
        
        Args:
            config: 配置
        """
        self.config = config or get_template_extract_config()
    
    def evaluate_coverage(
        self,
        templates: List[TemplateSpanDTO],
        evidences: List[TemplateEvidenceDTO],
        blocks: List[DocumentBlock],
    ) -> tuple[TemplateExtractStatus, float, List[TemplateKind], str]:
        """
        评估覆盖率，确定状态
        
        Args:
            templates: 抽取的模板列表
            evidences: 证据列表
            blocks: 全文块列表
            
        Returns:
            (status, coverage_ratio, missing_kinds, message)
        """
        # 1. 如果没有抽到任何模板
        if not templates:
            return self._evaluate_no_templates(evidences, blocks)
        
        # 2. 计算覆盖率
        expected_kinds = self._get_expected_kinds()
        found_kinds = set(t.kind for t in templates)
        covered_kinds = expected_kinds & found_kinds
        coverage_ratio = len(covered_kinds) / len(expected_kinds) if expected_kinds else 1.0
        
        missing_kinds = list(expected_kinds - found_kinds)
        
        logger.info(f"覆盖率: {coverage_ratio:.2%}, 期望{len(expected_kinds)}个，找到{len(found_kinds)}个")
        
        # 3. 判断状态
        if coverage_ratio >= self.config.coverage_min_ratio:
            return (
                TemplateExtractStatus.SUCCESS,
                coverage_ratio,
                missing_kinds,
                f"成功抽取{len(templates)}个范本，覆盖率{coverage_ratio:.1%}"
            )
        else:
            return (
                TemplateExtractStatus.LOW_COVERAGE,
                coverage_ratio,
                missing_kinds,
                f"覆盖率不足（{coverage_ratio:.1%}），缺少：{', '.join([k.value for k in missing_kinds][:3])}"
            )
    
    def _evaluate_no_templates(
        self,
        evidences: List[TemplateEvidenceDTO],
        blocks: List[DocumentBlock],
    ) -> tuple[TemplateExtractStatus, float, List[TemplateKind], str]:
        """
        评估没有抽到模板的情况
        
        Args:
            evidences: 证据列表
            blocks: 全文块列表
            
        Returns:
            (status, coverage_ratio, missing_kinds, message)
        """
        # 如果连证据都没有
        if not evidences:
            expected_kinds = self._get_expected_kinds()
            return (
                TemplateExtractStatus.NOT_FOUND,
                0.0,
                list(expected_kinds),
                "未找到任何范本块，文档可能不包含格式要求"
            )
        
        # 有证据但没抽到，判断原因
        
        # 1. 计算文本密度
        text_density = self._calculate_text_density(blocks)
        
        # 2. 统计图片锚点
        image_anchor_count = sum(
            1 for e in evidences
            if e.type.value == "IMAGE_ANCHOR"
        )
        
        # 判断是否需要OCR
        if self.config.image_anchor_hit_to_need_ocr and image_anchor_count > 5:
            expected_kinds = self._get_expected_kinds()
            return (
                TemplateExtractStatus.NEED_OCR,
                0.0,
                list(expected_kinds),
                f"检测到{image_anchor_count}个图片锚点，疑似扫描版范本，建议开启OCR"
            )
        
        if text_density < self.config.low_text_density_threshold:
            expected_kinds = self._get_expected_kinds()
            return (
                TemplateExtractStatus.NEED_OCR,
                0.0,
                list(expected_kinds),
                f"文本密度过低（{text_density:.3f}），疑似图片/扫描文档"
            )
        
        # 否则需要人工确认
        expected_kinds = self._get_expected_kinds()
        return (
            TemplateExtractStatus.NEED_CONFIRM,
            0.0,
            list(expected_kinds),
            f"找到{len(evidences)}个证据但无法确定边界，建议从证据列表中手动确认起点"
        )
    
    def _get_expected_kinds(self) -> set[TemplateKind]:
        """获取期望覆盖的范本类型"""
        expected = set()
        for kind_str in self.config.coverage_expected_kinds:
            try:
                expected.add(TemplateKind(kind_str))
            except ValueError:
                logger.warning(f"无效的期望kind: {kind_str}")
        return expected
    
    def _calculate_text_density(self, blocks: List[DocumentBlock]) -> float:
        """
        计算文本密度
        
        Args:
            blocks: 块列表
            
        Returns:
            文本密度（0~1）
        """
        if not blocks:
            return 0.0
        
        # 统计有文本的块
        text_blocks = 0
        total_chars = 0
        
        for block in blocks:
            text = (block.text or "").strip()
            if text:
                text_blocks += 1
                total_chars += len(text)
        
        # 文本密度 = 有文本的块比例 * 平均长度因子
        block_ratio = text_blocks / len(blocks)
        avg_chars = total_chars / text_blocks if text_blocks > 0 else 0
        char_factor = min(1.0, avg_chars / 100)  # 假设100字为"正常"
        
        density = block_ratio * char_factor
        
        return density
    
    def should_retry_enhanced(
        self,
        status: TemplateExtractStatus,
        coverage_ratio: float,
    ) -> bool:
        """
        判断是否应该触发增强重试
        
        Args:
            status: 当前状态
            coverage_ratio: 覆盖率
            
        Returns:
            是否应该重试
        """
        # 只在LOW_COVERAGE时触发增强重试
        if status == TemplateExtractStatus.LOW_COVERAGE:
            return True
        
        return False

