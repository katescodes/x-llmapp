"""
目录生成抽取规格 V2
"""
import os
from typing import Dict

from app.platform.extraction.types import ExtractionSpec
from app.platform.extraction.exceptions import PromptNotFoundError


async def build_directory_spec_async(pool=None) -> ExtractionSpec:
    """
    构建目录生成抽取规格（异步版本，从数据库加载）
    
    Args:
        pool: 数据库连接池（必需）
    
    Returns:
        ExtractionSpec: 目录生成配置
        
    Raises:
        PromptNotFoundError: 数据库中未找到活跃的prompt模板
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not pool:
        raise ValueError("pool参数是必需的，无法从数据库加载prompt")
    
    # 从数据库加载Prompt模板
    try:
        from app.services.prompt_loader import PromptLoaderService
        import hashlib
        
        loader = PromptLoaderService(pool)
        prompt = await loader.get_active_prompt("directory")
        
        if not prompt:
            raise PromptNotFoundError("directory")
        
        # 计算 SHA256 用于确认 prompt 版本
        h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
        logger.info(f"✅ [Prompt] module=directory len={len(prompt)} sha256={h}")
    except PromptNotFoundError:
        raise
    except Exception as e:
        logger.error(f"❌ [Prompt] Failed to load from database: {e}")
        raise RuntimeError(f"加载prompt失败: {e}") from e
    
    # 三个查询维度（包含评分办法关键词）
    queries: Dict[str, str] = {
        "directory": "投标文件目录 投标文件组成 投标文件格式 目录结构 编制要求 章节 顺序",
        "forms": "格式范本 表格 模板 投标函 法定代表人 身份证明 授权委托书 附件",
        "requirements": "必填 必须提交 需提供 否则废标 否决项 资格审查 文件要求 评分办法 综合评分法 评审因素 评审标准 技术分 商务分 资信分 价格分 业绩 证书 方案 服务 培训 售后 保密",
    }
    
    # 检索参数（可通过环境变量覆盖）
    topk_per_query = int(os.getenv("V2_RETRIEVAL_TOPK_PER_QUERY", "30"))
    topk_total = int(os.getenv("V2_RETRIEVAL_TOPK_TOTAL", "120"))
    
    # Schema model（用于严格校验）
    from app.works.tender.schemas.directory_v2 import DirectoryResultV2
    
    return ExtractionSpec(
        task_type="generate_directory",
        prompt=prompt,
        queries=queries,
        topk_per_query=topk_per_query,
        topk_total=topk_total,
        doc_types=["tender"],
        temperature=0.0,  # 确定性输出
        schema_model=DirectoryResultV2,  # 严格 schema 校验
    )

