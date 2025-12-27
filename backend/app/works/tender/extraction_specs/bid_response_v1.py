"""
投标响应要素抽取规格 (v1)
"""
import os
from typing import Dict, Optional

from app.platform.extraction.types import ExtractionSpec
from app.platform.extraction.exceptions import PromptNotFoundError


async def build_bid_response_spec_async(pool=None) -> ExtractionSpec:
    """
    构建投标响应要素抽取规格（异步版本，从数据库加载）
    
    Args:
        pool: 数据库连接池（必需）
        
    Returns:
        ExtractionSpec: 包含 queries、prompt、topk 等配置
        
    Raises:
        PromptNotFoundError: 数据库中未找到活跃的prompt模板
    """
    import logging
    logger = logging.getLogger(__name__)

    if not pool:
        raise ValueError("pool参数是必需的，无法从数据库加载prompt")

    # 从数据库加载prompt
    try:
        from app.services.prompt_loader import PromptLoaderService
        loader = PromptLoaderService(pool)
        prompt = await loader.get_active_prompt("bid_response")
        
        if not prompt:
            raise PromptNotFoundError("bid_response")
        
        logger.info(f"✅ [Prompt] Loaded from DATABASE for bid_response, length={len(prompt)}")
    except PromptNotFoundError:
        raise
    except Exception as e:
        logger.error(f"❌ [Prompt] Failed to load from database: {e}")
        raise RuntimeError(f"加载prompt失败: {e}") from e

    queries: Dict[str, str] = {
        "qualification": "投标人资格 营业执照 资质证书 业绩证明 财务报表 注册资本 信用记录 社会信用代码 法定代表人",
        "technical": "技术参数 技术规范 技术方案 性能指标 功能参数 设备配置 CPU 内存 硬盘 处理器 标准 型号 规格",
        "business": "商务条款 质保期 付款方式 交付时间 验收标准 售后服务 违约责任 保修期",
        "price": "投标总价 报价 单价 分项报价 价格 合价 金额 报价表 总计",
        "doc_structure": "投标文件目录 文件组成 格式 密封 签字 盖章 授权",
        "schedule_quality": "工期 进度计划 质量保证 质量标准 施工方案 项目计划",
        "other": "其他承诺 补充说明 偏离表 备注"
    }

    top_k_per_query = int(os.getenv("V2_RETRIEVAL_TOPK_PER_QUERY", "20"))
    top_k_total = int(os.getenv("V2_RETRIEVAL_TOPK_TOTAL", "140"))  # 7 queries * 20 topk

    return ExtractionSpec(
        prompt=prompt,
        queries=queries,
        topk_per_query=top_k_per_query,
        topk_total=top_k_total,
        doc_types=["bid"],  # 只检索投标文件
        temperature=0.0,
    )

