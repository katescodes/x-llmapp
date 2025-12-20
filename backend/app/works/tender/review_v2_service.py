"""
新审核服务 (v2) - 检索驱动 + 分维度生成
"""
import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from psycopg_pool import ConnectionPool

from app.platform.extraction.exceptions import ExtractionParseError, ExtractionSchemaError
from app.platform.extraction.types import ExtractionResult, RetrievalTrace
from app.platform.retrieval.facade import RetrievalFacade
from app.services.embedding_provider_store import get_embedding_store
from app.platform.extraction.context import build_marked_context
from app.platform.extraction.llm_adapter import call_llm
from app.platform.extraction.json_utils import extract_json, repair_json
from app.works.tender.review.review_dimensions import build_review_dimensions, ReviewDimension
from app.works.tender.schemas.review_v2 import ReviewResultV2, ReviewItemV2, ReviewDataV2

logger = logging.getLogger(__name__)


def _load_prompt(filename: str) -> str:
    """加载 prompt 模板文件"""
    filepath = os.path.join(os.path.dirname(__file__), "prompts", filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


class ReviewV2Service:
    """新审核服务 - 检索驱动 + 分维度生成"""
    
    def __init__(self, pool: ConnectionPool, llm_orchestrator: Any = None):
        self.pool = pool
        self.retriever = RetrievalFacade(pool)
        self.llm = llm_orchestrator
        self.review_prompt_template = _load_prompt("review_v2.md")
        self.dimensions = build_review_dimensions()
        self.max_dims = int(os.getenv("REVIEW_MAX_DIMS", "7"))
        self.top_k_per_dim = int(os.getenv("REVIEW_TOPK_PER_DIM", "20"))
        self.review_dimensions_enabled = os.getenv("REVIEW_DIMENSIONS_ENABLED", "").split(',')
        if self.review_dimensions_enabled == ['']: # Handle empty string case
            self.review_dimensions_enabled = [d.name for d in self.dimensions] # Enable all by default

    async def run_review_v2(
        self,
        project_id: str,
        model_id: Optional[str],
        bidder_name: Optional[str],
        bid_asset_ids: List[str],
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        运行审核 (v2) - 检索驱动 + 分维度生成
        
        Returns:
            Dict[str, Any] - 包含 items, retrieval_trace, raw_outputs 等
        """
        logger.info(f"ReviewV2: run_review_v2 start project_id={project_id} run_id={run_id}")
        
        embedding_provider = get_embedding_store().get_default()
        if not embedding_provider:
            raise ValueError("No embedding provider configured")
        
        all_compare_items: List[ReviewItemV2] = []
        all_retrieval_traces: Dict[str, Any] = {}
        all_raw_outputs: Dict[str, str] = {}
        
        enabled_dimensions = [d for d in self.dimensions if d.name in self.review_dimensions_enabled][:self.max_dims]

        for dim in enabled_dimensions:
            logger.info(f"ReviewV2: Processing dimension: {dim.name}")
            
            # 1. 检索招标要求 chunks
            tender_chunks_objs = await self.retriever.retrieve(
                query=dim.tender_query,
                project_id=project_id,
                doc_types=["tender"],
                embedding_provider=embedding_provider,
                top_k=dim.top_k,
                run_id=run_id,
                mode="NEW_ONLY" # Assuming NEW_ONLY for review retrieval
            )
            tender_ctx = build_marked_context([c.model_dump() for c in tender_chunks_objs])
            
            # 2. 检索投标响应 chunks
            bid_chunks_objs = await self.retriever.retrieve(
                query=dim.bid_query,
                project_id=project_id,
                doc_types=["bid"],
                embedding_provider=embedding_provider,
                top_k=dim.top_k,
                bidder_name=bidder_name,
                bid_asset_ids=bid_asset_ids,
                run_id=run_id,
                mode="NEW_ONLY" # Assuming NEW_ONLY for review retrieval
            )
            bid_ctx = build_marked_context([c.model_dump() for c in bid_chunks_objs])

            # Store retrieval trace for this dimension
            all_retrieval_traces[dim.name] = {
                "tender_retrieved_count": len(tender_chunks_objs),
                "bid_retrieved_count": len(bid_chunks_objs),
                "tender_queries": dim.tender_query,
                "bid_queries": dim.bid_query,
                "top_k": dim.top_k,
                "tender_chunk_ids": [c.chunk_id for c in tender_chunks_objs],
                "bid_chunk_ids": [c.chunk_id for c in bid_chunks_objs],
            }

            # Handle empty retrieval scenarios
            if not tender_ctx and not bid_ctx:
                logger.warning(f"ReviewV2: No chunks found for dimension {dim.name}, skipping LLM call.")
                all_compare_items.append(ReviewItemV2(
                    dimension=dim.name,
                    requirement_text="未检索到相关招标要求证据",
                    response_text="未检索到相关投标响应证据",
                    result="risk",
                    notes="无足够证据进行审查"
                ))
                continue
            elif not tender_ctx:
                logger.warning(f"ReviewV2: No tender chunks found for dimension {dim.name}.")
                all_compare_items.append(ReviewItemV2(
                    dimension=dim.name,
                    requirement_text="未检索到相关招标要求证据",
                    response_text="根据现有投标响应进行评估",
                    result="risk",
                    notes="招标要求证据不足"
                ))
                # Continue to LLM with only bid_ctx if tender_ctx is empty but bid_ctx exists
            elif not bid_ctx:
                logger.warning(f"ReviewV2: No bid chunks found for dimension {dim.name}.")
                all_compare_items.append(ReviewItemV2(
                    dimension=dim.name,
                    requirement_text="根据现有招标要求进行评估",
                    response_text="未检索到相关投标响应证据",
                    result="risk",
                    notes="投标响应证据不足"
                ))
                # Continue to LLM with only tender_ctx if bid_ctx is empty but tender_ctx exists

            # 3. 调用 LLM 生成该维度的 review items
            messages = [
                {"role": "system", "content": self.review_prompt_template.strip()},
                {
                    "role": "user",
                    "content": self.review_prompt_template.format(
                        dimension_name=dim.name,
                        tender_ctx=tender_ctx or "(未检索到招标要求原文片段)",
                        bid_ctx=bid_ctx or "(未检索到投标响应原文片段)"
                    )
                },
            ]
            
            llm_start = time.time()
            try:
                out_text = await call_llm(
                    messages,
                    self.llm,
                    model_id,
                    temperature=0.0, # Ensure reproducibility
                    max_tokens=4096
                )
                all_raw_outputs[dim.name] = out_text
                llm_ms = int((time.time() - llm_start) * 1000)
                logger.info(f"ReviewV2: LLM call for {dim.name} took {llm_ms}ms")
            except Exception as llm_error:
                logger.error(f"ReviewV2: LLM call failed for dimension {dim.name}: {llm_error}")
                raise RuntimeError(f"LLM call failed for review dimension {dim.name}") from llm_error

            # 4. 解析和校验 LLM 输出
            try:
                obj = extract_json(out_text)
                validated_result = ReviewResultV2.model_validate(obj)
                dimension_items = validated_result.data.items
                all_compare_items.extend(dimension_items)
                logger.info(f"ReviewV2: Dimension {dim.name} generated {len(dimension_items)} items.")
            except Exception as e:
                logger.error(f"ReviewV2: JSON parse or schema validation failed for dimension {dim.name}: {e}")
                logger.error(f"Raw LLM output for {dim.name}: {out_text[:1000]}")
                raise ExtractionSchemaError(
                    f"Review schema validation failed for dimension {dim.name}: {str(e)}",
                    errors=[] # TODO: Extract pydantic errors if possible
                ) from e
        
        # Collect all evidence_chunk_ids from all items
        all_evidence_chunk_ids = sorted(list(set(
            cid for item in all_compare_items for cid in item.evidence_chunk_ids
        )))

        # Generate evidence spans (simplified for now, can be enhanced)
        all_evidence_spans = [] # TODO: Implement detailed evidence span generation if needed

        logger.info(f"ReviewV2: run_review_v2 completed. Total compare items: {len(all_compare_items)}")

        return {
            "items": [item.to_dict_exclude_none() for item in all_compare_items],
            "retrieval_trace": all_retrieval_traces,
            "raw_outputs": all_raw_outputs,
            "evidence_chunk_ids": all_evidence_chunk_ids,
            "evidence_spans": all_evidence_spans,
        }
