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

from app.platform.extraction.exceptions import ExtractionParseError, ExtractionSchemaError, PromptNotFoundError
from app.platform.extraction.types import ExtractionResult, RetrievalTrace
from app.platform.retrieval.facade import RetrievalFacade
from app.services.embedding_provider_store import get_embedding_store
from app.platform.extraction.context import build_marked_context
from app.platform.extraction.llm_adapter import call_llm
from app.platform.extraction.json_utils import extract_json, repair_json
from app.works.tender.review.review_dimensions import get_review_dimensions, ReviewDimension
from app.works.tender.schemas.review_v2 import ReviewResultV2, ReviewItemV2, ReviewDataV2

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # 确保INFO级别日志被输出


class ReviewV2Service:
    """新审核服务 - 检索驱动 + 分维度生成"""
    
    def __init__(self, pool: ConnectionPool, llm_orchestrator: Any = None, review_prompt: Optional[str] = None):
        """
        初始化审核服务
        
        Args:
            pool: 数据库连接池
            llm_orchestrator: LLM编排器
            review_prompt: 审核prompt模板（如果为None，则从数据库加载）
        """
        self.pool = pool
        self.retriever = RetrievalFacade(pool)
        self.llm = llm_orchestrator
        self.review_prompt_template = review_prompt  # 可能为None，稍后加载
        self.dimensions = get_review_dimensions()
        self.max_dims = int(os.getenv("REVIEW_MAX_DIMS", "7"))
        self.top_k_per_dim = int(os.getenv("REVIEW_TOPK_PER_DIM", "20"))
        self.review_dimensions_enabled = os.getenv("REVIEW_DIMENSIONS_ENABLED", "").split(',')
        if self.review_dimensions_enabled == ['']: # Handle empty string case
            self.review_dimensions_enabled = [d.name for d in self.dimensions] # Enable all by default
    
    async def _ensure_prompt_loaded(self):
        """确保prompt已加载"""
        if self.review_prompt_template is not None:
            return
        
        # 从数据库加载
        try:
            from app.services.prompt_loader import PromptLoaderService
            loader = PromptLoaderService(self.pool)
            prompt = await loader.get_active_prompt("review")
            
            if not prompt:
                raise PromptNotFoundError("review")
            
            self.review_prompt_template = prompt
            logger.info(f"✅ [Prompt] Loaded review from DATABASE, length={len(prompt)}")
        except PromptNotFoundError:
            raise
        except Exception as e:
            logger.error(f"❌ [Prompt] Failed to load review_v2 from database: {e}")
            raise RuntimeError(f"加载审核prompt失败: {e}") from e
    
    def _map_severity_to_result(self, severity: str) -> str:
        """将LLM返回的severity映射为schema要求的result"""
        severity_lower = severity.lower()
        if severity_lower in ["error", "fail", "failed"]:
            return "fail"
        elif severity_lower in ["warning", "warn", "risk"]:
            return "risk"
        else:  # info, pass, success等
            return "pass"

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
        # 确保prompt已加载
        await self._ensure_prompt_loaded()
        
        logger.info(f"ReviewV2: run_review_v2 start project_id={project_id} run_id={run_id}")
        logger.info(f"ReviewV2: Enabled dimensions: {[d.name for d in self.dimensions if d.name in self.review_dimensions_enabled]}")
        
        embedding_provider = get_embedding_store().get_default()
        if not embedding_provider:
            raise ValueError("No embedding provider configured")
        
        all_compare_items: List[ReviewItemV2] = []
        all_retrieval_traces: Dict[str, Any] = {}
        all_raw_outputs: Dict[str, str] = {}
        
        enabled_dimensions = [d for d in self.dimensions if d.name in self.review_dimensions_enabled][:self.max_dims]
        logger.info(f"ReviewV2: Will process {len(enabled_dimensions)} dimensions")

        for idx, dim in enumerate(enabled_dimensions, 1):
            logger.info(f"ReviewV2: ========== Processing dimension: {dim.name} ==========")
            
            # 1. 检索招标要求 chunks
            logger.info(f"ReviewV2: Retrieving tender chunks, query={dim.tender_query[:50]}...")
            tender_chunks_objs = await self.retriever.retrieve(
                query=dim.tender_query,
                project_id=project_id,
                doc_types=["tender"],
                embedding_provider=embedding_provider,
                top_k=dim.top_k,
                run_id=run_id,
                mode="NEW_ONLY" # Assuming NEW_ONLY for review retrieval
            )
            tender_ctx = build_marked_context([c.to_dict() for c in tender_chunks_objs])
            logger.info(f"ReviewV2: Retrieved {len(tender_chunks_objs)} tender chunks, context length={len(tender_ctx)}")
            
            # 2. 检索投标响应 chunks
            logger.info(f"ReviewV2: Retrieving bid chunks, query={dim.bid_query[:50]}...")
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
            bid_ctx = build_marked_context([c.to_dict() for c in bid_chunks_objs])
            logger.info(f"ReviewV2: Retrieved {len(bid_chunks_objs)} bid chunks, context length={len(bid_ctx)}")

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
                logger.warning(f"ReviewV2: No chunks found for dimension {dim.name}, adding fallback item and skipping LLM.")
                fallback_item = ReviewItemV2(
                    dimension=dim.name,
                    requirement_text="未检索到相关招标要求证据",
                    response_text="未检索到相关投标响应证据",
                    result="risk",
                    notes="无足够证据进行审查"
                )
                all_compare_items.append(fallback_item)
                logger.info(f"ReviewV2: Added fallback item, total items so far: {len(all_compare_items)}")
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
            # 构建用户消息（手动替换变量，避免 .format() 与 JSON 示例冲突）
            user_content = f"""
## 当前审核维度

**{dim.name}**

## 招标文件相关片段

{tender_ctx or "(未检索到招标要求原文片段)"}

## 投标文件相关片段

{bid_ctx or "(未检索到投标响应原文片段)"}

请基于以上材料，按照系统提示词中的格式输出审核结果。
"""
            
            messages = [
                {"role": "system", "content": self.review_prompt_template.strip()},
                {"role": "user", "content": user_content.strip()}
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
                # 尝试提取JSON
                try:
                    obj = extract_json(out_text)
                except Exception as json_error:
                    logger.warning(f"ReviewV2: JSON parse failed for {dim.name}: {json_error}, trying repair...")
                    # 尝试修复JSON
                    try:
                        obj = repair_json(out_text)
                        logger.info(f"ReviewV2: JSON repair succeeded for {dim.name}")
                    except Exception as repair_error:
                        logger.error(f"ReviewV2: JSON repair also failed for {dim.name}: {repair_error}")
                        # JSON解析失败，添加兜底项
                        logger.info(f"ReviewV2: Adding fallback item due to JSON parse failure for {dim.name}")
                        fallback_item = ReviewItemV2(
                            dimension=dim.name,
                            requirement_text="LLM返回格式错误，无法解析",
                            response_text="需要人工审核",
                            result="risk",
                            notes=f"LLM输出JSON格式错误: {str(repair_error)[:100]}"
                        )
                        all_compare_items.append(fallback_item)
                        logger.info(f"ReviewV2: Added JSON parse fallback item, total items: {len(all_compare_items)}")
                        continue
                
                logger.info(f"ReviewV2: Extracted JSON for {dim.name}, keys: {obj.keys() if isinstance(obj, dict) else 'not-a-dict'}")
                
                # 字段映射：将LLM可能返回的不同字段名转换为schema期望的格式
                if "data" in obj and isinstance(obj["data"], dict):
                    logger.info(f"ReviewV2: data keys: {obj['data'].keys()}")
                    # 如果LLM返回了 review_items，将其改为 items
                    if "review_items" in obj["data"]:
                        logger.info(f"ReviewV2: Converting review_items to items, count={len(obj['data']['review_items'])}")
                        obj["data"]["items"] = obj["data"].pop("review_items")
                    
                    # 转换每个item的字段
                    if "items" in obj["data"] and isinstance(obj["data"]["items"], list):
                        logger.info(f"ReviewV2: Converting {len(obj['data']['items'])} items")
                        converted_items = []
                        for item in obj["data"]["items"]:
                            # 构建notes字段
                            notes_parts = []
                            if item.get("title"):
                                notes_parts.append(item.get("title"))
                            if item.get("description"):
                                notes_parts.append(item.get("description"))
                            if item.get("suggestion"):
                                notes_parts.append(f"建议: {item.get('suggestion')}")
                            notes = " | ".join(notes_parts) if notes_parts else item.get("notes", "")
                            
                            converted_item = {
                                "dimension": dim.name,  # 使用当前维度名称
                                "requirement_text": item.get("requirement_text", item.get("description", "未提取到具体要求")),
                                "response_text": item.get("response_text", item.get("suggestion", "未提取到响应内容")),
                                "result": self._map_severity_to_result(item.get("severity", item.get("result", "warning"))),
                                "rigid": item.get("rigid", False),
                                "notes": notes,
                                "evidence_chunk_ids": item.get("evidence_chunk_ids", [])
                            }
                            converted_items.append(converted_item)
                        obj["data"]["items"] = converted_items
                        logger.info(f"ReviewV2: Converted items sample: {converted_items[0] if converted_items else 'empty'}")
                else:
                    logger.warning(f"ReviewV2: No 'data' key in obj for {dim.name}, adding fallback item")
                    fallback_item = ReviewItemV2(
                        dimension=dim.name,
                        requirement_text="LLM返回结构不正确",
                        response_text="需要人工审核",
                        result="risk",
                        notes="LLM输出缺少data字段"
                    )
                    all_compare_items.append(fallback_item)
                    continue
                
                validated_result = ReviewResultV2.model_validate(obj)
                dimension_items = validated_result.data.items
                all_compare_items.extend(dimension_items)
                logger.info(f"ReviewV2: Dimension {dim.name} generated {len(dimension_items)} items, total: {len(all_compare_items)}")
            except Exception as e:
                logger.error(f"ReviewV2: Schema validation or other error for dimension {dim.name}: {e}")
                logger.error(f"Raw LLM output for {dim.name}: {out_text[:500]}")
                # 添加兜底项而不是跳过
                fallback_item = ReviewItemV2(
                    dimension=dim.name,
                    requirement_text="处理异常",
                    response_text="需要人工审核",
                    result="risk",
                    notes=f"处理错误: {str(e)[:100]}"
                )
                all_compare_items.append(fallback_item)
                logger.info(f"ReviewV2: Added exception fallback item, total items: {len(all_compare_items)}")
                continue
        
        # Collect all evidence_chunk_ids from all items
        all_evidence_chunk_ids = sorted(list(set(
            cid for item in all_compare_items for cid in item.evidence_chunk_ids
        )))

        # Generate evidence spans (simplified for now, can be enhanced)
        all_evidence_spans = [] # TODO: Implement detailed evidence span generation if needed

        logger.info(f"ReviewV2: run_review_v2 completed. Total compare items: {len(all_compare_items)}")
        logger.info(f"ReviewV2: Returning dict with keys: items({len(all_compare_items)}), retrieval_trace({len(all_retrieval_traces)}), raw_outputs({len(all_raw_outputs)})")

        result_dict = {
            "items": [item.to_dict_exclude_none() for item in all_compare_items],
            "retrieval_trace": all_retrieval_traces,
            "raw_outputs": all_raw_outputs,
            "evidence_chunk_ids": all_evidence_chunk_ids,
            "evidence_spans": all_evidence_spans,
        }
        return result_dict
        
        logger.info(f"ReviewV2: result_dict['items'] length = {len(result_dict['items'])}")
        return result_dict
