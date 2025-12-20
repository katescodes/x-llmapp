"""
审查服务 V2 - 检索驱动 + 分维度生成
"""
import logging
import os
from typing import Any, Dict, List, Optional
from pathlib import Path

from psycopg_pool import ConnectionPool

from app.platform.retrieval.facade import RetrievalFacade
from app.platform.extraction.context import build_marked_context
from app.platform.extraction.llm_adapter import call_llm
from app.platform.extraction.json_utils import extract_json, repair_json
from app.platform.extraction.exceptions import ExtractionParseError, ExtractionSchemaError
from app.services.embedding_provider_store import get_embedding_store
from .review_dimensions import get_review_dimensions
from ..schemas.review_v2 import ReviewResultV2

logger = logging.getLogger(__name__)


class ReviewV2Service:
    """审查服务 V2 - 检索驱动"""
    
    def __init__(self, pool: ConnectionPool, llm_orchestrator: Any = None):
        self.pool = pool
        self.retriever = RetrievalFacade(pool)
        self.llm = llm_orchestrator
    
    async def run_review_v2(
        self,
        project_id: str,
        bidder_name: Optional[str],
        bid_asset_ids: List[str],
        model_id: Optional[str],
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        运行审查 V2 - 分维度检索 + LLM
        
        Args:
            project_id: 项目 ID
            bidder_name: 投标人名称
            bid_asset_ids: 投标资产 IDs
            model_id: LLM 模型 ID
            run_id: 运行 ID (可选)
        
        Returns:
            {
                "items": [...],                    # 审查项列表
                "retrieval_trace": {...},          # 检索追踪
                "evidence_spans": [...],           # 证据片段
            }
        """
        logger.info(f"ReviewV2: run_review start project_id={project_id} bidder={bidder_name}")
        
        # 1. 获取 embedding provider
        embedding_provider = get_embedding_store().get_default()
        if not embedding_provider:
            raise ValueError("No embedding provider configured")
        
        # 2. 获取审查维度
        dimensions = get_review_dimensions()
        topk_per_dim = int(os.getenv("REVIEW_TOPK_PER_DIM", "20"))
        
        logger.info(f"ReviewV2: dimensions={len(dimensions)}, topk_per_dim={topk_per_dim}")
        
        # 3. 加载 Prompt
        prompt_file = Path(__file__).parent.parent / "prompts" / "review_v2.md"
        if not prompt_file.exists():
            raise FileNotFoundError(f"Review prompt not found: {prompt_file}")
        prompt = prompt_file.read_text(encoding="utf-8")
        
        # 4. 对每个维度执行检索 + LLM
        all_items = []
        retrieval_traces = {}
        all_evidence_spans = []
        
        for idx, dim in enumerate(dimensions, 1):
            logger.info(f"ReviewV2: processing dimension {idx}/{len(dimensions)}: {dim.name}")
            
            try:
                # 4.1 检索 tender chunks
                tender_chunks = await self.retriever.retrieve(
                    query=dim.tender_query,
                    project_id=project_id,
                    doc_types=["tender"],
                    embedding_provider=embedding_provider,
                    top_k=min(topk_per_dim, dim.top_k),
                )
                
                # 4.2 检索 bid chunks
                bid_chunks = await self.retriever.retrieve(
                    query=dim.bid_query,
                    project_id=project_id,
                    doc_types=["bid"],
                    embedding_provider=embedding_provider,
                    top_k=min(topk_per_dim, dim.top_k),
                    bidder_name=bidder_name,
                    bid_asset_ids=bid_asset_ids,
                )
                
                logger.info(
                    f"ReviewV2: dimension={dim.name} "
                    f"tender_chunks={len(tender_chunks)} bid_chunks={len(bid_chunks)}"
                )
                
                # 4.3 如果检索为空，生成风险项
                if not tender_chunks and not bid_chunks:
                    all_items.append({
                        "source": "compare",
                        "dimension": dim.name,
                        "requirement_text": "未检索到相关招标要求",
                        "response_text": "未检索到相关投标响应",
                        "result": "risk",
                        "rigid": False,
                        "notes": "检索未找到证据，可能关键词不匹配或文档未上传",
                        "evidence_chunk_ids": [],
                    })
                    continue
                
                if not tender_chunks:
                    all_items.append({
                        "source": "compare",
                        "dimension": dim.name,
                        "requirement_text": "未检索到相关招标要求",
                        "response_text": f"投标响应片段数: {len(bid_chunks)}",
                        "result": "risk",
                        "rigid": False,
                        "notes": "未检索到招标要求证据",
                        "evidence_chunk_ids": [f"bid:{c.chunk_id}" for c in bid_chunks[:3]],
                    })
                    continue
                
                if not bid_chunks:
                    all_items.append({
                        "source": "compare",
                        "dimension": dim.name,
                        "requirement_text": f"招标要求片段数: {len(tender_chunks)}",
                        "response_text": "未检索到相关投标响应",
                        "result": "risk",
                        "rigid": False,
                        "notes": "未检索到投标响应证据，建议人工核查",
                        "evidence_chunk_ids": [f"tender:{c.chunk_id}" for c in tender_chunks[:3]],
                    })
                    continue
                
                # 4.4 构建上下文
                tender_ctx = build_marked_context([
                    {"chunk_id": f"tender:{c.chunk_id}", "text": c.text, "meta": c.meta or {}}
                    for c in tender_chunks
                ])
                bid_ctx = build_marked_context([
                    {"chunk_id": f"bid:{c.chunk_id}", "text": c.text, "meta": c.meta or {}}
                    for c in bid_chunks
                ])
                
                # 4.5 调用 LLM
                messages = [
                    {"role": "system", "content": prompt.strip()},
                    {"role": "user", "content": f"""维度: {dim.name}

招标要求片段：
{tender_ctx}

投标响应片段：
{bid_ctx}"""},
                ]
                
                out_text = await call_llm(
                    messages,
                    self.llm,
                    model_id,
                    temperature=0.0,
                    max_tokens=2048
                )
                
                # 4.6 解析 JSON
                try:
                    obj = extract_json(out_text)
                except Exception as e:
                    logger.warning(f"ReviewV2: extract_json failed for {dim.name}, trying repair: {e}")
                    try:
                        obj = repair_json(out_text)
                    except Exception as e2:
                        logger.error(f"ReviewV2: repair_json failed for {dim.name}: {e2}")
                        raise ExtractionParseError(
                            f"Failed to parse JSON for dimension {dim.name}: {str(e2)}",
                            raw_output=out_text[:1000]
                        ) from e2
                
                # 4.7 Schema 校验
                try:
                    data_obj = obj if "data" in obj else {"data": obj}
                    validated = ReviewResultV2.model_validate(data_obj)
                    dim_items = validated.data.items
                except Exception as schema_err:
                    logger.error(f"ReviewV2: schema validation failed for {dim.name}: {schema_err}")
                    raise ExtractionSchemaError(
                        f"Schema validation failed for dimension {dim.name}: {str(schema_err)}",
                        schema_errors=schema_err.errors() if hasattr(schema_err, 'errors') else [],
                        raw_data=obj
                    ) from schema_err
                
                # 4.8 记录 retrieval_trace
                retrieval_traces[dim.name] = {
                    "tender_count": len(tender_chunks),
                    "bid_count": len(bid_chunks),
                    "tender_query": dim.tender_query,
                    "bid_query": dim.bid_query,
                    "tender_top_ids": [f"tender:{c.chunk_id}" for c in tender_chunks[:5]],
                    "bid_top_ids": [f"bid:{c.chunk_id}" for c in bid_chunks[:5]],
                }
                
                # 4.9 收集结果
                for item in dim_items:
                    item_dict = item.model_dump(exclude_none=True)
                    # 如果 dimension 字段和顶级维度名重复，则追加到前面
                    item_dim = item_dict.get("dimension", "")
                    if item_dim and item_dim != dim.name:
                        item_dict["dimension"] = f"{dim.name}/{item_dim}"
                    else:
                        item_dict["dimension"] = dim.name
                    
                    all_items.append(item_dict)
                
                logger.info(f"ReviewV2: dimension={dim.name} generated {len(dim_items)} items")
                
            except (ExtractionParseError, ExtractionSchemaError):
                # 解析/校验错误直接抛出，不捕获
                raise
            except Exception as e:
                logger.error(f"ReviewV2: dimension={dim.name} failed: {e}", exc_info=True)
                # 其他错误记录为风险项
                all_items.append({
                    "source": "compare",
                    "dimension": dim.name,
                    "requirement_text": f"维度审查失败",
                    "response_text": f"系统错误: {str(e)[:200]}",
                    "result": "risk",
                    "rigid": False,
                    "notes": "处理失败，建议人工核查",
                    "evidence_chunk_ids": [],
                })
        
        logger.info(f"ReviewV2: done total_items={len(all_items)} dimensions={len(dimensions)}")
        
        return {
            "items": all_items,
            "retrieval_trace": retrieval_traces,
            "evidence_spans": all_evidence_spans,
        }

