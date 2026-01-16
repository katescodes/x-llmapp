"""
PlaceholderDetector - 范本占位符检测器
识别范本中的占位符（如"（采购人名称）"、"【项目名称】"等）并映射到字段
"""
import re
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class PlaceholderDetector:
    """范本占位符检测器"""
    
    def __init__(self):
        """初始化占位符模式和字段映射"""
        self.placeholder_patterns = self._build_placeholder_patterns()
        self.field_mappings = self._build_field_mappings()
    
    def _build_placeholder_patterns(self) -> List[str]:
        """
        构建占位符识别模式
        
        支持的格式：
        - （XXX）
        - 【XXX】
        - [XXX]
        - _____（下划线）
        - XXX：________
        """
        return [
            r'[（(]([^）)]{2,20})[）)]',          # （采购人名称）
            r'[【\[]([^】\]]{2,20})[】\]]',       # 【项目名称】
            r'([^：:\n]{2,20})[：:]\s*_{3,}',    # 项目编号：________
            r'_{5,}',                             # 单独的下划线（至少5个）
        ]
    
    def _build_field_mappings(self) -> Dict[str, List[str]]:
        """
        构建占位符关键词到字段的映射
        
        Returns:
            {
                "purchaser_name": ["采购人", "招标人", "甲方", ...],
                ...
            }
        """
        return {
            "purchaser_name": [
                "采购人名称", "采购人", "招标人名称", "招标人", 
                "甲方名称", "甲方", "采购单位", "招标单位"
            ],
            "project_name": [
                "项目名称", "工程名称", "项目", "工程"
            ],
            "project_number": [
                "项目编号", "招标编号", "采购编号", "编号", "磋商编号"
            ],
            "bid_opening_time": [
                "开标时间", "开标日期"
            ],
            "bid_deadline": [
                "投标截止时间", "截止时间", "递交投标文件截止时间"
            ],
            "budget_amount": [
                "预算金额", "最高限价", "控制价", "项目预算", "投资估算"
            ],
            "bid_bond": [
                "投标保证金", "保证金"
            ],
            "contact_person": [
                "联系人", "项目联系人"
            ],
            "contact_phone": [
                "联系电话", "电话", "联系方式"
            ],
            "agent_name": [
                "代理机构", "招标代理", "采购代理"
            ],
            # 投标人信息（从企业信息填充）
            "bidder_name": [
                "投标人名称", "投标人", "乙方名称", "乙方", "供应商名称", "供应商"
            ],
            "bidder_address": [
                "投标人地址", "公司地址", "企业地址", "地址"
            ],
            "bidder_legal_person": [
                "法定代表人", "法人", "法人代表"
            ],
            "bidder_phone": [
                "投标人电话", "公司电话", "企业电话"
            ],
        }
    
    def detect_placeholders(self, text: str) -> List[Dict[str, any]]:
        """
        检测文本中的所有占位符
        
        Args:
            text: 范本文本
            
        Returns:
            [
                {
                    "placeholder": "（采购人名称）",  # 原始占位符
                    "field_name": "purchaser_name",   # 映射的字段名
                    "start": 10,                      # 起始位置
                    "end": 18,                        # 结束位置
                    "confidence": 0.9                 # 置信度
                },
                ...
            ]
        """
        placeholders = []
        
        # 应用所有占位符模式
        for pattern in self.placeholder_patterns:
            try:
                matches = re.finditer(pattern, text)
                for match in matches:
                    placeholder_text = match.group(0)
                    
                    # 提取占位符中的关键词
                    keyword = self._extract_keyword(placeholder_text, pattern)
                    
                    # 映射到字段
                    field_name, confidence = self._map_to_field(keyword)
                    
                    if field_name:
                        placeholders.append({
                            "placeholder": placeholder_text,
                            "field_name": field_name,
                            "start": match.start(),
                            "end": match.end(),
                            "confidence": confidence,
                            "keyword": keyword
                        })
                        logger.debug(f"检测到占位符: {placeholder_text} -> {field_name} (置信度: {confidence})")
            
            except re.error as e:
                logger.warning(f"占位符检测正则错误: {e}")
                continue
        
        # 去重（同一位置可能被多个模式匹配）
        placeholders = self._deduplicate_placeholders(placeholders)
        
        logger.info(f"共检测到 {len(placeholders)} 个占位符")
        return placeholders
    
    def _extract_keyword(self, placeholder_text: str, pattern: str) -> str:
        """
        从占位符中提取关键词
        
        Args:
            placeholder_text: 占位符文本（如"（采购人名称）"）
            pattern: 使用的正则模式
            
        Returns:
            关键词（如"采购人名称"）
        """
        # 尝试提取括号内的内容
        keyword_match = re.search(r'[（(【\[]([^）)】\]]+)[）)】\]]', placeholder_text)
        if keyword_match:
            return keyword_match.group(1).strip()
        
        # 尝试提取冒号前的内容
        colon_match = re.search(r'([^：:\n]+)[：:]', placeholder_text)
        if colon_match:
            return colon_match.group(1).strip()
        
        # 如果只是下划线，返回空（需要上下文判断）
        if re.match(r'^_{3,}$', placeholder_text):
            return ""
        
        return placeholder_text.strip()
    
    def _map_to_field(self, keyword: str) -> Tuple[Optional[str], float]:
        """
        将关键词映射到字段名
        
        Args:
            keyword: 关键词（如"采购人名称"）
            
        Returns:
            (field_name, confidence)
        """
        if not keyword:
            return None, 0.0
        
        # 完全匹配
        for field_name, keywords in self.field_mappings.items():
            if keyword in keywords:
                return field_name, 1.0
        
        # 部分匹配（包含关系）
        for field_name, keywords in self.field_mappings.items():
            for kw in keywords:
                if kw in keyword or keyword in kw:
                    confidence = len(kw) / max(len(keyword), len(kw))
                    return field_name, confidence * 0.8  # 部分匹配置信度打折
        
        logger.debug(f"无法映射关键词: {keyword}")
        return None, 0.0
    
    def _deduplicate_placeholders(
        self, 
        placeholders: List[Dict]
    ) -> List[Dict]:
        """
        去除重复的占位符（保留置信度最高的）
        
        Args:
            placeholders: 占位符列表
            
        Returns:
            去重后的列表
        """
        if not placeholders:
            return []
        
        # 按位置分组
        position_groups = {}
        for ph in placeholders:
            key = (ph["start"], ph["end"])
            if key not in position_groups:
                position_groups[key] = []
            position_groups[key].append(ph)
        
        # 每个位置保留置信度最高的
        result = []
        for group in position_groups.values():
            best = max(group, key=lambda x: x["confidence"])
            result.append(best)
        
        # 按位置排序
        result.sort(key=lambda x: x["start"])
        
        return result
    
    def fill_placeholders(
        self, 
        text: str, 
        field_values: Dict[str, str],
        placeholders: Optional[List[Dict]] = None
    ) -> str:
        """
        填充文本中的占位符
        
        Args:
            text: 原始文本
            field_values: 字段值字典（如 {"purchaser_name": "某某公司"}）
            placeholders: 已检测的占位符列表（如果为None则重新检测）
            
        Returns:
            填充后的文本
        """
        if not field_values:
            logger.warning("没有提供字段值，跳过填充")
            return text
        
        # 如果没有提供占位符列表，重新检测
        if placeholders is None:
            placeholders = self.detect_placeholders(text)
        
        if not placeholders:
            logger.info("未检测到任何占位符")
            return text
        
        # 按位置倒序排序（从后往前替换，避免位置偏移）
        placeholders_sorted = sorted(placeholders, key=lambda x: x["start"], reverse=True)
        
        filled_count = 0
        for ph in placeholders_sorted:
            field_name = ph["field_name"]
            value = field_values.get(field_name)
            
            if value:
                # 替换占位符
                text = text[:ph["start"]] + value + text[ph["end"]:]
                filled_count += 1
                logger.info(f"✅ 填充占位符: {ph['placeholder']} -> {value}")
            else:
                # 标记为待填写
                marked_value = f"【待填写：{ph.get('keyword', ph['field_name'])}】"
                text = text[:ph["start"]] + marked_value + text[ph["end"]:]
                logger.debug(f"⚠️  占位符无值: {ph['placeholder']} -> {marked_value}")
        
        logger.info(f"共填充 {filled_count}/{len(placeholders)} 个占位符")
        return text


# 全局实例
_detector_instance = None

def get_placeholder_detector() -> PlaceholderDetector:
    """获取全局占位符检测器实例"""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = PlaceholderDetector()
    return _detector_instance

