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
        自动填充单个章节（迁移到统一框架）
        
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
        logger.info(f"DeclareExtractV2: autofill_section (unified) start project_id={project_id} node_title={node_title}")
        
        # 委托给统一框架的实现（默认level=3，可根据需要调整）
        result = await self.autofill_section_unified(
            project_id=project_id,
            model_id=model_id,
            node_title=node_title,
            node_level=3,  # 默认层级
            requirements_summary=requirements_summary,
            run_id=run_id,
        )
        
        # 转换返回格式以保持向后兼容
        return {
            "data": result["data"],
            "evidence_chunk_ids": result.get("evidence_chunk_ids", []),
            "evidence_spans": [],  # 统一框架不使用evidence_spans
            "retrieval_trace": result.get("retrieval_trace", {})
        }
    
    async def autofill_section_unified(
        self,
        project_id: str,
        model_id: Optional[str],
        node_title: str,
        node_level: int,
        requirements_summary: str = "",
        requirements_dict: Optional[Dict[str, Any]] = None,  # ✅ 新增：结构化requirements
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        自动填充单个章节（使用统一组件）
        
        Args:
            project_id: 项目ID
            model_id: 模型ID
            node_title: 章节标题
            node_level: 章节层级
            requirements_summary: 申报要求摘要
            run_id: 运行记录ID
        
        Returns:
            {
                "data": {"content_md": "...", "confidence": "...", ...},
                "evidence_chunk_ids": [...],
                "quality_metrics": {...}
            }
        """
        from app.services.generation import (
            DocumentRetriever,
            RetrievalContext,
            PromptBuilder,
            PromptContext,
            ContentGenerator,
            GenerationContext,
            QualityAssessor
        )
        from app.services.dao.declare_dao import DeclareDAO
        
        logger.info(f"DeclareExtractV2: autofill_section_unified start project_id={project_id} node_title={node_title}")
        
        # Step 1: 获取项目信息
        dao = DeclareDAO(self.pool)
        proj = dao.get_project(project_id)
        if not proj:
            raise ValueError(f"项目不存在: {project_id}")
        
        kb_id = proj.get("kb_id")
        if not kb_id:
            raise ValueError(f"项目未绑定知识库: {project_id}")
        
        # ✅ 优先使用结构化的requirements_dict，否则使用旧的requirements_summary
        if requirements_dict is None:
            requirements_dict = {}
        if not requirements_dict and requirements_summary:
            requirements_dict = {"summary": requirements_summary}
        
        # 获取节点元数据（包含notes等信息）
        section_metadata = {}
        try:
            # 从活跃目录中查找该节点
            nodes = dao.get_active_directory_nodes(project_id)
            for node in nodes:
                if node.get("title") == node_title and node.get("level") == node_level:
                    meta_json = node.get("meta_json", {})
                    if isinstance(meta_json, dict):
                        section_metadata = meta_json
                    break
            logger.info(f"DeclareExtractV2: section_metadata={section_metadata}")
        except Exception as e:
            logger.warning(f"DeclareExtractV2: Failed to get section metadata: {e}")
        
        # Step 2: 检索相关资料（使用统一组件）
        retriever = DocumentRetriever(self.pool)
        retrieval_context = RetrievalContext(
            kb_id=kb_id,
            section_title=node_title,
            section_level=node_level,
            document_type="declare",
            requirements=requirements_dict
        )
        retrieval_result = await retriever.retrieve(retrieval_context, top_k=10)
        
        # 🔍 DEBUG: 检查检索结果
        logger.info(f"[DEBUG] 检索结果: {len(retrieval_result.chunks)} 个chunk")
        if retrieval_result.chunks:
            first_chunk = retrieval_result.chunks[0]
            logger.info(f"[DEBUG] 第一个chunk内容: {first_chunk.get('text', '')[:200]}")
            logger.info(f"[DEBUG] has_relevant: {retrieval_result.has_relevant}")
        else:
            logger.warning(f"[DEBUG] ⚠️  检索结果为空！")
        
        # Step 3: 构建Prompt（使用统一组件）
        prompt_builder = PromptBuilder()
        prompt_context = PromptContext(
            document_type="declare",
            section_title=node_title,
            section_level=node_level,
            project_info={},  # Declare一般不需要project_info
            requirements=requirements_dict,
            retrieval_result=retrieval_result,
            section_metadata=section_metadata  # 传递章节元数据（包含notes）
        )
        prompt = prompt_builder.build(prompt_context)
        
        # Step 4: 生成内容（使用统一组件）
        generator = ContentGenerator(self.llm)
        gen_context = GenerationContext(
            document_type="declare",
            section_title=node_title,
            prompt=prompt,
            model_id=model_id
        )
        generation_result = await generator.generate(gen_context)
        
        # Step 5: 评估质量（使用统一组件）
        assessor = QualityAssessor()
        quality_metrics = assessor.assess(
            generation_result,
            retrieval_result,
            node_level
        )
        
        # Step 6: 记录质量指标
        logger.info(
            f"DeclareExtractV2: autofill_section_unified done "
            f"content_length={generation_result.word_count} "
            f"evidence={len(retrieval_result.chunks)} "
            f"quality={quality_metrics.overall_score:.2f}"
        )
        
        return {
            "data": {
                "content_md": generation_result.content,
                "confidence": generation_result.confidence,
                "word_count": generation_result.word_count
            },
            "evidence_chunk_ids": retrieval_result.get_chunk_ids(),
            "quality_metrics": quality_metrics.to_dict(),
            "retrieval_trace": {
                "query_strategy": retrieval_result.retrieval_strategy,
                "chunk_count": len(retrieval_result.chunks),
                "quality_score": retrieval_result.quality_score
            }
        }

