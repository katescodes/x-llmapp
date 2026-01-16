"""
招标要求规则提取器
使用确定性规则识别标准废标条款，为LLM提取提供补充和加速
"""
import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class RuleResult:
    """规则提取的结果"""
    requirement_text: str
    consequence: str
    evidence_text: str
    confidence: float  # 规则的置信度
    matched_rule: str  # 匹配的规则名称
    span: Tuple[int, int]  # 文本中的位置范围


class TenderRuleExtractor:
    """招标文件规则提取器"""
    
    def __init__(self):
        # 定义规则：每个规则包含 pattern、consequence、confidence
        self.rules = [
            # === 废标/无效规则 ===
            {
                "name": "明确废标",
                "pattern": r"([^。；\n]{0,80}?)(导致|视为|作为|属于|认定为|判定为|构成)(废标|投标无效|标书无效|否决投标|取消投标资格|不予受理)",
                "consequence": "废标/无效",
                "confidence": 1.0,
            },
            {
                "name": "废标前置条件",
                "pattern": r"(废标|投标无效|否决投标)(.{0,50}?)(情形|条件|情况)",
                "consequence": "废标/无效",
                "confidence": 0.98,
            },
            {
                "name": "不满足即废标",
                "pattern": r"(不满足|未满足|不符合)(.{0,30}?)(废标|投标无效|否决)",
                "consequence": "废标/无效",
                "confidence": 0.95,
            },
            
            # === 关键要求规则 ===
            {
                "name": "标记符号-星号",
                "pattern": r"([★▲])(.{1,200}?)(?=[。；\n]|$)",
                "consequence": "关键要求",
                "confidence": 0.95,
            },
            {
                "name": "不允许偏离",
                "pattern": r"(不允许|不得|禁止|严禁)(负)?偏离(.{1,100}?)(?=[。；\n]|$)",
                "consequence": "关键要求",
                "confidence": 0.90,
            },
            {
                "name": "实质性要求",
                "pattern": r"(实质性要求|实质性响应)(.{0,30}?)[：:]\s*(.{1,200}?)(?=[。；\n]|$)",
                "consequence": "关键要求",
                "confidence": 0.90,
            },
            {
                "name": "投标人必须",
                "pattern": r"(投标人|供应商|竞标人)(必须|务必|须)(.{1,100}?)(?=[。；\n]|$)",
                "consequence": "关键要求",
                "confidence": 0.85,
            },
            {
                "name": "不得禁止",
                "pattern": r"([^。；\n]{0,60}?)(不得|禁止|严禁)([^。；\n]{1,80}?)(?=[。；\n]|$)",
                "consequence": "关键要求",
                "confidence": 0.85,
            },
            
            # === 扣分规则 ===
            {
                "name": "明确扣分",
                "pattern": r"([^。；\n]{0,80}?)(扣|减|降低|减少)\s*(\d+\.?\d*)\s*分",
                "consequence": "扣分",
                "confidence": 0.95,
            },
            {
                "name": "不满足扣分",
                "pattern": r"(不满足|未满足|不符合)(.{0,50}?)(扣|减)\s*分",
                "consequence": "扣分",
                "confidence": 0.90,
            },
            
            # === 加分规则 ===
            {
                "name": "明确加分",
                "pattern": r"([^。；\n]{0,80}?)(得|加|获得|给予)\s*(\d+\.?\d*)\s*分",
                "consequence": "加分",
                "confidence": 0.90,
            },
        ]
        
        # 编译正则表达式
        for rule in self.rules:
            rule["compiled"] = re.compile(rule["pattern"], re.DOTALL)
        
        # 排除模式：包含这些关键词的不提取（通常是说明性文字）
        self.exclude_patterns = [
            re.compile(r"(示例|举例|如下|注：|说明|备注)", re.IGNORECASE),
            re.compile(r"^(第.{1,5}条|第.{1,5}章|附件)"),  # 纯标题
        ]
    
    def extract(self, text: str, max_results: int = 200) -> List[RuleResult]:
        """
        从文本中使用规则提取要求
        
        Args:
            text: 原始文本
            max_results: 最大提取数量
            
        Returns:
            规则提取的结果列表
        """
        results = []
        seen_spans = set()  # 避免重复提取同一位置
        
        for rule in self.rules:
            pattern = rule["compiled"]
            
            for match in pattern.finditer(text):
                # 获取匹配的完整文本
                matched_text = match.group(0).strip()
                span = match.span()
                
                # ✨ 新增：向前扫描到完整句子（确保不截断）
                extended_span = self._extend_to_full_sentence(text, span)
                extended_text = text[extended_span[0]:extended_span[1]].strip()
                
                # 检查是否与已有结果重叠（允许10%的重叠）
                if self._has_significant_overlap(extended_span, seen_spans):
                    continue
                
                # 排除不相关的匹配
                if self._should_exclude(extended_text):
                    continue
                
                # 清理文本：去除多余空白、换行
                cleaned_text = self._clean_text(extended_text)
                
                # 太短或太长的不要
                if len(cleaned_text) < 10 or len(cleaned_text) > 500:
                    continue
                
                # 提取上下文作为证据
                evidence = self._extract_evidence(text, extended_span)
                
                result = RuleResult(
                    requirement_text=cleaned_text,
                    consequence=rule["consequence"],
                    evidence_text=evidence,
                    confidence=rule["confidence"],
                    matched_rule=rule["name"],
                    span=extended_span,  # 使用扩展后的span
                )
                
                results.append(result)
                seen_spans.add(extended_span)
                
                # 达到上限就停止
                if len(results) >= max_results:
                    break
            
            if len(results) >= max_results:
                break
        
        # 按文本位置排序
        results.sort(key=lambda x: x.span[0])
        
        logger.info(f"规则引擎提取了 {len(results)} 个要求")
        return results
    
    def _has_significant_overlap(self, span: Tuple[int, int], seen_spans: set) -> bool:
        """检查span是否与已有span有显著重叠"""
        start, end = span
        span_len = end - start
        
        for seen_start, seen_end in seen_spans:
            # 计算重叠长度
            overlap_start = max(start, seen_start)
            overlap_end = min(end, seen_end)
            overlap_len = max(0, overlap_end - overlap_start)
            
            # 如果重叠超过50%，认为是重复
            if overlap_len > span_len * 0.5:
                return True
        
        return False
    
    def _should_exclude(self, text: str) -> bool:
        """判断是否应该排除该匹配"""
        for pattern in self.exclude_patterns:
            if pattern.search(text):
                return True
        return False
    
    def _extend_to_full_sentence(self, text: str, span: Tuple[int, int]) -> Tuple[int, int]:
        """
        向前扫描到完整句子，确保不截断
        
        策略：
        1. 检查开头是否是半句话（如："外，"、"，其他"）
        2. 如果是，向前扫描到句子分隔符（。；\n）或常见开头（如"除"、"对于"）
        3. 限制最大扩展长度，避免过度扩展
        
        Args:
            text: 完整文本
            span: 原始匹配的位置
            
        Returns:
            扩展后的span
        """
        start, end = span
        original_start = start
        
        # 检查开头是否是不完整的（常见的半句话特征）
        preview = text[max(0, start-5):start+20] if start >= 5 else text[start:start+20]
        incomplete_starts = ['外，', '外。', '，', '；', '、', '的', '等', '及', '或']
        
        is_incomplete = False
        for marker in incomplete_starts:
            if preview.startswith(marker) or preview[max(0, 5-start):].startswith(marker):
                is_incomplete = True
                break
        
        # 如果开头不完整，向前扫描
        if is_incomplete and start > 0:
            # 向前最多扩展100个字符
            scan_start = max(0, start - 100)
            search_text = text[scan_start:start]
            
            # 查找前一个句子结束的位置（。；\n）
            last_separator = -1
            for i in range(len(search_text) - 1, -1, -1):
                if search_text[i] in '。；\n':
                    last_separator = i
                    break
            
            if last_separator >= 0:
                # 从分隔符后开始
                new_start = scan_start + last_separator + 1
                # 跳过空白
                while new_start < start and text[new_start] in ' \t\n':
                    new_start += 1
                start = new_start
            else:
                # 没找到分隔符，查找常见的句子开头
                sentence_starts = ['除', '对于', '关于', '如果', '若', '当', '在', '对', '根据']
                for marker in sentence_starts:
                    idx = search_text.rfind(marker)
                    if idx >= 0:
                        start = scan_start + idx
                        break
        
        # 确保不过度扩展（不超过原始位置前80个字符）
        if original_start - start > 80:
            start = original_start - 80
        
        return (start, end)
    
    def _clean_text(self, text: str) -> str:
        """清理文本"""
        # 去除多余的空白和换行
        text = re.sub(r'\s+', ' ', text)
        # 去除首尾空白
        text = text.strip()
        
        # 去除开头的标点符号（中英文）
        # 循环删除，直到开头不是标点为止
        while text and text[0] in '，。；：、！？,.:;!?|—-–…　 \t\n':
            text = text[1:].strip()
        
        # 去除编号（1）、1.、①等
        text = re.sub(r'^[\(（]?\d+[\)）]\.?\s*', '', text)
        text = re.sub(r'^[①②③④⑤⑥⑦⑧⑨⑩]\s*', '', text)
        
        # 再次去除可能产生的前导标点
        while text and text[0] in '，。；：、！？,.:;!?|—-–…　 \t\n':
            text = text[1:].strip()
        
        # 去除尾部的冗余标点（除了句号、问号、感叹号）
        while text and len(text) > 1 and text[-1] in '，、,;；:：':
            text = text[:-1].strip()
        
        return text
    
    def _extract_evidence(self, full_text: str, span: Tuple[int, int], context_chars: int = 100) -> str:
        """提取证据文本（包含上下文）"""
        start, end = span
        
        # 向前找到句子开头或段落开头
        evidence_start = max(0, start - context_chars)
        while evidence_start > 0 and full_text[evidence_start] not in '\n。；':
            evidence_start -= 1
        
        # 向后找到句子结尾或段落结尾
        evidence_end = min(len(full_text), end + context_chars)
        while evidence_end < len(full_text) and full_text[evidence_end] not in '\n。；':
            evidence_end += 1
        
        evidence = full_text[evidence_start:evidence_end].strip()
        
        # 清理
        evidence = re.sub(r'\s+', ' ', evidence)
        
        # 限制长度
        if len(evidence) > 300:
            evidence = evidence[:300] + "..."
        
        return evidence
    
    def convert_to_requirements(self, rule_results: List[RuleResult]) -> List[Dict]:
        """
        将规则结果转换为标准的requirement格式（与LLM格式兼容）
        
        Args:
            rule_results: 规则提取的结果
            
        Returns:
            标准格式的要求列表
        """
        requirements = []
        
        # 建立consequence到dimension的映射
        consequence_to_dimension = {
            "废标/无效": "qualification",
            "关键要求": "technical",
            "扣分": "scoring",
            "加分": "scoring",
        }
        
        for i, result in enumerate(rule_results, 1):
            # 确定维度
            dimension = consequence_to_dimension.get(result.consequence, "other")
            
            # 生成标题（从requirement_text的前30个字符）
            title = result.requirement_text[:30] + "..." if len(result.requirement_text) > 30 else result.requirement_text
            
            # 构建与LLM格式兼容的字典
            req = {
                "dimension": dimension,
                "title": title,
                "requirement_text": result.requirement_text,
                "consequence": result.consequence,
                "evidence_text": result.evidence_text,
                "requirement_type": "rule_based",  # 标记为规则提取
                "is_mandatory": result.consequence in ["废标/无效", "关键要求"],  # 废标和关键要求为强制
                "confidence": result.confidence,
                "extraction_source": "RULE",  # 提取来源
                "rule_name": result.matched_rule,  # 匹配的规则名称
            }
            requirements.append(req)
        
        return requirements

