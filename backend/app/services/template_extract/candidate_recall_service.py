"""
候选召回服务 - 规则召回（不依赖标题样式）
使用关键词匹配、表格特征等规则召回候选窗口
"""
from __future__ import annotations

import logging
import re
from typing import List, Tuple

from app.config.template_extract_config import TemplateExtractConfig, get_template_extract_config
from app.schemas.template_extract import CandidateWindow, DocumentBlock, TemplateEvidenceDTO, EvidenceType

logger = logging.getLogger(__name__)


class TemplateCandidateRecallService:
    """候选召回服务（规则/便宜/高召回）"""
    
    def __init__(self, config: TemplateExtractConfig | None = None):
        """
        初始化服务
        
        Args:
            config: 配置，如果为None则使用默认配置
        """
        self.config = config or get_template_extract_config()
    
    def recall(
        self,
        blocks: List[DocumentBlock],
        mode: str = "NORMAL",
    ) -> Tuple[List[CandidateWindow], List[TemplateEvidenceDTO]]:
        """
        召回候选窗口和证据
        
        Args:
            blocks: 文档块列表
            mode: 召回模式 NORMAL/ENHANCED
            
        Returns:
            (windows, evidences) 窗口列表和证据列表
        """
        logger.info(f"开始召回候选窗口，mode={mode}, blocks数量={len(blocks)}")
        
        # 1. 为每个block计算evidence score
        block_scores = self._calculate_block_scores(blocks)
        
        # 2. 根据模式选择阈值
        if mode == "ENHANCED":
            min_score = self.config.enhanced_min_evidence_score
            window_radius = self.config.enhanced_window_radius
            max_windows = self.config.enhanced_max_windows
        else:
            min_score = self.config.min_evidence_score
            window_radius = self.config.window_radius
            max_windows = self.config.max_windows
        
        # 3. 找出锚点（score >= min_score）
        anchors = []
        for i, (block, score, hits) in enumerate(block_scores):
            if score >= min_score:
                anchors.append((i, block.block_id, score, hits))
        
        logger.info(f"找到 {len(anchors)} 个锚点（阈值={min_score}）")
        
        # 4. 为每个锚点创建窗口
        raw_windows = []
        for anchor_idx, block_id, score, hits in anchors:
            start_idx = max(0, anchor_idx - window_radius)
            end_idx = min(len(blocks) - 1, anchor_idx + window_radius)
            
            raw_windows.append(CandidateWindow(
                start_idx=start_idx,
                end_idx=end_idx,
                score=score,
                hit_blocks=[block_id],
                anchor_block_id=block_id,
            ))
        
        # 5. 合并重叠窗口
        merged_windows = self._merge_overlapping_windows(raw_windows)
        
        # 6. 按得分排序，取top N
        merged_windows.sort(key=lambda w: w.score, reverse=True)
        top_windows = merged_windows[:max_windows]
        
        logger.info(f"合并后窗口数={len(merged_windows)}，取top {len(top_windows)}")
        
        # 7. 生成证据列表（用于UI展示）
        evidences = self._generate_evidences(block_scores, blocks)
        
        return top_windows, evidences
    
    def _calculate_block_scores(
        self,
        blocks: List[DocumentBlock],
    ) -> List[Tuple[DocumentBlock, float, List[str]]]:
        """
        计算每个block的evidence score
        
        Returns:
            List of (block, score, keywords_hit)
        """
        results = []
        
        for block in blocks:
            text = block.text or ""
            text_lower = text.lower()
            
            score = 0.0
            keywords_hit = []
            
            # 1. 强词命中：+0.2每个，最多+0.6
            strong_hits = 0
            for kw in self.config.strong_keywords:
                if kw in text:
                    strong_hits += 1
                    keywords_hit.append(kw)
                    if strong_hits >= 3:
                        break
            score += min(strong_hits * 0.2, 0.6)
            
            # 2. 弱词命中：最多+0.2
            weak_hits = 0
            for kw in self.config.weak_keywords:
                if kw in text:
                    weak_hits += 1
                    keywords_hit.append(kw)
                    if weak_hits >= 1:
                        break
            score += min(weak_hits * 0.2, 0.2)
            
            # 3. 签章/占位特征：+0.15
            signature_hit = False
            for kw in self.config.signature_keywords:
                if kw in text:
                    signature_hit = True
                    keywords_hit.append(kw)
                    break
            if signature_hit:
                score += 0.15
            
            # 4. 表格密集特征：+0.1
            is_table = block.block_type == "TABLE_CELL"
            has_separator = any(sep in text for sep in ["│", "|", "：", ":", "\t"])
            if is_table or has_separator:
                score += 0.1
            
            # 5. "附表/表X/格式/样表/模板"组合命中：额外+0.2
            marker_hit_count = 0
            for kw in self.config.template_marker_keywords:
                if kw in text:
                    marker_hit_count += 1
            if marker_hit_count >= 2:
                score += 0.2
            
            results.append((block, score, keywords_hit))
        
        return results
    
    def _merge_overlapping_windows(
        self,
        windows: List[CandidateWindow],
    ) -> List[CandidateWindow]:
        """
        合并重叠窗口
        
        Args:
            windows: 原始窗口列表
            
        Returns:
            合并后的窗口列表
        """
        if not windows:
            return []
        
        # 按起始位置排序
        sorted_windows = sorted(windows, key=lambda w: w.start_idx)
        
        merged = []
        current = sorted_windows[0]
        
        for next_window in sorted_windows[1:]:
            # 检查是否重叠（允许一定间隙）
            if next_window.start_idx <= current.end_idx + 5:
                # 合并
                current = CandidateWindow(
                    start_idx=current.start_idx,
                    end_idx=max(current.end_idx, next_window.end_idx),
                    score=max(current.score, next_window.score),
                    hit_blocks=list(set(current.hit_blocks + next_window.hit_blocks)),
                    anchor_block_id=current.anchor_block_id,
                )
            else:
                # 不重叠，保存当前，开始新窗口
                merged.append(current)
                current = next_window
        
        # 添加最后一个窗口
        merged.append(current)
        
        return merged
    
    def _generate_evidences(
        self,
        block_scores: List[Tuple[DocumentBlock, float, List[str]]],
        blocks: List[DocumentBlock],
    ) -> List[TemplateEvidenceDTO]:
        """
        生成证据列表（用于UI展示）
        
        Args:
            block_scores: 块得分列表
            blocks: 原始块列表
            
        Returns:
            证据列表
        """
        evidences = []
        
        # 按得分排序
        sorted_scores = sorted(block_scores, key=lambda x: x[1], reverse=True)
        
        # 取top N
        top_scores = sorted_scores[:self.config.top_evidences_count]
        
        for block, score, keywords_hit in top_scores:
            if score < 0.3:  # 过滤太低的
                continue
            
            # 确定证据类型
            evidence_type = self._infer_evidence_type(block)
            
            # 生成snippet（200-400字）
            text = block.text or ""
            snippet = text[:400] if len(text) > 400 else text
            
            # 生成reason
            reason = self._generate_evidence_reason(score, keywords_hit, block)
            
            evidences.append(TemplateEvidenceDTO(
                type=evidence_type,
                block_id=block.block_id,
                order_no=block.order_no,
                score=round(score, 2),
                keywords_hit=keywords_hit[:5],  # 最多显示5个关键词
                snippet=snippet,
                reason=reason,
            ))
        
        return evidences
    
    def _infer_evidence_type(self, block: DocumentBlock) -> EvidenceType:
        """推断证据类型"""
        block_type = block.block_type or ""
        
        if "TABLE" in block_type.upper():
            return EvidenceType.TABLE_CELL
        elif "IMAGE" in block_type.upper():
            return EvidenceType.IMAGE_ANCHOR
        elif "TEXTBOX" in block_type.upper():
            return EvidenceType.TEXTBOX
        else:
            return EvidenceType.PARAGRAPH
    
    def _generate_evidence_reason(
        self,
        score: float,
        keywords_hit: List[str],
        block: DocumentBlock,
    ) -> str:
        """生成证据命中原因"""
        reasons = []
        
        if keywords_hit:
            reasons.append(f"命中关键词：{', '.join(keywords_hit[:3])}")
        
        if block.block_type == "TABLE_CELL":
            reasons.append("表格密集区域")
        
        if score >= 0.8:
            reasons.append("高置信度匹配")
        elif score >= 0.65:
            reasons.append("中等置信度匹配")
        
        return "；".join(reasons) if reasons else "疑似范本区域"

