"""
审查维度定义
"""
from typing import List
from dataclasses import dataclass
import os


@dataclass
class ReviewDimension:
    """审查维度"""
    name: str
    tender_query: str
    bid_query: str
    top_k: int = 20


def get_review_dimensions() -> List[ReviewDimension]:
    """
    获取审查维度列表
    
    可通过环境变量 REVIEW_DIMENSIONS_ENABLED 控制启用的维度（逗号分隔）
    """
    all_dims = [
        ReviewDimension(
            name="资格审查/资质",
            tender_query="资格要求 资质 证书 业绩 人员 必须 否则废标 否决",
            bid_query="资质证书 营业执照 业绩证明 人员证书 社保",
            top_k=20
        ),
        ReviewDimension(
            name="报价/价格",
            tender_query="预算 最高限价 投标报价 价格 费用 报价要求",
            bid_query="投标报价 总价 分项报价 价格明细",
            top_k=20
        ),
        ReviewDimension(
            name="工期与交付",
            tender_query="工期 交付期 完成时间 交货 安装 调试",
            bid_query="工期承诺 交付时间 进度安排 里程碑",
            top_k=20
        ),
        ReviewDimension(
            name="技术参数",
            tender_query="技术要求 技术规范 技术参数 性能指标 功能要求",
            bid_query="技术方案 技术参数 性能指标 功能实现",
            top_k=20
        ),
        ReviewDimension(
            name="商务条款",
            tender_query="付款 质保 验收 违约 保证金 合同条款",
            bid_query="付款承诺 质保承诺 验收方案 商务条款",
            top_k=20
        ),
        ReviewDimension(
            name="评分响应",
            tender_query="评分标准 评分细则 加分项 评审 分值",
            bid_query="评分响应 加分项证明 评分材料",
            top_k=20
        ),
        ReviewDimension(
            name="文件结构/完整性",
            tender_query="投标文件格式 投标文件组成 目录 必须提交 否则废标",
            bid_query="投标文件目录 文件完整性 格式符合性",
            top_k=15
        ),
    ]
    
    # 过滤启用的维度
    enabled = os.getenv("REVIEW_DIMENSIONS_ENABLED", "").strip()
    if enabled:
        enabled_names = set(name.strip() for name in enabled.split(","))
        all_dims = [d for d in all_dims if d.name in enabled_names]
    
    # 限制最大维度数
    max_dims = int(os.getenv("REVIEW_MAX_DIMS", "7"))
    return all_dims[:max_dims]

