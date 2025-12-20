"""
申报书 V2 抽取服务
基于平台 ExtractionEngine
"""
import logging
from typing import Any, Dict, Optional

from psycopg_pool import ConnectionPool

from app.platform.extraction.engine import ExtractionEngine
from app.platform.retrieval.facade import RetrievalFacade
from app.services.embedding_provider_store import get_embedding_store
from app.works.declare.extraction_specs.requirements_v2 import build_requirements_spec
from app.works.declare.extraction_specs.directory_v2 import build_directory_spec
from app.works.declare.extraction_specs.section_autofill_v2 import build_section_autofill_spec

logger = logging.getLogger(__name__)


class DeclareExtractV2Service:
    """申报书 V2 抽取服务"""
    
    def __init__(self, pool: ConnectionPool, llm_orchestrator: Any = None):
        self.pool = pool
        self.retriever = RetrievalFacade(pool)
        self.llm = llm_orchestrator
        self.engine = ExtractionEngine()
    
    async def extract_requirements(
        self,
        project_id: str,
        model_id: Optional[str],
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        抽取申报要求
        
        Returns:
            {
                "data": {"eligibility_conditions": [...], "materials_required": [...], ...},
                "evidence_chunk_ids": [...],
                "evidence_spans": [...],
                "retrieval_trace": {...}
            }
        """
        logger.info(f"DeclareExtractV2: extract_requirements start project_id={project_id}")
        
        embedding_provider = get_embedding_store().get_default()
        if not embedding_provider:
            raise ValueError("No embedding provider configured")
        
        spec = build_requirements_spec()
        
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
            f"DeclareExtractV2: extract_requirements done "
            f"eligibility_count={len(result.data.get('eligibility_conditions', [])) if isinstance(result.data, dict) else 0} "
            f"evidence={len(result.evidence_chunk_ids)}"
        )
        
        return {
            "data": result.data,
            "evidence_chunk_ids": result.evidence_chunk_ids,
            "evidence_spans": result.evidence_spans,
            "retrieval_trace": result.retrieval_trace.__dict__ if result.retrieval_trace else {}
        }
    
    async def generate_directory(
        self,
        project_id: str,
        model_id: Optional[str],
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        生成申报书目录
        
        Returns:
            {
                "data": {"nodes": [...]},
                "evidence_chunk_ids": [...],
                "evidence_spans": [...],
                "retrieval_trace": {...}
            }
        """
        logger.info(f"DeclareExtractV2: generate_directory start project_id={project_id}")
        
        embedding_provider = get_embedding_store().get_default()
        if not embedding_provider:
            raise ValueError("No embedding provider configured")
        
        spec = build_directory_spec()
        
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
            f"DeclareExtractV2: generate_directory done "
            f"nodes_count={len(result.data.get('nodes', [])) if isinstance(result.data, dict) else 0} "
            f"evidence={len(result.evidence_chunk_ids)}"
        )
        
        return {
            "data": result.data,
            "evidence_chunk_ids": result.evidence_chunk_ids,
            "evidence_spans": result.evidence_spans,
            "retrieval_trace": result.retrieval_trace.__dict__ if result.retrieval_trace else {}
        }
    
    async def autofill_section(
        self,
        project_id: str,
        model_id: Optional[str],
        node_title: str,
        requirements_summary: str = "",
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        自动填充单个章节
        
        Args:
            node_title: 章节标题
            requirements_summary: 申报要求摘要
        
        Returns:
            {
                "data": {"content_md": "...", "summary": "...", ...},
                "evidence_chunk_ids": [...],
                "evidence_spans": [...],
                "retrieval_trace": {...}
            }
        """
        logger.info(f"DeclareExtractV2: autofill_section start project_id={project_id} node_title={node_title}")
        
        embedding_provider = get_embedding_store().get_default()
        if not embedding_provider:
            raise ValueError("No embedding provider configured")
        
        spec = build_section_autofill_spec(node_title, requirements_summary)
        
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
            f"DeclareExtractV2: autofill_section done "
            f"content_length={len(result.data.get('content_md', '')) if isinstance(result.data, dict) else 0} "
            f"evidence={len(result.evidence_chunk_ids)}"
        )
        
        return {
            "data": result.data,
            "evidence_chunk_ids": result.evidence_chunk_ids,
            "evidence_spans": result.evidence_spans,
            "retrieval_trace": result.retrieval_trace.__dict__ if result.retrieval_trace else {}
        }

