"""
模板抽取总编排服务
协调召回、LLM分析、边界细化、覆盖率guard等所有环节
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Dict, List, Optional

from app.config.template_extract_config import TemplateExtractConfig, get_template_extract_config
from app.schemas.template_extract import (
    DocumentBlock,
    ExtractMode,
    TemplateExtractDiagnostics,
    TemplateExtractResultDTO,
    TemplateExtractStatus,
    TemplateSpanDTO,
)
from app.services.template_extract.candidate_recall_service import TemplateCandidateRecallService
from app.services.template_extract.coverage_guard_service import TemplateCoverageGuard
from app.services.template_extract.llm_span_service import LlmTemplateSpanService
from app.services.template_extract.span_refiner_service import TemplateSpanRefiner

logger = logging.getLogger(__name__)


class TemplateExtractOrchestrator:
    """模板抽取总编排服务"""
    
    def __init__(
        self,
        llm_orchestrator: Any = None,
        config: TemplateExtractConfig | None = None,
    ):
        """
        初始化服务
        
        Args:
            llm_orchestrator: LLM编排器
            config: 配置
        """
        self.llm = llm_orchestrator
        self.config = config or get_template_extract_config()
        
        # 初始化子服务
        self.recall_service = TemplateCandidateRecallService(self.config)
        self.llm_service = LlmTemplateSpanService(self.llm, self.config)
        self.refiner_service = TemplateSpanRefiner(self.config)
        self.coverage_guard = TemplateCoverageGuard(self.config)
        
        # LLM调用缓存（window hash -> result）
        self._llm_cache: Dict[str, Any] = {}
    
    def extract(
        self,
        blocks: List[DocumentBlock],
        mode: str = "NORMAL",
    ) -> TemplateExtractResultDTO:
        """
        执行模板抽取
        
        Args:
            blocks: 文档块列表
            mode: 抽取模式 NORMAL/ENHANCED
            
        Returns:
            抽取结果
        """
        start_time = time.time()
        
        logger.info(f"开始模板抽取，mode={mode}, blocks数量={len(blocks)}")
        
        try:
            # 1. 候选召回
            windows, evidences = self.recall_service.recall(blocks, mode=mode)
            
            logger.info(f"召回窗口数={len(windows)}, 证据数={len(evidences)}")
            
            # 2. LLM分析窗口（并发限制）
            llm_results = self._analyze_windows_with_llm(windows, blocks)
            
            logger.info(f"LLM分析结果数={len(llm_results)}")
            
            # 3. 边界细化
            block_scores = self._build_block_scores(evidences)
            refined_spans = self._refine_spans(llm_results, blocks, block_scores)
            
            logger.info(f"细化后span数={len(refined_spans)}")
            
            # 4. 去重合并
            merged_spans = self._merge_duplicate_spans(refined_spans)
            
            logger.info(f"去重后span数={len(merged_spans)}")
            
            # 5. 覆盖率评估
            status, coverage_ratio, missing_kinds, message = self.coverage_guard.evaluate_coverage(
                templates=merged_spans,
                evidences=evidences,
                blocks=blocks,
            )
            
            # 6. 判断是否需要增强重试（只重试一次）
            if mode == "NORMAL" and self.coverage_guard.should_retry_enhanced(status, coverage_ratio):
                logger.info("覆盖率不足，触发增强重试")
                return self.extract(blocks, mode="ENHANCED")
            
            # 7. 生成诊断信息
            elapsed_ms = int((time.time() - start_time) * 1000)
            diagnostics = self._build_diagnostics(
                blocks=blocks,
                windows=windows,
                evidences=evidences,
                llm_results=llm_results,
                templates=merged_spans,
                coverage_ratio=coverage_ratio,
                missing_kinds=missing_kinds,
                elapsed_ms=elapsed_ms,
            )
            
            # 8. 返回结果
            return TemplateExtractResultDTO(
                status=status,
                templates=merged_spans,
                evidences=evidences,
                diagnostics=diagnostics,
                message=message,
            )
            
        except Exception as e:
            logger.error(f"模板抽取失败: {e}", exc_info=True)
            
            # 返回失败结果
            elapsed_ms = int((time.time() - start_time) * 1000)
            return TemplateExtractResultDTO(
                status=TemplateExtractStatus.NOT_FOUND,
                templates=[],
                evidences=[],
                diagnostics=TemplateExtractDiagnostics(
                    recall_hit_count=0,
                    window_count=0,
                    llm_call_count=0,
                    coverage_ratio=0.0,
                    missing_kinds=[],
                    total_blocks=len(blocks),
                    text_density=0.0,
                    image_anchor_count=0,
                    extraction_time_ms=elapsed_ms,
                ),
                message=f"抽取失败: {str(e)}",
            )
    
    def _analyze_windows_with_llm(
        self,
        windows: List[Any],
        blocks: List[DocumentBlock],
    ) -> List[Any]:
        """
        使用LLM分析窗口（带缓存和并发控制）
        
        Args:
            windows: 窗口列表
            blocks: 全文块列表
            
        Returns:
            LLM分析结果列表
        """
        results = []
        
        # 构建block索引
        block_map = {b.block_id: b for b in blocks}
        
        for window in windows:
            # 提取窗口块
            window_blocks = blocks[window.start_idx:window.end_idx+1]
            
            # 计算窗口hash（用于缓存）
            window_hash = self._hash_window(window_blocks)
            
            # 检查缓存
            if window_hash in self._llm_cache:
                logger.debug(f"使用缓存的LLM结果: {window_hash}")
                result = self._llm_cache[window_hash]
            else:
                # 调用LLM
                result = self.llm_service.analyze_window(window_blocks)
                
                # 缓存结果
                if result:
                    self._llm_cache[window_hash] = result
            
            if result and result.is_template:
                results.append(result)
        
        return results
    
    def _hash_window(self, window_blocks: List[DocumentBlock]) -> str:
        """计算窗口hash（用于缓存）"""
        content = "".join([f"{b.block_id}:{b.text[:100]}" for b in window_blocks])
        return hashlib.md5(content.encode()).hexdigest()
    
    def _build_block_scores(self, evidences: List[Any]) -> Dict[str, float]:
        """构建块得分字典"""
        scores = {}
        for evidence in evidences:
            scores[evidence.block_id] = evidence.score
        return scores
    
    def _refine_spans(
        self,
        llm_results: List[Any],
        blocks: List[DocumentBlock],
        block_scores: Dict[str, float],
    ) -> List[TemplateSpanDTO]:
        """
        细化所有span
        
        Args:
            llm_results: LLM分析结果
            blocks: 全文块列表
            block_scores: 块得分字典
            
        Returns:
            细化后的span列表
        """
        refined = []
        
        for llm_result in llm_results:
            # 细化边界
            span = self.refiner_service.refine_span(
                llm_result=llm_result,
                window_blocks=[],  # refiner不需要window_blocks
                all_blocks=blocks,
                block_scores=block_scores,
            )
            
            if span:
                refined.append(span)
        
        return refined
    
    def _merge_duplicate_spans(
        self,
        spans: List[TemplateSpanDTO],
    ) -> List[TemplateSpanDTO]:
        """
        去重合并span（同kind、重叠>60%合并，保留高confidence）
        
        Args:
            spans: span列表
            
        Returns:
            合并后的span列表
        """
        if not spans:
            return []
        
        # 按kind分组
        by_kind: Dict[str, List[TemplateSpanDTO]] = {}
        for span in spans:
            kind_key = span.kind.value
            if kind_key not in by_kind:
                by_kind[kind_key] = []
            by_kind[kind_key].append(span)
        
        # 对每个kind组内去重
        merged = []
        for kind_key, kind_spans in by_kind.items():
            # 按confidence排序
            sorted_spans = sorted(kind_spans, key=lambda s: s.confidence, reverse=True)
            
            kept = []
            for span in sorted_spans:
                # 检查是否与已保留的span重叠
                should_keep = True
                for kept_span in kept:
                    if self._spans_overlap(span, kept_span, threshold=0.6):
                        # 重叠超过60%，不保留
                        should_keep = False
                        break
                
                if should_keep:
                    kept.append(span)
            
            merged.extend(kept)
        
        return merged
    
    def _spans_overlap(
        self,
        span1: TemplateSpanDTO,
        span2: TemplateSpanDTO,
        threshold: float = 0.6,
    ) -> bool:
        """
        判断两个span是否重叠超过阈值
        
        Args:
            span1: span1
            span2: span2
            threshold: 重叠阈值
            
        Returns:
            是否重叠
        """
        # 简化判断：如果start或end相同，认为重叠
        # 更精确的方法需要计算block范围重叠度
        if span1.start_block_id == span2.start_block_id:
            return True
        if span1.end_block_id == span2.end_block_id:
            return True
        
        return False
    
    def _build_diagnostics(
        self,
        blocks: List[DocumentBlock],
        windows: List[Any],
        evidences: List[Any],
        llm_results: List[Any],
        templates: List[TemplateSpanDTO],
        coverage_ratio: float,
        missing_kinds: List[Any],
        elapsed_ms: int,
    ) -> TemplateExtractDiagnostics:
        """构建诊断信息"""
        # 计算文本密度
        text_density = self.coverage_guard._calculate_text_density(blocks)
        
        # 统计图片锚点
        image_anchor_count = sum(
            1 for e in evidences
            if e.type.value == "IMAGE_ANCHOR"
        )
        
        return TemplateExtractDiagnostics(
            recall_hit_count=len(evidences),
            window_count=len(windows),
            llm_call_count=len(llm_results),
            coverage_ratio=coverage_ratio,
            missing_kinds=missing_kinds,
            total_blocks=len(blocks),
            text_density=text_density,
            image_anchor_count=image_anchor_count,
            extraction_time_ms=elapsed_ms,
        )

