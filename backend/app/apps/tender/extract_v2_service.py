"""
新抽取服务 (v2) - Step 3
基于平台 ExtractionEngine 的项目信息/风险抽取
"""
import logging
from typing import Any, Dict, List, Optional

from psycopg_pool import ConnectionPool

from app.platform.extraction.engine import ExtractionEngine
from app.platform.retrieval.facade import RetrievalFacade
from app.services.embedding_provider_store import get_embedding_store
from .extraction_specs.project_info_v2 import build_project_info_spec
from .extraction_specs.risks_v2 import build_risks_spec

logger = logging.getLogger(__name__)


class ExtractV2Service:
    """新抽取服务 - 使用平台 ExtractionEngine"""
    
    def __init__(self, pool: ConnectionPool, llm_orchestrator: Any = None):
        self.pool = pool
        self.retriever = RetrievalFacade(pool)
        self.llm = llm_orchestrator
        self.engine = ExtractionEngine()
    
    async def extract_project_info_v2(
        self,
        project_id: str,
        model_id: Optional[str],
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        抽取项目信息 (v2) - 使用平台 ExtractionEngine
        
        Returns:
            {
                "data": {...},
                "evidence_chunk_ids": [...],
                "evidence_spans": [...],
                "retrieval_trace": {...}
            }
        """
        logger.info(f"ExtractV2: extract_project_info start project_id={project_id}")
        
        # 1. 获取 embedding provider
        embedding_provider = get_embedding_store().get_default()
        if not embedding_provider:
            raise ValueError("No embedding provider configured")
        
        # 2. 构建 spec
        spec = build_project_info_spec()
        
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
        
        logger.info(
            f"ExtractV2: extract_project_info done "
            f"evidence={len(result.evidence_chunk_ids)} "
            f"tech_params={len(result.data.get('technicalParameters', []))} "
            f"biz_terms={len(result.data.get('businessTerms', []))} "
            f"scoring_items={len(result.data.get('scoringCriteria', {}).get('items', []))}"
        )
        
        # 4. 返回结果（保持接口兼容）
        return {
            "data": result.data,
            "evidence_chunk_ids": result.evidence_chunk_ids,
            "evidence_spans": result.evidence_spans,
            "retrieval_trace": result.retrieval_trace.__dict__ if result.retrieval_trace else {}
        }
    
    async def extract_risks_v2(
        self,
        project_id: str,
        model_id: Optional[str],
        run_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        识别风险 (v2) - 使用平台 ExtractionEngine
        
        Returns:
            [
                {
                    "risk_type": "...",
                    "title": "...",
                    "description": "...",
                    "suggestion": "...",
                    "severity": "high|medium|low",
                    "tags": [...],
                    "evidence_chunk_ids": [...],
                    "evidence_spans": [...]
                }
            ]
        """
        logger.info(f"ExtractV2: extract_risks start project_id={project_id}")
        
        # 1. 获取 embedding provider
        embedding_provider = get_embedding_store().get_default()
        if not embedding_provider:
            raise ValueError("No embedding provider configured")
        
        # 2. 构建 spec
        spec = build_risks_spec()
        
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
        
        # 4. 解析结果为风险列表
        # result.data 可能直接是 list，或者在某个 key 下
        if isinstance(result.data, list):
            arr = result.data
        elif isinstance(result.data, dict) and "risks" in result.data:
            arr = result.data["risks"]
        else:
            # 尝试直接从 raw output 解析
            logger.warning(f"Unexpected risks data format: {type(result.data)}")
            arr = []
        
        if not isinstance(arr, list):
            logger.error(f"ExtractV2: risk output not list, type={type(arr)}")
            arr = []
        
        # 5. 为每个风险补充 evidence_spans（如果还没有）
        for risk in arr:
            if "evidence_spans" not in risk or not risk["evidence_spans"]:
                risk["evidence_spans"] = result.evidence_spans
        
        logger.info(f"ExtractV2: extract_risks done risks={len(arr)}")
        
        return arr
    
    def _generate_evidence_spans(
        self,
        chunks: List,
        evidence_chunk_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        生成 evidence_spans（基于 meta.page_no）
        此方法保留用于向后兼容，但新代码应使用 ExtractionEngine 内置方法
        
        Returns:
            [
                {
                    "source": "asset_id or doc_version_id",
                    "page_no": 5,
                    "snippet": "证据片段..."
                }
            ]
        """
        spans = []
        chunk_map = {c.chunk_id: c for c in chunks}
        
        for chunk_id in evidence_chunk_ids:
            chunk = chunk_map.get(chunk_id)
            if not chunk:
                continue
            
            meta = chunk.meta or {}
            page_no = meta.get("page_no") or meta.get("chunk_position", 0)
            doc_version_id = meta.get("doc_version_id", "")
            
            spans.append({
                "source": doc_version_id,
                "page_no": page_no,
                "snippet": chunk.text[:200]  # 只取前 200 字符作为片段
            })
        
        return spans
    

