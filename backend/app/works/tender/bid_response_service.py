"""
投标响应要素抽取服务 (v2)

v2 特性:
- 输出 normalized_fields_json (标准化字段集)
- 输出 evidence_segment_ids (文档片段ID)
- 组装 evidence_json (页码+引用片段)
"""
import logging
import uuid
from typing import Any, Dict, List, Optional

from app.platform.extraction.engine import ExtractionEngine
from app.platform.retrieval.facade import RetrievalFacade
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
        """批量预取 doc_segments"""
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
        """截取 quote"""
        if not text:
            return ""
        text = " ".join(text.split())  # 压缩空白
        if len(text) <= limit:
            return text
        return text[:limit] + "..."
    
    def _deduplicate_responses(self, responses: List[Dict]) -> List[Dict]:
        """
        去除重复的响应
        基于response_text的相似度判断
        """
        if not responses:
            return []
        
        unique_responses = []
        seen_texts = set()
        
        for resp in responses:
            resp_text = resp.get("response_text", "").strip()
            # 简化文本用于比较（去除空白和标点）
            normalized_text = "".join(resp_text.split())
            
            # 检查是否与已有响应重复（使用前100个字符作为指纹）
            fingerprint = normalized_text[:100]
            
            if fingerprint and fingerprint not in seen_texts:
                unique_responses.append(resp)
                seen_texts.add(fingerprint)
        
        logger.info(f"BidResponseService: dedup {len(responses)} -> {len(unique_responses)}")
        return unique_responses
    
    def _build_evidence_json_from_segments(
        self, 
        segment_ids: List[str], 
        seg_map: Dict[str, Dict]
    ) -> List[Dict]:
        """从 segment_ids 组装 evidence_json"""
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
    
    async def extract_bid_response(
        self,
        project_id: str,
        bidder_name: str,
        model_id: Optional[str],
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        抽取投标响应要素
        
        特性:
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
        logger.info(f"BidResponseService: extract_bid_response start project_id={project_id}, bidder={bidder_name}")
        
        # 1. 获取 embedding provider
        embedding_provider = get_embedding_store().get_default()
        if not embedding_provider:
            raise ValueError("No embedding provider configured")
        
        # 2. 构建 spec
        from app.works.tender.extraction_specs.bid_response_v2 import build_bid_response_spec_v2_async
        spec = await build_bid_response_spec_v2_async(self.pool)
        
        # 3. 单次调用（暂时接受LLM的输出限制）
        # TODO: 后续可以实现分批提取策略
        print(f"[DEBUG BidResponse] Single extraction call...")
        
        result = await self.engine.run(
            spec=spec,
            retriever=self.retriever,
            llm=self.llm,
            project_id=project_id,
            model_id=model_id,
            run_id=run_id,
            embedding_provider=embedding_provider,
            module_name="bid_response",
        )
        
        # 解析结果
        responses_list = []
        extracted_bidder_name = bidder_name
        
        if isinstance(result.data, dict):
            responses_list = result.data.get("responses", [])
            print(f"[DEBUG BidResponse] Extracted {len(responses_list)} responses")
        
        # 4. 解析结果（保留原有逻辑）
        
        # 诊断：打印原始LLM返回数据
        print(f"[DEBUG BidResponse] result.data type: {type(result.data)}")
        if isinstance(result.data, dict):
            print(f"[DEBUG BidResponse] result.data keys: {list(result.data.keys())}")
            print(f"[DEBUG BidResponse] responses length: {len(result.data.get('responses', []))}")
        
        if isinstance(result.data, dict):
            # 检查 schema_version
            schema_version = result.data.get("schema_version", "unknown")
            logger.info(f"BidResponseService: schema_version={schema_version}")
            
            if schema_version != "bid_response_v2":
                logger.warning(f"BidResponseService: Expected v2 schema but got {schema_version}")
            
            responses_list = result.data.get("responses", [])
            logger.info(f"BidResponseService: parsed responses_list length={len(responses_list)}")
            
            # 诊断：打印所有response的维度分布
            dimension_count = {}
            for resp in responses_list:
                dim = resp.get('dimension', 'unknown')
                dimension_count[dim] = dimension_count.get(dim, 0) + 1
            print(f"[DEBUG BidResponse] Dimension distribution: {dimension_count}")
            
            # 诊断：打印前3个response的简要信息
            for idx, resp in enumerate(responses_list[:3]):
                logger.info(f"BidResponseService: response[{idx}]: dimension={resp.get('dimension')}, " +
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
        
        # 6. 落库到 tender_bid_response_items
        added_count = 0
        for resp in responses_list:
            response_id = resp.get("response_id", str(uuid.uuid4()))
            db_id = str(uuid.uuid4())
            
            # 旧字段（向后兼容）
            extracted_value_json = resp.get("extracted_value_json", {})
            evidence_chunk_ids = resp.get("evidence_chunk_ids", [])
            
            # 新字段
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
        
        logger.info(f"BidResponseService: extract_bid_response done responses={len(responses_list)}, added={added_count}")
        
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
                result = await self.extract_bid_response(
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

