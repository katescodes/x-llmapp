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
from .extraction_specs.directory_v2 import build_directory_spec_async

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
        
        ⚠️ V3 版本：六大类招标信息抽取（合并版）
        
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
            # 从环境变量读取是否启用并行
            import os
            parallel_enabled = os.getenv("EXTRACT_PROJECT_INFO_PARALLEL", "false").lower() in ("true", "1", "yes")
            
            return await self._extract_project_info_staged(
                project_id=project_id,
                model_id=model_id,
                run_id=run_id,
                embedding_provider=embedding_provider,
                parallel=parallel_enabled,
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
            
            # 4. 返回结果（V3结构：顶层直接是六大类）
            return {
                "schema_version": "tender_info_v3",
                **result.data,  # 展开六大类
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
        parallel: bool = False,
    ) -> Dict[str, Any]:
        """
        六阶段顺序抽取项目信息（V3版本 - 合并版）
        
        Stage 1: project_overview (项目概览 - 含范围、进度、保证金)
        Stage 2: bidder_qualification (投标人资格)
        Stage 3: evaluation_and_scoring (评审与评分)
        Stage 4: business_terms (商务条款)
        Stage 5: technical_requirements (技术要求)
        Stage 6: document_preparation (文件编制)
        
        Args:
            parallel: 是否并行执行所有Stage（默认False保持串行）
        """
        import json
        import os
        from app.works.tender.extraction_specs.project_info_v2 import build_project_info_spec_async
        
        # 从环境变量读取是否启用并行
        parallel_enabled = os.getenv("EXTRACT_PROJECT_INFO_PARALLEL", "false").lower() in ("true", "1", "yes")
        parallel = parallel or parallel_enabled
        
        mode = "PARALLEL" if parallel else "SERIAL"
        logger.info(f"ExtractV2: Starting {mode} extraction (V3 - 6 stages) for project={project_id}")
        
        # 构建统一的 spec（从 project_info 模块加载）
        spec = await build_project_info_spec_async(self.pool)
        
        # 定义六个阶段
        stages = [
            {"stage": 1, "name": "项目概览", "key": "project_overview"},
            {"stage": 2, "name": "投标人资格", "key": "bidder_qualification"},
            {"stage": 3, "name": "评审与评分", "key": "evaluation_and_scoring"},
            {"stage": 4, "name": "商务条款", "key": "business_terms"},
            {"stage": 5, "name": "技术要求", "key": "technical_requirements"},
            {"stage": 6, "name": "文件编制", "key": "document_preparation"},
        ]
        
        # 存储各阶段结果
        stage_results = {}
        all_evidence_chunk_ids = set()
        all_evidence_spans = []
        all_traces = []
        
        if parallel:
            # 并行执行所有Stage
            return await self._extract_stages_parallel(
                stages, spec, project_id, model_id, run_id, embedding_provider,
                stage_results, all_evidence_chunk_ids, all_evidence_spans, all_traces
            )
        
        # 顺序执行六个阶段
        for stage_info in stages:
            stage_num = stage_info["stage"]
            stage_name = stage_info["name"]
            stage_key = stage_info["key"]
            
            logger.info(f"ExtractV2: Executing Stage {stage_num}/6 - {stage_name}")
            
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
                    progress = 0.05 + (stage_num - 1) * 0.15  # Stage 1: 0.05, Stage 2: 0.20, ..., Stage 6: 0.80
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
                    f"ExtractV2: Stage {stage_num}/6 done - "
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
                    progress = 0.05 + stage_num * 0.15  # Stage 1完成: 0.20, ..., Stage 6: 0.95
                    self.dao.update_run(run_id, "running", progress=progress, message=f"{stage_name}已完成")
                
                logger.info(f"ExtractV2: Stage {stage_num}/6 incremental update done")
                
            except Exception as e:
                logger.error(f"ExtractV2: Stage {stage_num}/6 failed: {e}", exc_info=True)
                # 失败时设置默认值，但不影响其他阶段
                stage_results[stage_key] = {}
        
        # 合并所有阶段结果（V3结构）
        final_data = {
            "schema_version": "tender_info_v3",
            **{stage["key"]: stage_results.get(stage["key"], {}) for stage in stages}
        }
        
        logger.info(
            f"ExtractV2: STAGED extraction (V3) completed - "
            f"stages_completed={len(stage_results)}/6"
        )
        
        # ❌ 已移除：Step 2.1 追加调用 requirements 抽取
        # 原因：与单独的"招标要求提取"功能重复
        # 现在用户需要单独点击"招标要求提取"按钮来生成 tender_requirements
        # 这样职责更清晰，避免资源浪费
        
        # 返回完整结果
        return {
            **final_data,  # 直接展开六大类到顶层
            "evidence_chunk_ids": list(all_evidence_chunk_ids),
            "evidence_spans": all_evidence_spans,
            "retrieval_trace": {
                "mode": "staged_v3",
                "stages": all_traces
            }
        }
    
    # extract_risks_v2 已删除，请使用 extract_requirements_v1
    # risks模块已废弃，统一使用requirements模块提取招标要求
    
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
            module_name="requirements_v1",  # 传递 module_name 用于 max_tokens 设置
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
            from psycopg.types.json import Json
            
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    for req in requirements:
                        # 处理 JSONB 字段 - 无论是 dict 还是 None 都需要正确处理
                        value_schema = req.get("value_schema_json")
                        if value_schema is not None:
                            if isinstance(value_schema, dict):
                                value_schema = Json(value_schema)
                            # 如果是其他类型（如字符串），尝试解析为dict再包装
                            elif isinstance(value_schema, str):
                                import json
                                try:
                                    value_schema = Json(json.loads(value_schema))
                                except:
                                    value_schema = None  # 解析失败则设为None
                        
                        # Step 2: 推断路由字段（eval_method、must_reject 等）
                        eval_method, must_reject, expected_evidence, rubric, weight = self._infer_routing_fields(req)
                        
                        # 处理 JSONB 字段
                        expected_evidence_json = Json(expected_evidence) if expected_evidence else None
                        rubric_json = Json(rubric) if rubric else None
                        
                        cur.execute("""
                            INSERT INTO tender_requirements (
                                id, project_id, requirement_id, dimension, req_type,
                                requirement_text, is_hard, allow_deviation, 
                                value_schema_json, evidence_chunk_ids,
                                eval_method, must_reject, expected_evidence_json, rubric_json, weight
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            str(uuid.uuid4()),
                            project_id,
                            req.get("requirement_id"),
                            req.get("dimension"),
                            req.get("req_type"),
                            req.get("requirement_text"),
                            req.get("is_hard", False),
                            req.get("allow_deviation", False),
                            value_schema,  # JSONB - 已包装或为None
                            req.get("evidence_chunk_ids", []),
                            eval_method,
                            must_reject,
                            expected_evidence_json,
                            rubric_json,
                            weight,
                        ))
                    conn.commit()
            
            logger.info(f"ExtractV2: Saved {len(requirements)} requirements to DB")
        
        # 返回统计信息（dict格式）
        return {
            "count": len(requirements),
            "requirements": requirements
        }
    
    def _infer_routing_fields(self, req: Dict[str, Any]) -> tuple:
        """
        推断路由字段（Step 2）
        
        根据 requirement 的特征推断 eval_method、must_reject 等字段
        
        Returns:
            (eval_method, must_reject, expected_evidence_json, rubric_json, weight)
        """
        dimension = req.get("dimension", "")
        req_type = req.get("req_type", "")
        requirement_text = req.get("requirement_text", "")
        is_hard = req.get("is_hard", False)
        value_schema = req.get("value_schema_json", {})
        
        # 默认值
        eval_method = "PRESENCE"  # 默认为存在性检查
        must_reject = False
        expected_evidence = None
        rubric = None
        weight = 1.0
        
        # 1. 根据 dimension 和 req_type 推断 eval_method
        if dimension == "qualification":
            # 资格类多为存在性/有效性检查
            if "营业执照" in requirement_text or "资质证书" in requirement_text or "许可证" in requirement_text:
                eval_method = "VALIDITY"
                expected_evidence = {"doc_types": ["license", "certificate"], "fields": ["expire_date", "scope"]}
            elif "业绩" in requirement_text or "项目经验" in requirement_text:
                eval_method = "VALIDITY"
                expected_evidence = {"doc_types": ["performance"], "fields": ["project_name", "contract_amount", "completion_date"]}
            else:
                eval_method = "PRESENCE"
        
        elif dimension == "price":
            # 价格类多为数值比较
            eval_method = "NUMERIC"
            if value_schema and isinstance(value_schema, dict):
                expected_evidence = {
                    "type": "numeric",
                    "constraints": value_schema
                }
        
        elif dimension == "technical":
            # 技术类：参数表为 TABLE_COMPARE，评分点为 SEMANTIC
            if req_type == "scoring":
                eval_method = "SEMANTIC"
                # 提取评分细则作为 rubric
                score = self._extract_score(requirement_text)
                rubric = {
                    "criteria": requirement_text,
                    "scoring_method": "LLM",
                    "max_points": score
                }
            elif "参数表" in requirement_text or "规格表" in requirement_text:
                eval_method = "TABLE_COMPARE"
            elif ("参数" in requirement_text or "规格" in requirement_text or "指标" in requirement_text or
                  "不低于" in requirement_text or "不超过" in requirement_text or "≥" in requirement_text or "≤" in requirement_text):
                # 包含数值比较关键词，使用 NUMERIC
                eval_method = "NUMERIC"
            elif "偏离" in requirement_text and "不允许" in requirement_text:
                eval_method = "EXACT_MATCH"
            else:
                eval_method = "PRESENCE"
        
        elif dimension == "business":
            # 商务类：工期/质保/付款等为数值检查，评分点为语义
            if req_type == "scoring":
                eval_method = "SEMANTIC"
                score = self._extract_score(requirement_text)
                rubric = {
                    "criteria": requirement_text,
                    "scoring_method": "LLM",
                    "max_points": score
                }
            elif "工期" in requirement_text or "质保" in requirement_text or "付款" in requirement_text:
                eval_method = "NUMERIC"
            else:
                eval_method = "PRESENCE"
        
        elif dimension == "doc_structure":
            # 文档结构类多为存在性检查
            eval_method = "PRESENCE"
        
        # 2. 根据 is_hard 和 req_type 推断 must_reject
        if is_hard and req_type in ("threshold", "must_provide", "must_not_deviate"):
            must_reject = True
        
        # 3. 权重：评分项权重较高
        if req_type == "scoring":
            score = self._extract_score(requirement_text)
            weight = score if score else 5.0
        elif must_reject:
            weight = 10.0  # 必须项权重最高
        
        return eval_method, must_reject, expected_evidence, rubric, weight
    
    def _extract_score(self, text: str) -> Optional[float]:
        """从文本中提取分值"""
        import re
        # 匹配"XX分"、"X-XX分"、"最多XX分"、"不超过XX分"等模式
        patterns = [
            r'最多\s*(\d+(?:\.\d+)?)\s*分',
            r'不超过\s*(\d+(?:\.\d+)?)\s*分',
            r'(?:得|为)\s*(\d+(?:\.\d+)?)\s*分',
            r'(\d+(?:\.\d+)?)\s*分',
            r'(\d+(?:\.\d+)?)\s*points?',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return float(match.group(1))
                except:
                    pass
        return None
    
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
        spec = await build_directory_spec_async(self.pool)
        
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
    
    async def _extract_stages_parallel(
        self,
        stages: List[Dict],
        spec: Any,
        project_id: str,
        model_id: Optional[str],
        run_id: Optional[str],
        embedding_provider: str,
        stage_results: Dict,
        all_evidence_chunk_ids: set,
        all_evidence_spans: List,
        all_traces: List,
    ) -> Dict[str, Any]:
        """
        并行执行所有Stage（6个Stage同时执行）
        
        实时更新message字段，展示所有正在进行的Stage
        """
        import json
        import asyncio
        from app.platform.extraction.parallel import ParallelExtractor, ParallelExtractionTask
        import time
        
        parallel_start = time.time()
        logger.info(f"[PARALLEL_TIMING] ========== PARALLEL EXTRACTION START at {parallel_start:.3f} ==========")
        logger.info(f"ExtractV2: Starting PARALLEL extraction with {len(stages)} stages")
        
        # 创建并行任务
        tasks = []
        for stage_info in stages:
            task = ParallelExtractionTask(
                task_id=f"stage_{stage_info['stage']}",
                spec=spec,
                project_id=project_id,
                stage=stage_info['stage'],
                stage_name=stage_info['name'],
                module_name="project_info",
            )
            tasks.append(task)
        
        # 跟踪正在执行的Stage
        active_stages = set()
        completed_stages = set()
        
        def update_progress_message():
            """更新进度消息，显示所有活跃的Stage"""
            if run_id:
                active_names = [stages[s-1]['name'] for s in sorted(active_stages)]
                completed_count = len(completed_stages)
                total = len(stages)
                progress = completed_count / total
                
                if active_names:
                    # 构建消息：正在抽取：项目概览、投标人资格、评审与评分...
                    msg = f"正在抽取：{('、').join(active_names)}"
                    if completed_count > 0:
                        msg += f" ({completed_count}/{total}已完成)"
                else:
                    msg = f"并行抽取完成 ({completed_count}/{total})"
                
                self.dao.update_run(run_id, "running", progress=progress, message=msg)
                logger.info(f"[ParallelExtract] {msg}")
        
        def on_task_start(stage_num: int):
            """任务开始回调"""
            active_stages.add(stage_num)
            update_progress_message()
        
        def on_task_complete(stage_num: int):
            """任务完成回调"""
            if stage_num in active_stages:
                active_stages.remove(stage_num)
            completed_stages.add(stage_num)
            update_progress_message()
        
        # 创建并行抽取器
        extractor = ParallelExtractor(max_concurrent=6)  # 6个Stage并发
        
        # 包装执行函数以添加回调
        async def execute_with_callbacks(task: ParallelExtractionTask):
            """执行单个任务并触发回调"""
            import time
            stage_num = task.stage
            stage_name = task.stage_name
            
            # 记录精确开始时间
            task_start = time.time()
            logger.info(f"[PARALLEL_TIMING] Stage {stage_num} ({stage_name}) START at {task_start:.3f}")
            
            # 开始回调
            on_task_start(stage_num)
            
            try:
                # 执行抽取
                result = await self.engine.run(
                    spec=task.spec,
                    retriever=self.retriever,
                    llm=self.llm,
                    project_id=task.project_id,
                    model_id=model_id,
                    run_id=run_id,
                    embedding_provider=embedding_provider,
                    stage=task.stage,
                    stage_name=task.stage_name,
                    module_name=task.module_name,
                )
                
                # 记录精确完成时间
                task_end = time.time()
                duration = task_end - task_start
                logger.info(f"[PARALLEL_TIMING] Stage {stage_num} ({stage_name}) END at {task_end:.3f}, duration={duration:.2f}s")
                
                # 完成回调
                on_task_complete(stage_num)
                
                return result
                
            except Exception as e:
                task_end = time.time()
                duration = task_end - task_start
                logger.error(f"[PARALLEL_TIMING] Stage {stage_num} ({stage_name}) FAILED at {task_end:.3f}, duration={duration:.2f}s, error={e}", exc_info=True)
                on_task_complete(stage_num)
                raise
        
        # 并行执行所有任务
        try:
            results = await asyncio.gather(*[execute_with_callbacks(task) for task in tasks], return_exceptions=True)
            
            # 处理结果
            for idx, result in enumerate(results):
                stage_info = stages[idx]
                stage_key = stage_info['key']
                
                if isinstance(result, Exception):
                    logger.error(f"ExtractV2: Stage {stage_info['stage']} failed: {result}")
                    stage_results[stage_key] = {}
                else:
                    # 提取数据
                    stage_data = result.data.get(stage_key) if isinstance(result.data, dict) else result.data
                    if not stage_data:
                        stage_data = {}
                    
                    stage_results[stage_key] = stage_data
                    
                    # 收集证据
                    all_evidence_chunk_ids.update(result.evidence_chunk_ids)
                    all_evidence_spans.extend(result.evidence_spans)
                    
                    # 收集追踪信息
                    if result.retrieval_trace:
                        all_traces.append({
                            "stage": stage_info['stage'],
                            "name": stage_info['name'],
                            "trace": result.retrieval_trace.__dict__
                        })
                    
                    logger.info(f"ExtractV2: Stage {stage_info['stage']}/6 completed in parallel mode")
            
        except Exception as e:
            logger.error(f"ExtractV2: Parallel extraction failed: {e}", exc_info=True)
            # 失败时设置默认值
            for stage_info in stages:
                if stage_info['key'] not in stage_results:
                    stage_results[stage_info['key']] = {}
        
        # 合并所有阶段结果（V3结构）
        final_data = {
            "schema_version": "tender_info_v3",
            **{stage["key"]: stage_results.get(stage["key"], {}) for stage in stages}
        }
        
        parallel_end = time.time()
        total_duration = parallel_end - parallel_start
        logger.info(f"[PARALLEL_TIMING] ========== PARALLEL EXTRACTION END at {parallel_end:.3f}, TOTAL={total_duration:.2f}s ==========")
        
        logger.info(
            f"ExtractV2: PARALLEL extraction completed - "
            f"stages_completed={len([r for r in results if not isinstance(r, Exception)])}/6"
        )
        
        # ❌ 已移除：追加调用 requirements 抽取
        # 原因：与单独的"招标要求提取"功能重复
        # 现在用户需要单独点击"招标要求提取"按钮来生成 tender_requirements
        
        return {
            "schema_version": "tender_info_v3",
            **final_data,
            "evidence_chunk_ids": list(all_evidence_chunk_ids),
            "evidence_spans": all_evidence_spans,
            "retrieval_trace": all_traces,
        }


