"""
招标要求提取规格 (v2)

注：虽然内部保留"risks"模块名（历史兼容），但实际功能是提取招标要求。
"""
from app.platform.extraction.types import ExtractionSpec
from app.platform.extraction.exceptions import PromptNotFoundError


async def build_risks_spec_async(pool=None) -> ExtractionSpec:
    """
    构建招标要求提取规格（异步版本，从数据库加载）
    
    从招标文件中提取法律、技术、商务、合规等招标要求。
    
    Args:
        pool: 数据库连接池（必需）
    
    Returns:
        ExtractionSpec: 包含 query、prompt、topk 等配置
        
    Raises:
        PromptNotFoundError: 数据库中未找到活跃的prompt模板
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not pool:
        raise ValueError("pool参数是必需的，无法从数据库加载prompt")
    
    # 从数据库加载prompt（模块名为"risks"，实际功能是招标要求提取）
    try:
        from app.services.prompt_loader import PromptLoaderService
        loader = PromptLoaderService(pool)
        prompt = await loader.get_active_prompt("risks")
        
        if not prompt:
            raise PromptNotFoundError("risks")
        
        logger.info(f"✅ [Prompt] Loaded from DATABASE for risks (招标要求提取), length={len(prompt)}")
    except PromptNotFoundError:
        raise
    except Exception as e:
        logger.error(f"❌ [Prompt] Failed to load from database: {e}")
        raise RuntimeError(f"加载prompt失败: {e}") from e
    
    return ExtractionSpec(
        task_type="extract_risks",
        prompt=prompt,
        queries="招标要求 技术规范 资质条件 合规要求 法律条款 必须条款 硬性要求",
        topk_per_query=20,
        topk_total=20,
        doc_types=["tender"],
        temperature=0.0,
    )

