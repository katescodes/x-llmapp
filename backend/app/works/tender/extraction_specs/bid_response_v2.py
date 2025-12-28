"""
投标响应要素抽取规格 (v2)

v2 新特性:
- 新增 normalized_fields_json: 标准化字段集，用于自动化审核
- 新增 evidence_segment_ids: 文档片段ID，用于精确定位
- 保留 evidence_chunk_ids: 向后兼容
"""
import logging
import os
from typing import Dict, Optional

from app.platform.extraction.types import ExtractionSpec
from app.platform.extraction.exceptions import PromptNotFoundError

logger = logging.getLogger(__name__)


async def build_bid_response_spec_v2_async(pool=None) -> ExtractionSpec:
    """
    构建投标响应要素抽取规格 v2（异步版本，从数据库加载）
    
    v2 变更:
    - prompt 使用 bid_response v2 版本（schema_version: bid_response_v2）
    - 输出包含 normalized_fields_json（标准化字段）
    - 输出包含 evidence_segment_ids（文档片段ID）
    
    Args:
        pool: 数据库连接池（必需）
        
    Returns:
        ExtractionSpec: 包含 queries、prompt、topk 等配置
        
    Raises:
        PromptNotFoundError: 数据库中未找到活跃的prompt模板
    """
    if not pool:
        raise ValueError("pool参数是必需的，无法从数据库加载prompt")

    # 从数据库加载 v2 prompt
    try:
        from app.services.prompt_loader import PromptLoaderService
        loader = PromptLoaderService(pool)
        
        # 优先加载 v2 prompt（通过 version=2 或直接指定 ID）
        prompt = None
        
        # 方法1: 直接通过ID加载v2
        try:
            prompt = await loader.get_prompt_by_id("prompt_bid_response_v2_001")
            if prompt:
                logger.info(f"✅ [Prompt] Loaded BID_RESPONSE_V2 from DATABASE by ID, length={len(prompt)}")
        except Exception as e:
            logger.warning(f"Failed to load v2 by ID: {e}")
        
        # 方法2: 如果没有v2，尝试加载 module=bid_response 的最新活跃版本
        if not prompt:
            prompt = await loader.get_active_prompt("bid_response")
            if prompt:
                logger.info(f"✅ [Prompt] Loaded BID_RESPONSE (active) from DATABASE, length={len(prompt)}")
        
        if not prompt:
            raise PromptNotFoundError("bid_response (v2 或活跃版本)")
        
    except PromptNotFoundError:
        raise
    except Exception as e:
        logger.error(f"❌ [Prompt] Failed to load from database: {e}")
        raise RuntimeError(f"加载prompt失败: {e}") from e

    # Queries 定义（与 v1 相同，检索策略不变）
    queries: Dict[str, str] = {
        "qualification": "投标人资格 营业执照 资质证书 业绩证明 财务报表 注册资本 信用记录 社会信用代码 法定代表人",
        "technical": "技术参数 技术规范 技术方案 性能指标 功能参数 设备配置 CPU 内存 硬盘 处理器 标准 型号 规格",
        "business": "商务条款 质保期 付款方式 交付时间 验收标准 售后服务 违约责任 保修期 工期 项目周期",
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

