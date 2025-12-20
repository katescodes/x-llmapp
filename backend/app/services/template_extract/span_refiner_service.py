"""
边界细化服务 - 终止规则（防吞章/防切短）
工程规则控制，不依赖LLM
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

from app.config.template_extract_config import TemplateExtractConfig, get_template_extract_config
from app.schemas.template_extract import DocumentBlock, LlmWindowResult, TemplateSpanDTO

logger = logging.getLogger(__name__)


class TemplateSpanRefiner:
    """范围细化服务"""
    
    def __init__(self, config: TemplateExtractConfig | None = None):
        """
        初始化服务
        
        Args:
            config: 配置
        """
        self.config = config or get_template_extract_config()
    
    def refine_span(
        self,
        llm_result: LlmWindowResult,
        window_blocks: List[DocumentBlock],
        all_blocks: List[DocumentBlock],
        block_scores: Optional[Dict[str, float]] = None,
    ) -> Optional[TemplateSpanDTO]:
        """
        细化范围边界
        
        Args:
            llm_result: LLM粗分析结果
            window_blocks: 窗口块列表
            all_blocks: 全文块列表
            block_scores: 块得分字典（block_id -> score）
            
        Returns:
            细化后的span，如果失败返回None
        """
        if not llm_result.is_template:
            return None
        
        if not llm_result.start_block_id or not llm_result.end_block_id:
            logger.warning("LLM结果缺少start/end block ID")
            return None
        
        # 构建block索引
        block_map = {b.block_id: (i, b) for i, b in enumerate(all_blocks)}
        
        if llm_result.start_block_id not in block_map or llm_result.end_block_id not in block_map:
            logger.warning("start/end block ID 在全文中找不到")
            return None
        
        start_idx, start_block = block_map[llm_result.start_block_id]
        end_idx, end_block = block_map[llm_result.end_block_id]
        
        # 1. 微调start（向前回看）
        refined_start_idx = self._refine_start(
            start_idx,
            all_blocks,
            block_map,
        )
        
        # 2. 微调end（终止规则）
        refined_end_idx = self._refine_end(
            refined_start_idx,
            end_idx,
            all_blocks,
            block_scores or {},
        )
        
        # 3. 验证范围
        if refined_end_idx <= refined_start_idx:
            logger.warning("细化后范围无效")
            return None
        
        # 4. 验证长度限制
        span_blocks = all_blocks[refined_start_idx:refined_end_idx+1]
        if len(span_blocks) > self.config.max_span_blocks:
            logger.warning(f"span超过最大块数限制：{len(span_blocks)} > {self.config.max_span_blocks}")
            # 强制截断
            refined_end_idx = refined_start_idx + self.config.max_span_blocks - 1
            span_blocks = all_blocks[refined_start_idx:refined_end_idx+1]
        
        total_chars = sum(len(b.text or "") for b in span_blocks)
        if total_chars > self.config.max_span_chars:
            logger.warning(f"span超过最大字符数限制：{total_chars} > {self.config.max_span_chars}")
            # 从end往回缩
            while total_chars > self.config.max_span_chars and refined_end_idx > refined_start_idx:
                refined_end_idx -= 1
                span_blocks = all_blocks[refined_start_idx:refined_end_idx+1]
                total_chars = sum(len(b.text or "") for b in span_blocks)
        
        # 5. 构建TemplateSpanDTO
        refined_start_block = all_blocks[refined_start_idx]
        refined_end_block = all_blocks[refined_end_idx]
        
        return TemplateSpanDTO(
            kind=llm_result.kind,
            display_title=llm_result.display_title or llm_result.kind.value,
            start_block_id=refined_start_block.block_id,
            end_block_id=refined_end_block.block_id,
            confidence=llm_result.confidence,
            evidence_block_ids=llm_result.evidence_block_ids,
            reason=llm_result.reason,
        )
    
    def _refine_start(
        self,
        start_idx: int,
        all_blocks: List[DocumentBlock],
        block_map: Dict[str, tuple],
    ) -> int:
        """
        微调开始位置（向前回看，寻找标题）
        
        Args:
            start_idx: 原始start索引
            all_blocks: 全文块列表
            block_map: 块索引映射
            
        Returns:
            细化后的start索引
        """
        # 向前回看N个块
        lookback = self.config.refine_lookback_blocks
        search_start = max(0, start_idx - lookback)
        
        # 定义标题型强词
        title_keywords = [
            "授权委托书", "投标函", "报价表", "偏离表",
            "承诺书", "格式", "样表", "范本", "模板",
            "附表", "业绩表", "人员表", "证书清单",
        ]
        
        best_idx = start_idx
        best_score = 0.0
        
        for i in range(search_start, start_idx):
            block = all_blocks[i]
            text = block.text or ""
            
            # 检查是否像标题：短文本 + 命中关键词
            if len(text) > 100:  # 太长不像标题
                continue
            
            score = 0.0
            for kw in title_keywords:
                if kw in text:
                    score += 1.0
            
            # 如果是短文本且命中关键词，考虑前移
            if score > 0 and len(text) < 50:
                if score > best_score:
                    best_score = score
                    best_idx = i
        
        if best_idx < start_idx:
            logger.info(f"start前移：{start_idx} -> {best_idx}")
        
        return best_idx
    
    def _refine_end(
        self,
        start_idx: int,
        end_idx: int,
        all_blocks: List[DocumentBlock],
        block_scores: Dict[str, float],
    ) -> int:
        """
        微调结束位置（应用终止规则）
        
        Args:
            start_idx: start索引
            end_idx: 原始end索引
            all_blocks: 全文块列表
            block_scores: 块得分字典
            
        Returns:
            细化后的end索引
        """
        current_idx = end_idx
        
        # 遍历从start到end的所有块，检查终止条件
        for i in range(start_idx + 1, min(end_idx + 1, len(all_blocks))):
            block = all_blocks[i]
            text = block.text or ""
            score = block_scores.get(block.block_id, 0.0)
            
            # 终止规则1：遇到下一个高分anchor
            if i > start_idx + self.config.next_anchor_min_distance:
                if score >= self.config.min_evidence_score:
                    logger.info(f"终止规则1触发：遇到下一个高分anchor at {i}")
                    current_idx = i - 1
                    break
            
            # 终止规则2：遇到章节切换信号
            for pattern in self.config.chapter_switch_patterns:
                if re.search(pattern, text):
                    # 如果该块得分也高，更确定是切换点
                    if score >= 0.5:
                        logger.info(f"终止规则2触发：章节切换信号 at {i}")
                        current_idx = i - 1
                        break
            else:
                continue
            break
            
            # 终止规则3：超过最大块数/字符数（在外层已处理）
        
        # 尾部去噪：连续N个空白/极短块
        current_idx = self._trim_tail(
            start_idx,
            current_idx,
            all_blocks,
        )
        
        return current_idx
    
    def _trim_tail(
        self,
        start_idx: int,
        end_idx: int,
        all_blocks: List[DocumentBlock],
    ) -> int:
        """
        尾部去噪：去除连续的空白/极短块
        
        Args:
            start_idx: start索引
            end_idx: end索引
            all_blocks: 全文块列表
            
        Returns:
            trim后的end索引
        """
        trim_count = self.config.refine_tail_trim_blocks
        
        # 从尾部往前检查
        empty_count = 0
        new_end_idx = end_idx
        
        for i in range(end_idx, start_idx, -1):
            block = all_blocks[i]
            text = (block.text or "").strip()
            
            # 判断是否是"空白/极短"块
            if len(text) < 10:
                empty_count += 1
                if empty_count >= trim_count:
                    # 连续N个空块，回缩
                    new_end_idx = i - 1
                    logger.info(f"尾部去噪：回缩到 {new_end_idx}")
                    break
            else:
                # 遇到非空块，重置计数
                empty_count = 0
        
        return max(start_idx, new_end_idx)

