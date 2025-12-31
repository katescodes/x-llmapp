"""
目录生成 Schema V2 + ExtractionSpec 构建器

包含：
1. Pydantic Schema定义（DirectoryNodeV2, DirectoryDataV2, DirectoryResultV2）
2. ExtractionSpec构建函数（build_directory_spec_async）
"""
import os
import logging
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from app.platform.extraction.types import ExtractionSpec
from app.platform.extraction.exceptions import PromptNotFoundError

logger = logging.getLogger(__name__)


class DirectoryNodeV2(BaseModel):
    """目录节点 V2"""
    title: str = Field(..., min_length=1, description="章节标题")
    level: int = Field(..., ge=1, le=6, description="层级 (1~6)")
    order_no: int = Field(..., ge=1, description="同级顺序号")
    parent_ref: Optional[str] = Field(None, description="父节点标题引用")
    required: bool = Field(True, description="是否必填")
    volume: Optional[str] = Field(None, description="卷号")
    notes: Optional[str] = Field(None, description="备注说明")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="证据 chunk IDs")
    
    @field_validator('title')
    @classmethod
    def title_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("title 不能为空")
        return v.strip()


class DirectoryDataV2(BaseModel):
    """目录数据 V2"""
    nodes: List[DirectoryNodeV2] = Field(..., min_length=1, description="目录节点列表")
    
    @field_validator('nodes')
    @classmethod
    def nodes_not_empty(cls, v):
        if not v:
            raise ValueError("nodes 数组不能为空")
        return v


class DirectoryResultV2(BaseModel):
    """目录生成结果 V2"""
    data: DirectoryDataV2 = Field(..., description="目录数据")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="全局证据 chunk IDs")
    
    def to_dict_exclude_none(self):
        """转为字典，排除 None 值"""
        return self.model_dump(exclude_none=True)


# ==================== ExtractionSpec 构建器 ====================

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

