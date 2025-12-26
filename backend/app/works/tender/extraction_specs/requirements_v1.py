"""
招标要求抽取规格 (v1)
"""
import os
from pathlib import Path
from typing import Dict

from app.platform.extraction.types import ExtractionSpec


def _load_prompt(filename: str) -> str:
    """加载prompt文件"""
    prompt_dir = Path(__file__).parent.parent / "prompts"
    prompt_file = prompt_dir / filename
    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read().strip()


async def build_requirements_spec_async(pool=None) -> ExtractionSpec:
    """
    构建招标要求抽取规格（异步版本，支持数据库加载）
    
    从招标文件中抽取结构化的 requirements
    
    Args:
        pool: 数据库连接池（可选）
    
    Returns:
        ExtractionSpec: 包含 queries、prompt、topk 等配置
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # 尝试从数据库加载prompt
    prompt = None
    if pool:
        try:
            from app.services.prompt_loader import PromptLoaderService
            loader = PromptLoaderService(pool)
            prompt = await loader.get_active_prompt("requirements_v1")
            if prompt:
                logger.info(f"✅ [Prompt] Loaded from DATABASE for requirements_v1, length={len(prompt)}")
        except Exception as e:
            logger.warning(f"⚠️ [Prompt] Failed to load from database: {e}")
    
    # Fallback：从文件加载
    if not prompt:
        prompt = _load_prompt("requirements_v1.md")
        logger.info(f"📁 [Prompt] Using FALLBACK (file) for requirements_v1, length={len(prompt)}")
    
    # 查询：覆盖所有类型的要求
    queries_env = os.getenv("V1_REQUIREMENTS_QUERIES_JSON")
    if queries_env:
        import json
        queries = json.loads(queries_env)
    else:
        queries: Dict[str, str] = {
            # 资格要求
            "qualification": "投标人资格 资格要求 资质要求 资质证书 营业执照 业绩要求 项目经验 类似项目 人员要求 项目经理 技术负责人 财务要求 资产负债率 投标限制 禁止投标 资格审查 必须具备 必须提供 须具有",
            
            # 技术要求
            "technical": "技术要求 技术规范 技术标准 技术参数 性能指标 不低于 不超过 大于等于 小于等于 应符合 必须满足 应达到 技术指标 设备参数 质量标准 技术规格",
            
            # 商务要求
            "business": "商务要求 合同条款 付款方式 付款条件 交付期 交货期 质保期 验收标准 违约责任 不得偏离 实质性偏离 应当 必须 须",
            
            # 价格要求
            "price": "投标报价 报价要求 最高限价 招标控制价 不得超过 价格构成 报价范围 总价 单价 预算",
            
            # 文档结构要求
            "doc_structure": "投标文件 文件编制 格式要求 装订要求 正本 副本 签字盖章 密封 必须提交 应包含 份数",
            
            # 进度与质量要求
            "schedule_quality": "工期要求 施工周期 交付期限 里程碑 关键节点 质量要求 质量标准 验收标准 必须达到 应符合 不得低于",
            
            # 评分标准（也是一种要求）
            "evaluation": "评分标准 评分细则 得分规则 评审标准 打分方法 分值 满分 扣分 加分 不得分",
            
            # 其他要求
            "other": "应当 必须 须 不得 禁止 严格执行 不允许 强制 要求 条件 前提",
        }
    
    # 可配置参数
    top_k_per_query = int(os.getenv("V1_REQUIREMENTS_TOPK_PER_QUERY", "25"))
    top_k_total = int(os.getenv("V1_REQUIREMENTS_TOPK_TOTAL", "120"))
    
    return ExtractionSpec(
        prompt=prompt,
        queries=queries,
        topk_per_query=top_k_per_query,
        topk_total=top_k_total,
        doc_types=["tender"],
        temperature=0.0,
    )


def build_requirements_spec() -> ExtractionSpec:
    """
    构建招标要求抽取规格（同步版本，使用文件）
    
    向后兼容，直接从文件加载
    
    Returns:
        ExtractionSpec: 包含 queries、prompt、topk 等配置
    """
    # 加载 prompt
    prompt = _load_prompt("requirements_v1.md")
    
    # 查询：覆盖所有类型的要求
    queries_env = os.getenv("V1_REQUIREMENTS_QUERIES_JSON")
    if queries_env:
        import json
        queries = json.loads(queries_env)
    else:
        queries: Dict[str, str] = {
            # 资格要求
            "qualification": "投标人资格 资格要求 资质要求 资质证书 营业执照 业绩要求 项目经验 类似项目 人员要求 项目经理 技术负责人 财务要求 资产负债率 投标限制 禁止投标 资格审查 必须具备 必须提供 须具有",
            
            # 技术要求
            "technical": "技术要求 技术规范 技术标准 技术参数 性能指标 不低于 不超过 大于等于 小于等于 应符合 必须满足 应达到 技术指标 设备参数 质量标准 技术规格",
            
            # 商务要求
            "business": "商务要求 合同条款 付款方式 付款条件 交付期 交货期 质保期 验收标准 违约责任 不得偏离 实质性偏离 应当 必须 须",
            
            # 价格要求
            "price": "投标报价 报价要求 最高限价 招标控制价 不得超过 价格构成 报价范围 总价 单价 预算",
            
            # 文档结构要求
            "doc_structure": "投标文件 文件编制 格式要求 装订要求 正本 副本 签字盖章 密封 必须提交 应包含 份数",
            
            # 进度与质量要求
            "schedule_quality": "工期要求 施工周期 交付期限 里程碑 关键节点 质量要求 质量标准 验收标准 必须达到 应符合 不得低于",
            
            # 评分标准（也是一种要求）
            "evaluation": "评分标准 评分细则 得分规则 评审标准 打分方法 分值 满分 扣分 加分 不得分",
            
            # 其他要求
            "other": "应当 必须 须 不得 禁止 严格执行 不允许 强制 要求 条件 前提",
        }
    
    # 可配置参数
    top_k_per_query = int(os.getenv("V1_REQUIREMENTS_TOPK_PER_QUERY", "25"))
    top_k_total = int(os.getenv("V1_REQUIREMENTS_TOPK_TOTAL", "120"))
    
    return ExtractionSpec(
        prompt=prompt,
        queries=queries,
        topk_per_query=top_k_per_query,
        topk_total=top_k_total,
        doc_types=["tender"],
        temperature=0.0,
    )

