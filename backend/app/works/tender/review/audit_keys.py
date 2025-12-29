"""
审查键（norm_key）定义与规范化工具

目标：为招标要求与投标响应建立可比对的标准键，实现精确匹配
"""
import re
from typing import Optional


# ==================== 允许的 norm_key 列表（最小集） ====================

ALLOWED_NORM_KEYS = {
    # 价格相关
    "total_price_cny",              # 投标总价（人民币元）
    "bid_security_amount_cny",      # 投标保证金金额（人民币元）
    "price_upper_limit_cny",        # 最高限价/招标控制价（人民币元）
    
    # 工期与质保
    "duration_days",                # 工期（天）
    "warranty_months",              # 质保期（月）
    
    # 公司信息
    "company_name",                 # 公司名称
    "credit_code",                  # 统一社会信用代码
    "legal_representative",         # 法定代表人
    
    # 证件材料（布尔型：是否提供）
    "doc_business_license_present",     # 营业执照
    "doc_authorization_present",        # 法定代表人授权书
    "doc_seal_present",                 # 公章/签章
    "doc_qualification_present",        # 资质证书
    "doc_security_receipt_present",     # 保证金回执
    "doc_performance_present",          # 业绩证明
}


# ==================== 维度枚举（中英文映射） ====================

DIMENSION_ENUM = {
    "qualification",     # 资格
    "technical",         # 技术
    "business",          # 商务
    "price",            # 价格
    "doc_structure",    # 文档结构
    "schedule_quality", # 进度与质量
    "other",            # 其他
}

DIMENSION_CN_TO_EN = {
    "资格": "qualification",
    "技术": "technical",
    "商务": "business",
    "价格": "price",
    "报价": "price",
    "文档": "doc_structure",
    "文档结构": "doc_structure",
    "进度": "schedule_quality",
    "质量": "schedule_quality",
    "工期": "schedule_quality",
    "其他": "other",
}


def normalize_dimension(dim: str) -> str:
    """
    统一维度枚举：将中文维度映射为英文
    
    Args:
        dim: 维度值（可能是中文或英文）
    
    Returns:
        英文维度值
    """
    if not dim:
        return "other"
    
    dim = dim.strip().lower()
    
    # 如果已经是英文枚举，直接返回
    if dim in DIMENSION_ENUM:
        return dim
    
    # 中文映射
    return DIMENSION_CN_TO_EN.get(dim, "other")


# ==================== 价格锚点判断 ====================

def is_price_anchor(text: str) -> bool:
    """
    判断文本是否包含投标报价的锚点关键词
    
    只有明确的报价相关词汇才返回 True，业绩合同金额不算
    
    Args:
        text: 待检查的文本
    
    Returns:
        True 如果包含报价锚点
    """
    if not text:
        return False
    
    # 投标报价的明确锚点
    price_anchors = [
        "投标总价", "投标报价", "报价表", "开标一览表", 
        "报价汇总", "投标函总价", "报价一览", "分项报价",
        "总报价", "投标金额"
    ]
    
    # 业绩/合同关键词（排除）
    performance_keywords = [
        "合同金额", "业绩", "类似项目", "项目业绩", 
        "中标金额", "合同价", "历史业绩", "完成项目"
    ]
    
    # 检查是否包含业绩关键词（如果有，直接返回 False）
    for keyword in performance_keywords:
        if keyword in text:
            return False
    
    # 检查是否包含报价锚点
    for anchor in price_anchors:
        if anchor in text:
            return True
    
    return False


# ==================== 金额规范化 ====================

def normalize_money_to_cny(text: str) -> Optional[int]:
    """
    将金额文本规范化为人民币分（整数）
    
    支持格式：
    - "500万元" → 5000000
    - "50万" → 500000
    - "1,234,567元" → 1234567
    - "￥100,000" → 100000
    
    Args:
        text: 包含金额的文本
    
    Returns:
        金额（元，整数），解析失败返回 None
    """
    if not text:
        return None
    
    # 移除常见货币符号和空格
    text = text.replace("￥", "").replace("人民币", "").replace(" ", "").strip()
    
    # 匹配金额模式
    # 支持：数字 + 可选小数 + 可选单位（万元/万/元）
    pattern = r'([\d,]+(?:\.\d+)?)\s*(万元|万|元)?'
    match = re.search(pattern, text)
    
    if not match:
        return None
    
    try:
        # 提取数字（移除逗号）
        number_str = match.group(1).replace(",", "")
        number = float(number_str)
        
        # 单位处理
        unit = match.group(2) or ""
        if "万" in unit:
            number *= 10000
        
        return int(number)
    except (ValueError, AttributeError):
        return None


# ==================== 工期规范化 ====================

def normalize_duration_to_days(text: str) -> Optional[int]:
    """
    将工期文本规范化为天数（整数）
    
    支持格式：
    - "90天" → 90
    - "120日" → 120
    - "90个自然日" → 90
    - "3个月" → 90 (按30天/月估算)
    
    Args:
        text: 包含工期的文本
    
    Returns:
        工期（天数，整数），解析失败返回 None
    """
    if not text:
        return None
    
    # 匹配工期模式
    # 天/日
    day_pattern = r'(\d+)\s*(?:个)?(?:自然)?(?:日历)?(?:天|日)'
    match = re.search(day_pattern, text)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    
    # 月（估算为 30 天/月）
    month_pattern = r'(\d+)\s*(?:个)?月'
    match = re.search(month_pattern, text)
    if match:
        try:
            months = int(match.group(1))
            return months * 30
        except ValueError:
            pass
    
    return None


# ==================== 质保期规范化 ====================

def normalize_warranty_to_months(text: str) -> Optional[int]:
    """
    将质保期文本规范化为月数（整数）
    
    支持格式：
    - "24个月" → 24
    - "2年" → 24
    - "4年" → 48
    
    Args:
        text: 包含质保期的文本
    
    Returns:
        质保期（月数，整数），解析失败返回 None
    """
    if not text:
        return None
    
    # 匹配月数
    month_pattern = r'(\d+)\s*(?:个)?月'
    match = re.search(month_pattern, text)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    
    # 匹配年数（转换为月）
    year_pattern = r'(\d+)\s*年'
    match = re.search(year_pattern, text)
    if match:
        try:
            years = int(match.group(1))
            return years * 12
        except ValueError:
            pass
    
    return None


# ==================== 验证工具 ====================

def is_valid_norm_key(key: str) -> bool:
    """
    检查 norm_key 是否在允许列表中
    
    Args:
        key: norm_key 值
    
    Returns:
        True 如果是有效的 norm_key
    """
    return key in ALLOWED_NORM_KEYS


def validate_normalized_fields(fields: dict) -> dict:
    """
    验证并清理 normalized_fields_json
    
    移除不在允许列表中的 norm_key
    
    Args:
        fields: normalized_fields_json 字典
    
    Returns:
        清理后的字典
    """
    if not isinstance(fields, dict):
        return {}
    
    cleaned = {}
    for key, value in fields.items():
        if key == "_norm_key" or key in ALLOWED_NORM_KEYS:
            cleaned[key] = value
    
    return cleaned

