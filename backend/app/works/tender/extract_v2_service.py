"""
新抽取服务 (v2) - Step 3
基于平台 ExtractionEngine 的项目信息/风险抽取/目录生成
"""
import logging
from typing import Any, Dict, List, Optional

from psycopg_pool import ConnectionPool

from app.platform.extraction.engine import ExtractionEngine
from app.platform.retrieval.facade import RetrievalFacade
from app.services.embedding_provider_store import get_embedding_store
from .extraction_specs.project_info_v2 import build_project_info_spec
from .extraction_specs.risks_v2 import build_risks_spec
from .extraction_specs.directory_v2 import build_directory_spec

logger = logging.getLogger(__name__)


class ExtractV2Service:
    """新抽取服务 - 使用平台 ExtractionEngine"""
    
    def __init__(self, pool: ConnectionPool, llm_orchestrator: Any = None):
        self.pool = pool
        self.retriever = RetrievalFacade(pool)
        self.llm = llm_orchestrator
        self.engine = ExtractionEngine()
        # 创建DAO用于更新run状态和保存数据
        from app.services.dao.tender_dao import TenderDAO
        self.dao = TenderDAO(pool)
    
    async def extract_project_info_v2(
        self,
        project_id: str,
        model_id: Optional[str],
        run_id: Optional[str] = None,
        use_staged: bool = True,
    ) -> Dict[str, Any]:
        """
        抽取项目信息 (v3) - 九阶段顺序抽取
        
        ⚠️ V3 版本：九大类招标信息抽取
        
        优先从数据库加载最新的prompt模板，如果数据库中没有则使用文件fallback
        
        Args:
            project_id: 项目ID
            model_id: 模型ID
            run_id: 运行ID
            use_staged: 是否使用九阶段抽取（默认True）
        
        Returns:
            {
                "schema_version": "tender_info_v3",
                "project_overview": {...},
                "scope_and_lots": {...},
                "schedule_and_submission": {...},
                "bidder_qualification": {...},
                "evaluation_and_scoring": {...},
                "business_terms": {...},
                "technical_requirements": {...},
                "document_preparation": {...},
                "bid_security": {...},
                "evidence_chunk_ids": [...],
                "evidence_spans": [...],
                "retrieval_trace": {...}
            }
        """
        logger.info(f"ExtractV2: extract_project_info_v3 start project_id={project_id} use_staged={use_staged}")
        
        # 1. 获取 embedding provider
        embedding_provider = get_embedding_store().get_default()
        if not embedding_provider:
            raise ValueError("No embedding provider configured")
        
        # 2. 构建 spec（使用异步版本，支持数据库加载）
        from app.works.tender.extraction_specs.project_info_v2 import build_project_info_spec_async
        
        if use_staged:
            # 使用九阶段抽取（V3版本）
            return await self._extract_project_info_staged(
                project_id=project_id,
                model_id=model_id,
                run_id=run_id,
                embedding_provider=embedding_provider,
            )
        else:
            # 使用原有的一次性抽取（不推荐，返回V3结构）
            spec = await build_project_info_spec_async(self.pool)
            
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
            
            # 调试日志：查看实际返回的数据结构
            logger.info(
                f"ExtractV2: extract_project_info_v3 done "
                f"evidence={len(result.evidence_chunk_ids)} "
                f"data_keys={list(result.data.keys()) if isinstance(result.data, dict) else 'NOT_DICT'} "
                f"data_type={type(result.data).__name__} "
                f"data_empty={not bool(result.data)}"
            )
            
            # 如果 data 是空的，记录警告
            if not result.data or (isinstance(result.data, dict) and not result.data):
                logger.warning(
                    f"ExtractV2: extract_project_info_v3 returned EMPTY data! "
                    f"project_id={project_id} "
                    f"result.data={result.data}"
            )
            
            # 4. 返回结果（V3结构：顶层直接是九大类）
            return {
                "schema_version": "tender_info_v3",
                **result.data,  # 展开九大类
                "evidence_chunk_ids": result.evidence_chunk_ids,
                "evidence_spans": result.evidence_spans,
                "retrieval_trace": result.retrieval_trace.__dict__ if result.retrieval_trace else {}
            }
    
    async def _extract_project_info_staged(
        self,
        project_id: str,
        model_id: Optional[str],
        run_id: Optional[str],
        embedding_provider: str,
    ) -> Dict[str, Any]:
        """
        九阶段顺序抽取项目信息（V3版本）
        
        Stage 1: project_overview (项目概览)
        Stage 2: scope_and_lots (范围与标段)
        Stage 3: schedule_and_submission (进度与递交)
        Stage 4: bidder_qualification (投标人资格)
        Stage 5: evaluation_and_scoring (评审与评分)
        Stage 6: business_terms (商务条款)
        Stage 7: technical_requirements (技术要求)
        Stage 8: document_preparation (文件编制)
        Stage 9: bid_security (保证金与担保)
        """
        import json
        from app.works.tender.extraction_specs.project_info_v2 import build_project_info_spec_async
        
        logger.info(f"ExtractV2: Starting STAGED extraction (V3 - 9 stages) for project={project_id}")
        
        # 构建统一的 spec（从 project_info 模块加载）
        spec = await build_project_info_spec_async(self.pool)
        
        # 定义九个阶段
        stages = [
            {"stage": 1, "name": "项目概览", "key": "project_overview"},
            {"stage": 2, "name": "范围与标段", "key": "scope_and_lots"},
            {"stage": 3, "name": "进度与递交", "key": "schedule_and_submission"},
            {"stage": 4, "name": "投标人资格", "key": "bidder_qualification"},
            {"stage": 5, "name": "评审与评分", "key": "evaluation_and_scoring"},
            {"stage": 6, "name": "商务条款", "key": "business_terms"},
            {"stage": 7, "name": "技术要求", "key": "technical_requirements"},
            {"stage": 8, "name": "文件编制", "key": "document_preparation"},
            {"stage": 9, "name": "保证金与担保", "key": "bid_security"},
        ]
        
        # 存储各阶段结果
        stage_results = {}
        all_evidence_chunk_ids = set()
        all_evidence_spans = []
        all_traces = []
        
        # 顺序执行九个阶段
        for stage_info in stages:
            stage_num = stage_info["stage"]
            stage_name = stage_info["name"]
            stage_key = stage_info["key"]
            
            logger.info(f"ExtractV2: Executing Stage {stage_num}/9 - {stage_name}")
            
            # 构建上下文信息（前序阶段的结果）
            context_info = ""
            if stage_num > 1:
                context_parts = []
                for prev_stage in stages[:stage_num-1]:
                    prev_key = prev_stage["key"]
                    if prev_key in stage_results:
                        context_parts.append(f"{prev_stage['name']}: {json.dumps(stage_results[prev_key], ensure_ascii=False)[:300]}")
                context_info = "\n".join(context_parts)
            
            try:
                # 更新run状态：开始当前阶段
                if run_id:
                    progress = 0.05 + (stage_num - 1) * 0.1  # Stage 1: 0.05, Stage 2: 0.15, ..., Stage 9: 0.85
                    self.dao.update_run(run_id, "running", progress=progress, message=f"正在抽取：{stage_name}...")
                
                # 调用引擎执行当前阶段
                result = await self.engine.run(
                    spec=spec,
                    retriever=self.retriever,
                    llm=self.llm,
                    project_id=project_id,
                    model_id=model_id,
                    run_id=run_id,
                    embedding_provider=embedding_provider,
                    stage=stage_num,
                    stage_name=stage_name,
                    context_info=context_info,
                )
                
                # 提取当前阶段的数据
                stage_data = result.data.get(stage_key) if isinstance(result.data, dict) else result.data
                
                if not stage_data:
                    logger.warning(f"ExtractV2: Stage {stage_num} returned EMPTY data")
                    # 设置默认值
                        stage_data = {}
                
                # 保存当前阶段结果
                stage_results[stage_key] = stage_data
                
                # 收集证据
                all_evidence_chunk_ids.update(result.evidence_chunk_ids)
                all_evidence_spans.extend(result.evidence_spans)
                
                # 收集追踪信息
                if result.retrieval_trace:
                    all_traces.append({
                        "stage": stage_num,
                        "name": stage_name,
                        "trace": result.retrieval_trace.__dict__
                    })
                
                logger.info(
                    f"ExtractV2: Stage {stage_num}/9 done - "
                    f"data_type={type(stage_data).__name__} "
                    f"data_keys={list(stage_data.keys()) if isinstance(stage_data, dict) else 'N/A'} "
                    f"evidence={len(result.evidence_chunk_ids)}"
                )
                
                # ✅ 增量更新：每完成一个阶段就写入数据库
                incremental_data = {
                    "schema_version": "tender_info_v3",
                    **{k: stage_results.get(k, {}) for k in [s["key"] for s in stages]}
                }
                self.dao.upsert_project_info(
                    project_id, 
                    data_json=incremental_data, 
                    evidence_chunk_ids=list(all_evidence_chunk_ids)
                )
                
                # 更新run进度
                if run_id:
                    progress = 0.05 + stage_num * 0.1  # Stage 1完成: 0.15, ..., Stage 9: 0.95
                    self.dao.update_run(run_id, "running", progress=progress, message=f"{stage_name}已完成")
                
                logger.info(f"ExtractV2: Stage {stage_num}/9 incremental update done")
                
            except Exception as e:
                logger.error(f"ExtractV2: Stage {stage_num}/9 failed: {e}", exc_info=True)
                # 失败时设置默认值，但不影响其他阶段
                    stage_results[stage_key] = {}
        
        # 合并所有阶段结果（V3结构）
        final_data = {
            "schema_version": "tender_info_v3",
            **{stage["key"]: stage_results.get(stage["key"], {}) for stage in stages}
        }
        
        logger.info(
            f"ExtractV2: STAGED extraction (V3) completed - "
            f"stages_completed={len(stage_results)}/9"
        )
        
        # ✅ Step 2.1: 追加调用 requirements 抽取（基准条款库）
        try:
            logger.info(f"ExtractV2: Starting requirements extraction for project={project_id}")
            if run_id:
                self.dao.update_run(run_id, "running", progress=0.95, message="正在生成招标要求基准条款库...")
            
            requirements = await self.extract_requirements_v1(
                project_id=project_id,
                model_id=model_id,
                run_id=None,  # 不更新run状态，避免冲突
            )
            
            logger.info(f"ExtractV2: Requirements extraction done - count={len(requirements)}")
        except Exception as e:
            logger.error(f"ExtractV2: Requirements extraction failed: {e}", exc_info=True)
            # 不影响主流程，继续返回
        
        # 返回完整结果
        return {
            **final_data,  # 直接展开九大类到顶层
            "evidence_chunk_ids": list(all_evidence_chunk_ids),
            "evidence_spans": all_evidence_spans,
            "retrieval_trace": {
                "mode": "staged_v3",
                "stages": all_traces
            }
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
    
    async def extract_requirements_v1(
        self,
        project_id: str,
        model_id: Optional[str],
        run_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        抽取招标要求 (v1) - 生成 tender_requirements 基准条款库
        
        从招标文件中抽取结构化的 requirements，用于后续审核
        
        Returns:
            [
                {
                    "requirement_id": "qual_001",
                    "dimension": "qualification",
                    "req_type": "must_provide",
                    "requirement_text": "...",
                    "is_hard": true,
                    "allow_deviation": false,
                    "value_schema_json": {...},
                    "evidence_chunk_ids": [...]
                }
            ]
        """
        logger.info(f"ExtractV2: extract_requirements start project_id={project_id}")
        
        # 1. 获取 embedding provider
        embedding_provider = get_embedding_store().get_default()
        if not embedding_provider:
            raise ValueError("No embedding provider configured")
        
        # 2. 构建 spec
        from app.works.tender.extraction_specs.requirements_v1 import build_requirements_spec_async
        spec = await build_requirements_spec_async(self.pool)
        
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
        
        # 4. 解析结果
        requirements = []
        if isinstance(result.data, dict) and "requirements" in result.data:
            requirements = result.data["requirements"]
        elif isinstance(result.data, list):
            requirements = result.data
        
        logger.info(
            f"ExtractV2: extract_requirements done - "
            f"requirements_count={len(requirements)}"
        )
        
        # 5. 写入数据库
        if requirements:
            import uuid
            
            # 先删除旧的 requirements
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM tender_requirements WHERE project_id = %s",
                        (project_id,)
                    )
                    conn.commit()
            
            # 插入新的 requirements
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    for req in requirements:
                        cur.execute("""
                            INSERT INTO tender_requirements (
                                id, project_id, requirement_id, dimension, req_type,
                                requirement_text, is_hard, allow_deviation, 
                                value_schema_json, evidence_chunk_ids
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            str(uuid.uuid4()),
                            project_id,
                            req.get("requirement_id"),
                            req.get("dimension"),
                            req.get("req_type"),
                            req.get("requirement_text"),
                            req.get("is_hard", False),
                            req.get("allow_deviation", False),
                            req.get("value_schema_json"),  # JSONB
                            req.get("evidence_chunk_ids", []),
                        ))
                    conn.commit()
            
            logger.info(f"ExtractV2: Saved {len(requirements)} requirements to DB")
        
        return requirements
    
    async def generate_directory_v2(
        self,
        project_id: str,
        model_id: Optional[str],
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        生成目录 (v2) - 使用平台 ExtractionEngine
        
        Returns:
            {
                "data": {
                    "nodes": [
                        {
                            "title": "章节标题",
                            "level": 1,
                            "order_no": 1,
                            "parent_ref": "父节点标题",
                            "required": true,
                            "volume": "第一卷",
                            "notes": "说明",
                            "evidence_chunk_ids": [...]
                        }
                    ]
                },
                "evidence_chunk_ids": [...],
                "evidence_spans": [...]
            }
        """
        logger.info(f"ExtractV2: generate_directory start project_id={project_id}")
        
        # 1. 获取 embedding provider
        embedding_provider = get_embedding_store().get_default()
        if not embedding_provider:
            raise ValueError("No embedding provider configured")
        
        # 2. 构建 spec
        spec = build_directory_spec()
        
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
        
        # 4. 验证结果
        if not result.data or not isinstance(result.data, dict):
            logger.error(f"ExtractV2: directory data invalid, type={type(result.data)}")
            raise ValueError("Directory extraction returned invalid data")
        
        nodes = result.data.get("nodes", [])
        if not nodes:
            logger.warning(f"ExtractV2: no directory nodes extracted for project={project_id}")
        
        logger.info(f"ExtractV2: generate_directory done nodes={len(nodes)}")
        
        # 5. 目录增强 - 利用 tender_info_v3 补充必填节点
        try:
            logger.info(f"ExtractV2: Attempting directory augmentation for project={project_id}")
            
            # 读取 tender_project_info
            tender_info = self.dao.get_project_info(project_id)
            if tender_info and tender_info.get("schema_version") == "tender_info_v3":
                from app.works.tender.directory_augment_v1 import augment_directory_from_tender_info_v3
                
                augment_result = augment_directory_from_tender_info_v3(
                    project_id=project_id,
                    pool=self.pool,
                    tender_info=tender_info
                )
                
                logger.info(
                    f"ExtractV2: Directory augmentation done - "
                    f"added={augment_result['added_count']}, "
                    f"titles={augment_result['enhanced_titles'][:5]}"
                )
        except Exception as e:
            logger.warning(f"ExtractV2: Directory augmentation failed (non-fatal): {e}")
        
        # 6. 返回结果
        return {
            "data": result.data,
            "evidence_chunk_ids": result.evidence_chunk_ids,
            "evidence_spans": result.evidence_spans,
            "retrieval_trace": result.retrieval_trace.__dict__ if result.retrieval_trace else {}
        }
    
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
    

