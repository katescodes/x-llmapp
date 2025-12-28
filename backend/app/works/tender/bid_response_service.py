"""
投标响应要素抽取服务 (v1)
"""
import logging
import uuid
from typing import Any, Dict, List, Optional

from app.platform.extraction.engine import ExtractionEngine
from app.platform.retrieval.facade import RetrievalFacade
# from app.platform.llm.orchestrator import LLMOrchestrator  # 不存在的路径
from app.services.embedding_provider_store import get_embedding_store
from app.services.dao.tender_dao import TenderDAO

logger = logging.getLogger(__name__)


class BidResponseService:
    """投标响应要素抽取服务"""
    
    def __init__(
        self,
        pool: Any,
        engine: ExtractionEngine,
        retriever: RetrievalFacade,
        llm: Any,  # LLM orchestrator (使用Any避免循环导入)
    ):
        self.pool = pool
        self.engine = engine
        self.retriever = retriever
        self.llm = llm
        self.dao = TenderDAO(pool)
    
    async def extract_bid_response_v1(
        self,
        project_id: str,
        bidder_name: str,
        model_id: Optional[str],
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        抽取投标响应要素 (v1)
        
        从指定投标人的投标文件中抽取结构化响应要素，并落库到 tender_bid_response_items
        
        Args:
            project_id: 项目ID
            bidder_name: 投标人名称（用于过滤投标文件）
            model_id: LLM模型ID
            run_id: 运行ID（可选）
        
        Returns:
            {
                "bidder_name": "投标人名称",
                "responses": [
                    {
                        "response_id": "qual_resp_001",
                        "dimension": "qualification",
                        "response_type": "document_ref",
                        "response_text": "...",
                        "extracted_value_json": {...},
                        "evidence_chunk_ids": [...]
                    }
                ]
            }
        """
        logger.info(f"BidResponseService: extract_bid_response_v1 start project_id={project_id}, bidder={bidder_name}")
        
        # 1. 获取 embedding provider
        embedding_provider = get_embedding_store().get_default()
        if not embedding_provider:
            raise ValueError("No embedding provider configured")
        
        # 2. 构建 spec
        from app.works.tender.extraction_specs.bid_response_v1 import build_bid_response_spec_async
        spec = await build_bid_response_spec_async(self.pool)
        
        # 3. 调用引擎
        result = await self.engine.run(
            spec=spec,
            retriever=self.retriever,
            llm=self.llm,
            project_id=project_id,
            model_id=model_id,
            run_id=run_id,
            embedding_provider=embedding_provider,
            # TODO: 如果需要过滤特定投标人的文件，可以传入 doc_filters
        )
        
        # 4. 解析结果
        responses_list = []
        # 重要：直接使用传入的bidder_name，不使用LLM提取的值
        # 这样可以确保前后端的bidder_name一致，避免查询时匹配不上
        extracted_bidder_name = bidder_name
        
        if isinstance(result.data, dict):
            # 不再使用LLM提取的bidder_name: extracted_bidder_name = result.data.get("bidder_name", bidder_name)
            responses_list = result.data.get("responses", [])
        else:
            logger.warning(f"BidResponseService: unexpected data format, type={type(result.data)}")
        
        if not isinstance(responses_list, list):
            logger.error(f"BidResponseService: responses not list, type={type(responses_list)}")
            responses_list = []
        
        # 5. 落库到 tender_bid_response_items
        added_count = 0
        for resp in responses_list:
            response_id = resp.get("response_id", str(uuid.uuid4()))
            
            # 确保每个 response 有唯一的 ID
            db_id = str(uuid.uuid4())
            
            # 转换dict和list为JSON字符串（Psycopg3需要）
            import json
            extracted_value_json = resp.get("extracted_value_json", {})
            evidence_chunk_ids = resp.get("evidence_chunk_ids", [])
            
            self.dao._execute("""
                INSERT INTO tender_bid_response_items (
                    id, project_id, bidder_name, dimension, response_type,
                    response_text, extracted_value_json, evidence_chunk_ids
                ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::text[])
            """, (
                db_id,
                project_id,
                extracted_bidder_name,
                resp.get("dimension", "other"),
                resp.get("response_type", "text"),
                resp.get("response_text", ""),
                json.dumps(extracted_value_json) if extracted_value_json else '{}',
                evidence_chunk_ids,
            ))
            added_count += 1
        
        logger.info(f"BidResponseService: extract_bid_response_v1 done responses={len(responses_list)}, added={added_count}")
        
        return {
            "bidder_name": extracted_bidder_name,
            "responses": responses_list,
            "added_count": added_count
        }
    
    async def extract_all_bidders_responses(
        self,
        project_id: str,
        bidder_names: List[str],
        model_id: Optional[str],
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        批量抽取所有投标人的响应要素
        
        Args:
            project_id: 项目ID
            bidder_names: 投标人名称列表
            model_id: LLM模型ID
            run_id: 运行ID（可选）
        
        Returns:
            {
                "total_bidders": 3,
                "total_responses": 50,
                "bidders": {
                    "投标人A": {"responses": [...], "added_count": 15},
                    "投标人B": {"responses": [...], "added_count": 18},
                    ...
                }
            }
        """
        logger.info(f"BidResponseService: extract_all_bidders_responses start project_id={project_id}, bidders={len(bidder_names)}")
        
        results = {}
        total_responses = 0
        
        for bidder_name in bidder_names:
            try:
                result = await self.extract_bid_response_v1(
                    project_id=project_id,
                    bidder_name=bidder_name,
                    model_id=model_id,
                    run_id=run_id,
                )
                results[bidder_name] = result
                total_responses += len(result.get("responses", []))
            except Exception as e:
                logger.error(f"BidResponseService: Failed to extract for bidder={bidder_name}: {e}", exc_info=True)
                results[bidder_name] = {"error": str(e), "responses": [], "added_count": 0}
        
        logger.info(f"BidResponseService: extract_all_bidders_responses done total_responses={total_responses}")
        
        return {
            "total_bidders": len(bidder_names),
            "total_responses": total_responses,
            "bidders": results
        }

