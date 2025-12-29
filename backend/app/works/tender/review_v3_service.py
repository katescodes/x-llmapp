"""
审核服务 V3 - 固定流水线模式

使用 ReviewPipelineV3 实现分层审核：
1. Mapping: 构建候选对
2. Hard Gate: 硬性审核
3. Quant Checks: 量化检查
4. Semantic Escalation: 语义升级
5. Consistency: 一致性检查
6. Aggregate: 汇总统计
"""
import logging
from typing import Any, Dict, List, Optional

from app.works.tender.review_pipeline_v3 import ReviewPipelineV3

logger = logging.getLogger(__name__)


class ReviewV3Service:
    """审核服务 V3 - 固定流水线"""
    
    def __init__(self, pool: Any, llm_orchestrator: Any = None):
        self.pool = pool
        self.llm = llm_orchestrator
        self.pipeline = ReviewPipelineV3(pool, llm_orchestrator)
    
    async def run_review_v3(
        self,
        project_id: str,
        bidder_name: str,
        model_id: Optional[str] = None,
        custom_rule_pack_ids: Optional[List[str]] = None,
        run_id: Optional[str] = None,
        use_llm_semantic: bool = False,
    ) -> Dict[str, Any]:
        """
        运行审核 V3（固定流水线）
        
        Args:
            project_id: 项目ID
            bidder_name: 投标人名称
            model_id: LLM模型ID
            custom_rule_pack_ids: 保留参数（兼容性，不再使用）
            run_id: 运行ID（可选）
            use_llm_semantic: 是否使用LLM语义审核（可选，默认False）
        
        Returns:
            {
                "total_review_items": 50,
                "pass_count": 30,
                "fail_count": 15,
                "warn_count": 5,
                "pending_count": 3,
                "review_mode": "FIXED_PIPELINE",
                "items": [...]
            }
        """
        logger.info(f"ReviewV3: run_review start project_id={project_id}, bidder={bidder_name}")
        logger.info("ReviewV3: Using FIXED_PIPELINE mode")
        
        # 使用固定流水线
        result = await self.pipeline.run_pipeline(
            project_id=project_id,
            bidder_name=bidder_name,
            model_id=model_id,
            use_llm_semantic=use_llm_semantic,
            review_run_id=run_id,
        )
        
        return {
            "review_mode": "FIXED_PIPELINE",
            **result["stats"],
            "items": result["review_items"]
        }
