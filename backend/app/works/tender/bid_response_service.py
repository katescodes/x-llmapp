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
    
    def _prefetch_doc_segments(self, segment_ids: List[str]) -> Dict[str, Dict]:
        """批量预取 doc_segments（v2辅助函数）"""
        if not segment_ids:
            return {}
        
        import psycopg.rows
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute("""
                    SELECT 
                        id as segment_id, 
                        doc_version_id as asset_id, 
                        content_text as content, 
                        page_start, 
                        page_end, 
                        heading_path, 
                        segment_type
                    FROM doc_segments
                    WHERE id = ANY(%s)
                """, (list(set(segment_ids)),))
                rows = cur.fetchall()
        
        return {row["segment_id"]: row for row in rows}
    
    def _make_quote(self, text: str, limit: int = 220) -> str:
        """截取 quote（v2辅助函数）"""
        if not text:
            return ""
        text = " ".join(text.split())  # 压缩空白
        if len(text) <= limit:
            return text
        return text[:limit] + "..."
    
    def _build_evidence_json_from_segments(
        self, 
        segment_ids: List[str], 
        seg_map: Dict[str, Dict]
    ) -> List[Dict]:
        """从 segment_ids 组装 evidence_json（v2辅助函数）"""
        evidence = []
        for sid in segment_ids[:5]:  # 最多5条
            seg = seg_map.get(sid)
            if not seg:
                # 降级：只保留 segment_id
                evidence.append({
                    "segment_id": sid,
                    "source": "fallback_chunk"
                })
                continue
            
            evidence.append({
                "segment_id": sid,
                "asset_id": seg.get("asset_id"),
                "page_start": seg.get("page_start"),
                "page_end": seg.get("page_end"),
                "heading_path": seg.get("heading_path"),
                "quote": self._make_quote(seg.get("content", ""), 220),
                "segment_type": seg.get("segment_type"),
                "source": "doc_segments"
            })
        return evidence
    
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
    
    async def extract_bid_response_v2(
        self,
        project_id: str,
        bidder_name: str,
        model_id: Optional[str],
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        抽取投标响应要素 (v2)
        
        v2 新特性:
        - 输出 normalized_fields_json (标准化字段集)
        - 输出 evidence_segment_ids (文档片段ID)
        - 组装 evidence_json (页码+引用片段)
        
        Args:
            project_id: 项目ID
            bidder_name: 投标人名称
            model_id: LLM模型ID
            run_id: 运行ID（可选）
        
        Returns:
            {
                "bidder_name": "投标人名称",
                "responses": [...],
                "added_count": 15,
                "schema_version": "bid_response_v2"
            }
        """
        logger.info(f"BidResponseService: extract_bid_response_v2 start project_id={project_id}, bidder={bidder_name}")
        
        # 1. 获取 embedding provider
        embedding_provider = get_embedding_store().get_default()
        if not embedding_provider:
            raise ValueError("No embedding provider configured")
        
        # 2. 构建 v2 spec
        from app.works.tender.extraction_specs.bid_response_v2 import build_bid_response_spec_v2_async
        spec = await build_bid_response_spec_v2_async(self.pool)
        
        # 3. 调用引擎
        result = await self.engine.run(
            spec=spec,
            retriever=self.retriever,
            llm=self.llm,
            project_id=project_id,
            model_id=model_id,
            run_id=run_id,
            embedding_provider=embedding_provider,
        )
        
        # 4. 解析 v2 结果
        responses_list = []
        extracted_bidder_name = bidder_name
        
        if isinstance(result.data, dict):
            # 检查 schema_version
            schema_version = result.data.get("schema_version", "unknown")
            logger.info(f"BidResponseService: v2 schema_version={schema_version}")
            
            if schema_version != "bid_response_v2":
                logger.warning(f"BidResponseService: Expected v2 schema but got {schema_version}")
            
            responses_list = result.data.get("responses", [])
            logger.info(f"BidResponseService: v2 parsed responses_list length={len(responses_list)}")
            
            # 诊断：打印前3个response的简要信息
            for idx, resp in enumerate(responses_list[:3]):
                logger.info(f"BidResponseService: v2 response[{idx}]: dimension={resp.get('dimension')}, " +
                           f"type={resp.get('response_type')}, " +
                           f"has_normalized={bool(resp.get('normalized_fields_json'))}, " +
                           f"has_segment_ids={bool(resp.get('evidence_segment_ids'))}")
        else:
            logger.warning(f"BidResponseService: unexpected data format, type={type(result.data)}")
        
        if not isinstance(responses_list, list):
            logger.error(f"BidResponseService: responses not list, type={type(responses_list)}")
            responses_list = []
        
        # 5. 预取所有 segment_ids
        all_segment_ids = []
        for resp in responses_list:
            all_segment_ids.extend(resp.get("evidence_segment_ids", []))
        
        logger.info(f"BidResponseService: prefetching {len(set(all_segment_ids))} unique segments")
        seg_map = self._prefetch_doc_segments(all_segment_ids)
        logger.info(f"BidResponseService: fetched {len(seg_map)} segments from database")
        
        # 6. 落库到 tender_bid_response_items (v2 字段)
        added_count = 0
        for resp in responses_list:
            response_id = resp.get("response_id", str(uuid.uuid4()))
            db_id = str(uuid.uuid4())
            
            # v1 字段
            extracted_value_json = resp.get("extracted_value_json", {})
            evidence_chunk_ids = resp.get("evidence_chunk_ids", [])
            
            # v2 新字段
            normalized_fields_json = resp.get("normalized_fields_json", {})
            evidence_segment_ids = resp.get("evidence_segment_ids", [])
            
            # 兼容性处理
            if not evidence_chunk_ids and evidence_segment_ids:
                evidence_chunk_ids = evidence_segment_ids
            elif not evidence_segment_ids and evidence_chunk_ids:
                evidence_segment_ids = evidence_chunk_ids
            
            # 组装 evidence_json
            evidence_json = self._build_evidence_json_from_segments(evidence_segment_ids, seg_map)
            
            # 插入数据库
            import json
            self.dao._execute("""
                INSERT INTO tender_bid_response_items (
                    id, project_id, bidder_name, dimension, response_type,
                    response_text, extracted_value_json, evidence_chunk_ids,
                    normalized_fields_json, evidence_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::text[], %s::jsonb, %s::jsonb)
            """, (
                db_id,
                project_id,
                extracted_bidder_name,
                resp.get("dimension", "other"),
                resp.get("response_type", "text"),
                resp.get("response_text", ""),
                json.dumps(extracted_value_json) if extracted_value_json else '{}',
                evidence_chunk_ids,
                json.dumps(normalized_fields_json) if normalized_fields_json else '{}',
                json.dumps(evidence_json) if evidence_json else None,
            ))
            added_count += 1
        
        logger.info(f"BidResponseService: extract_bid_response_v2 done responses={len(responses_list)}, added={added_count}")
        
        return {
            "bidder_name": extracted_bidder_name,
            "responses": responses_list,
            "added_count": added_count,
            "schema_version": "bid_response_v2"
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

