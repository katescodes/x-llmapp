"""
FragmentType - 范本片段类型枚举
定义招标文件中常见的投标文件格式范本类型
"""
from enum import Enum


class FragmentType(str, Enum):
    """范本片段类型"""
    
    BID_LETTER = "BID_LETTER"                           # 投标函
    LEGAL_REP_AUTHORIZATION = "LEGAL_REP_AUTHORIZATION"  # 法定代表人授权书/授权委托书
    BID_OPENING_SCHEDULE = "BID_OPENING_SCHEDULE"        # 开标一览表/报价一览表
    ITEMIZED_PRICE_SCHEDULE = "ITEMIZED_PRICE_SCHEDULE"  # 分项报价表/价格明细表/清单报价表
    TECH_DEVIATION_TABLE = "TECH_DEVIATION_TABLE"        # 技术偏离表/技术响应表
    BIZ_DEVIATION_TABLE = "BIZ_DEVIATION_TABLE"          # 商务偏离表/条款偏离表
    SERVICE_COMMITMENT = "SERVICE_COMMITMENT"            # 售后/服务承诺书
    QUALITY_SCHEDULE_COMMITMENT = "QUALITY_SCHEDULE_COMMITMENT"  # 质量/工期承诺书
    INTEGRITY_STATEMENT = "INTEGRITY_STATEMENT"          # 诚信/廉洁/无违法声明
    BID_BOND_FORM = "BID_BOND_FORM"                      # 投标保证金/保函格式
    JOINT_BID_AGREEMENT = "JOINT_BID_AGREEMENT"          # 联合体协议书
    OTHER_FORMAT = "OTHER_FORMAT"                        # 其他格式（兜底）
    
    def __str__(self):
        return self.value
