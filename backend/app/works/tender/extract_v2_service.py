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
from .schemas.directory_v2 import build_directory_spec_async

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
    ) -> Dict[str, Any]:
        """
        抽取项目信息 (V3) - 六阶段顺序/并行抽取
        
        使用基于Checklist的P0+P1两阶段提取框架
        
        Args:
            project_id: 项目ID
            model_id: 模型ID
            run_id: 运行ID
        
        Returns:
            {
                "schema_version": "tender_info_v3",
                "project_overview": {...},
                "bidder_qualification": {...},
                "evaluation_and_scoring": {...},
                "business_terms": {...},
                "technical_requirements": {...},
                "document_preparation": {...},
                "evidence_chunk_ids": [...],
                "evidence_spans": [...],
                "retrieval_trace": {...}
            }
        """
        logger.info(f"ExtractV2: extract_project_info_v2 start project_id={project_id}")
        
        # 获取 embedding provider
        embedding_provider = get_embedding_store().get_default()
        if not embedding_provider:
            raise ValueError("No embedding provider configured")
        
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
    
    async def _extract_project_info_staged(
        self,
        project_id: str,
        model_id: Optional[str],
        run_id: Optional[str],
        embedding_provider: str,
        parallel: bool = False,
    ) -> Dict[str, Any]:
        """
        六阶段顺序抽取项目信息（V3版本 - Checklist-based）
        
        ✨ 新方法：基于Checklist的P0+P1两阶段提取框架
        
        Stage 1: project_overview (项目概览 - 含范围、进度、保证金)
        Stage 2: bidder_qualification (投标人资格)
        Stage 3: evaluation_and_scoring (评审与评分)
        Stage 4: business_terms (商务条款)
        Stage 5: technical_requirements (技术要求)
        Stage 6: document_preparation (文件编制)
        
        每个stage采用：
        - P0阶段：基于checklist的结构化提取
        - P1阶段：补充扫描遗漏信息
        - 验证：检查必填字段和证据
        
        Args:
            parallel: 是否并行执行所有Stage（支持最多6个并行）
        """
        import os
        import asyncio
        from app.works.tender.project_info_extractor import ProjectInfoExtractor
        from app.works.tender.tender_context_retriever import TenderContextRetriever
        
        logger.info(
            f"ExtractV2: Starting CHECKLIST-BASED extraction (V3 - 6 stages) "
            f"for project={project_id} parallel={parallel}"
        )
        
        # 定义六个阶段元数据（用于进度展示）
        stages_meta = [
            {"stage": 1, "name": "项目概览", "key": "project_overview"},
            {"stage": 2, "name": "投标人资格", "key": "bidder_qualification"},
            {"stage": 3, "name": "评审与评分", "key": "evaluation_and_scoring"},
            {"stage": 4, "name": "商务条款", "key": "business_terms"},
            {"stage": 5, "name": "技术要求", "key": "technical_requirements"},
            {"stage": 6, "name": "文件编制", "key": "document_preparation"},
        ]
        
        try:
            # ===== 步骤1：统一检索招标文档上下文 =====
            logger.info("Step 1: 检索招标文档上下文（一次性检索）")
            
            if run_id:
                self.dao.update_run(
                    run_id, "running", progress=0.05, 
                    message="正在检索招标文档..."
                )
            
            context_retriever = TenderContextRetriever(self.retriever)
            context_data = await context_retriever.retrieve_tender_context(
                project_id=project_id,
                top_k=150,  # 获取足够多的上下文
                max_context_chunks=100,
                sort_by_position=True,
                filter_contract_clauses=True,  # ✨ 启用合同条款过滤
            )
            
            if context_data.used_chunks == 0:
                raise ValueError(f"未检索到招标文档内容，project_id={project_id}")
            
            logger.info(
                f"上下文检索完成: total={context_data.total_chunks}, "
                f"used={context_data.used_chunks}, "
                f"context_length={len(context_data.context_text)}"
            )
            
            # ===== 步骤2：创建Checklist提取器 =====
            logger.info("Step 2: 初始化Checklist提取器")
            
            extractor = ProjectInfoExtractor(llm=self.llm)
            
            # ===== 步骤3：执行6个stage（支持并行或顺序） =====
            logger.info(f"Step 3: 开始6阶段checklist提取 (parallel={parallel})")
            
            all_stage_results = {}
            all_evidence_ids = set()
            
            if parallel:
                # ===== 并行模式：所有stage同时执行 =====
                logger.info("使用并行模式，所有6个stage同时执行")
                
                # 获取最大并发数
                max_concurrent = int(os.getenv("EXTRACT_MAX_CONCURRENT", "6"))
                logger.info(f"最大并发数: {max_concurrent}")
                
                # 创建信号量限制并发
                semaphore = asyncio.Semaphore(max_concurrent)
                
                async def extract_stage_with_semaphore(stage_meta):
                    async with semaphore:
                        stage_num = stage_meta["stage"]
                        stage_name = stage_meta["name"]
                        stage_key = stage_meta["key"]
                        
                        logger.info(f"=== 开始并行提取 Stage {stage_num}/6: {stage_name} ===")
                        
                        try:
                            stage_result = await extractor.extract_stage(
                                stage=stage_num,
                                context_text=context_data.context_text,
                                segment_id_map=context_data.segment_id_map,
                                model_id=model_id,
                                context_info=None,  # 并行模式下不传递context
                                enable_p1=True
                            )
                            
                            logger.info(
                                f"Stage {stage_num} 完成: "
                                f"fields={len(stage_result['data'])}, "
                                f"evidence={len(stage_result['evidence_segment_ids'])}"
                            )
                            
                            return stage_key, stage_result
                            
                        except Exception as e:
                            logger.error(f"Stage {stage_num} 失败: {e}", exc_info=True)
                            return stage_key, {
                                "data": {},
                                "evidence_segment_ids": [],
                                "p1_supplements_count": 0
                            }
                
                # 并行执行所有stage
                if run_id:
                    self.dao.update_run(
                        run_id, "running", progress=0.10,
                        message="正在并行提取所有阶段..."
                    )
                
                tasks = [extract_stage_with_semaphore(meta) for meta in stages_meta]
                results = await asyncio.gather(*tasks)
                
                # 收集结果
                for stage_key, stage_result in results:
                    all_stage_results[stage_key] = stage_result["data"]
                    all_evidence_ids.update(stage_result["evidence_segment_ids"])
                
                # 更新进度
                if run_id:
                    self.dao.update_run(
                        run_id, "running", progress=0.90,
                        message="所有阶段提取完成，正在保存..."
                    )
                
            else:
                # ===== 顺序模式：一个接一个执行（支持context传递） =====
                logger.info("使用顺序模式，stage依次执行")
                context_info = None  # 用于传递前序stage的结果
                
                for stage_meta in stages_meta:
                    stage_num = stage_meta["stage"]
                    stage_name = stage_meta["name"]
                    stage_key = stage_meta["key"]
                    
                    logger.info(f"=== Extracting Stage {stage_num}/6: {stage_name} ===")
                    
                    # 更新进度
                    if run_id:
                        progress = 0.05 + (stage_num - 1) * 0.15  # 0.05, 0.20, 0.35, 0.50, 0.65, 0.80
                        self.dao.update_run(
                            run_id, "running", progress=progress,
                            message=f"正在抽取：{stage_name} (P0+P1)..."
                        )
                    
                    try:
                        # 调用extractor提取单个stage
                        stage_result = await extractor.extract_stage(
                            stage=stage_num,
                            context_text=context_data.context_text,
                            segment_id_map=context_data.segment_id_map,
                            model_id=model_id,
                            context_info=context_info,  # 传递前序stage的结果
                            enable_p1=True  # 启用P1补充扫描
                        )
                        
                        # 保存结果
                        all_stage_results[stage_key] = stage_result["data"]
                        all_evidence_ids.update(stage_result["evidence_segment_ids"])
                        
                        # 传递context给下一个stage
                        if context_info is None:
                            context_info = {}
                        context_info[stage_key] = stage_result["data"]
                        
                        logger.info(
                            f"Stage {stage_num} complete: "
                            f"fields={len(stage_result['data'])}, "
                            f"evidence={len(stage_result['evidence_segment_ids'])}, "
                            f"p1_supplements={stage_result['p1_supplements_count']}"
                        )
                        
                        # ✅ 增量保存到数据库（顺序模式）
                        incremental_data = {
                            "schema_version": "tender_info_v3",
                            **{k: all_stage_results.get(k, {}) for k in [s["key"] for s in stages_meta]}
                        }
                        self.dao.upsert_project_info(
                            project_id,
                            data_json=incremental_data,
                            evidence_chunk_ids=list(all_evidence_ids)
                        )
                        
                        # 更新完成进度
                        if run_id:
                            progress = 0.05 + stage_num * 0.15  # 0.20, 0.35, 0.50, 0.65, 0.80, 0.95
                            self.dao.update_run(
                                run_id, "running", progress=progress,
                                message=f"{stage_name}已完成"
                            )
                        
                    except Exception as e:
                        logger.error(f"Stage {stage_num} failed: {e}", exc_info=True)
                        # 失败时设置空数据，继续执行后续stage
                        all_stage_results[stage_key] = {}
                        
                        # 记录错误但不中断流程
                        if run_id:
                            self.dao.update_run(
                                run_id, "running",
                                message=f"{stage_name}提取失败，继续下一阶段"
                            )
            
            # ===== 步骤4：最终保存（并行模式需要在这里保存） =====
            if parallel:
                incremental_data = {
                    "schema_version": "tender_info_v3",
                    **{k: all_stage_results.get(k, {}) for k in [s["key"] for s in stages_meta]}
                }
                self.dao.upsert_project_info(
                    project_id,
                    data_json=incremental_data,
                    evidence_chunk_ids=list(all_evidence_ids)
                )
            
            # ===== 步骤5：验证提取结果 =====
            logger.info("Step 5: 验证提取结果")
            
            final_result = {
                "schema_version": "tender_info_v3",
                **all_stage_results,
                "evidence_chunk_ids": list(all_evidence_ids)
            }
            
            validation_report = extractor.validate_result(final_result)
            
            if not validation_report["is_valid"]:
                logger.warning(
                    f"Validation failed: errors={validation_report['errors']}"
                )
            
            if validation_report["warnings"]:
                logger.warning(
                    f"Validation warnings: {validation_report['warnings']}"
                )
            
            # ===== 步骤6：构建最终返回结果 =====
            logger.info(
                f"ExtractV2: CHECKLIST-BASED extraction complete - "
                f"mode={'parallel' if parallel else 'sequential'}, "
                f"stages_completed={len([r for r in all_stage_results.values() if r])}/6, "
                f"evidence_segments={len(all_evidence_ids)}"
            )
            
            # 构建evidence_spans（兼容旧格式）
            evidence_spans = []
            for seg_id in list(all_evidence_ids)[:50]:  # 限制数量
                chunk = context_data.segment_id_map.get(seg_id)
                if chunk:
                    meta = chunk.meta or {}
                    evidence_spans.append({
                        "source": meta.get("doc_version_id", ""),
                        "page_no": meta.get("page_no", 0),
                        "snippet": chunk.text[:200]
                    })
            
            # ===== 步骤6：构建完整的结果（确保包含所有6个stage） =====
            final_result = {
                "schema_version": "tender_info_v3",
                # 明确列出所有6个stage，即使某些为空
                "project_overview": all_stage_results.get("project_overview", {}),
                "bidder_qualification": all_stage_results.get("bidder_qualification", {}),
                "evaluation_and_scoring": all_stage_results.get("evaluation_and_scoring", {}),
                "business_terms": all_stage_results.get("business_terms", {}),
                "technical_requirements": all_stage_results.get("technical_requirements", {}),
                "document_preparation": all_stage_results.get("document_preparation", {}),
                "evidence_chunk_ids": list(all_evidence_ids),
                "evidence_spans": evidence_spans,
                "retrieval_trace": {
                    "mode": "checklist_based_v3",
                    "method": "P0+P1",
                    "stages": len(all_stage_results),
                    "validation": validation_report
                }
            }
            
            # ===== 步骤7：最终确认保存（确保数据完整） =====
            # 最后再保存一次，确保所有stage的数据都已保存
            logger.info("最终保存项目信息到数据库...")
            data_to_save_final = {
                "schema_version": "tender_info_v3",
                "project_overview": all_stage_results.get("project_overview", {}),
                "bidder_qualification": all_stage_results.get("bidder_qualification", {}),
                "evaluation_and_scoring": all_stage_results.get("evaluation_and_scoring", {}),
                "business_terms": all_stage_results.get("business_terms", {}),
                "technical_requirements": all_stage_results.get("technical_requirements", {}),
                "document_preparation": all_stage_results.get("document_preparation", {}),
            }
            self.dao.upsert_project_info(
                project_id,
                data_json=data_to_save_final,
                evidence_chunk_ids=list(all_evidence_ids)
            )
            logger.info("项目信息已保存到数据库")
            
            # ===== 步骤8：更新run进度为接近完成 =====
            if run_id:
                logger.info(f"更新run进度: run_id={run_id}")
                self.dao.update_run(
                    run_id, 
                    "running",  # 保持running状态，由TenderService最终更新为success
                    progress=0.98,
                    message="项目信息提取完成，正在保存..."
                )
            
            return final_result
            
        except Exception as e:
            logger.error(f"Checklist-based extraction failed: {e}", exc_info=True)
            
            if run_id:
                self.dao.update_run(run_id, "failed", message=f"提取失败: {str(e)}")
            
            raise
    
    # ❌ extract_risks_v2 和 extract_requirements_v1 已删除
    # V1版本使用关键词召回存在遗漏废标条款的风险，已彻底移除
    # 请使用 extract_requirements_v2（框架式自主提取方式）
    
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
        use_fast_mode: bool = True,
        enable_refinement: bool = False,  # ❌ 禁用规则细化（会自行创造分册）
        enable_bracket_parsing: bool = False,  # ❌ 禁用括号解析（避免额外层级）
        enable_template_matching: bool = True,  # ✨ 阶段5：格式范本自动填充
    ) -> Dict[str, Any]:
        """
        生成目录 (v2) - 多阶段生成
        
        阶段1（快速模式）：如果有项目信息，直接构建骨架
        阶段2（LLM补充）：检索补全细节或全新生成
        阶段3（目录增强）：补充遗漏的必填节点
        阶段4-A（规则细化）：基于招标要求细化评分标准、资格审查等节点
        阶段4-B（LLM括号解析）：解析括号说明，生成L4细分节点
        阶段5（格式范本填充）：自动识别并填充格式范本到节点正文 ✨ 新增
        
        Args:
            use_fast_mode: 是否启用快速模式（默认True）
            enable_refinement: 是否启用规则细化（默认True，设为False可回退）
            enable_bracket_parsing: 是否启用LLM括号解析（默认True，设为False可回退）
            enable_template_matching: 是否启用格式范本匹配（默认True，设为False可回退）
        
        Returns:
            {
                "data": {
                    "nodes": [...]
                },
                "evidence_chunk_ids": [...],
                "evidence_spans": [...],
                "generation_mode": "fast" | "llm" | "hybrid",
                "refinement_stats": {...},
                "bracket_parsing_stats": {...},
                "template_matching_stats": {...}  # ✨ 新增：范本填充统计
            }
        """
        logger.info(f"ExtractV2: generate_directory start project_id={project_id}, fast_mode={use_fast_mode}")
        
        # 阶段1：尝试快速模式
        # ❌ 已禁用：不再使用固定的商务/技术/价格划分，完全依赖从招标书提取的实际目录结构
        # 现在目录生成完全基于招标书中的"投标文件格式"章节
        fast_nodes = []
        fast_stats = {}
        generation_mode = "llm"  # 默认全LLM
        
        # if use_fast_mode:
        #     tender_info = self.dao.get_project_info(project_id)
        #     if tender_info and tender_info.get("schema_version") == "tender_info_v3":
        #         try:
        #             from app.works.tender.directory_fast_builder import build_directory_from_project_info
        #             
        #             fast_nodes, fast_stats = build_directory_from_project_info(
        #                 project_id=project_id,
        #                 pool=self.pool,
        #                 tender_info=tender_info
        #             )
        #             
        #             if fast_nodes and len(fast_nodes) >= 5:  # 至少5个节点才认为有效
        #                 logger.info(
        #                     f"ExtractV2: Fast mode success - {len(fast_nodes)} nodes, "
        #                     f"skip LLM generation"
        #                 )
        #                 generation_mode = "fast"
        #                 
        #                 # 快速模式成功，直接返回
        #                 return {
        #                     "data": {"nodes": fast_nodes},
        #                     "evidence_chunk_ids": [],
        #                     "evidence_spans": [],
        #                     "retrieval_trace": {},
        #                     "generation_mode": generation_mode,
        #                     "fast_stats": fast_stats
        #                 }
        #             else:
        #                 logger.info(f"ExtractV2: Fast mode insufficient ({len(fast_nodes)} nodes), fallback to LLM")
        #                 generation_mode = "hybrid"
        #                 
        #         except Exception as e:
        #             logger.warning(f"ExtractV2: Fast mode failed (non-fatal): {e}")
        #             generation_mode = "llm"
        #     else:
        #         logger.info("ExtractV2: No project_info available, using LLM mode")
        
        # ✅ 新策略（2026-01）：优先从招标书原文提取目录，禁止LLM自行划分大类
        # 
        # 流程：
        # 1. 先用 augment 从招标书"投标文件格式"章节提取原文目录（写入数据库）
        # 2. 如果提取成功（>= 5个节点），直接使用，不调用LLM
        # 3. 如果提取失败或节点太少，才回退到LLM生成
        
        logger.info(f"ExtractV2: 开始生成目录...")
        
        # 🔍 DEBUG: 强制写入日志文件
        import sys
        debug_log = open("/tmp/extract_v2_debug.log", "a")
        debug_log.write(f"\n=== ExtractV2.generate_directory_v2 START ===\n")
        debug_log.write(f"project_id: {project_id}\n")
        debug_log.write(f"use_fast_mode: {use_fast_mode}\n")
        debug_log.flush()
        
        print(f"[ExtractV2-DEBUG] 开始生成目录: project_id={project_id}", file=sys.stderr)
        
        # 步骤0：清空现有目录节点（避免使用旧数据）
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM tender_directory_nodes WHERE project_id = %s
                    """, [project_id])
                    deleted_count = cur.rowcount
                    conn.commit()
                    if deleted_count > 0:
                        logger.info(f"ExtractV2: 清空了 {deleted_count} 个旧目录节点")
                        debug_log.write(f"清空了 {deleted_count} 个旧节点\n")
                        debug_log.flush()
        except Exception as e:
            logger.warning(f"ExtractV2: 清空旧节点失败（非致命）: {e}")
            debug_log.write(f"清空失败: {e}\n")
            debug_log.flush()
        
        # 步骤1：直接跳过augment，强制使用LLM生成
        # 原因：augment对于"投标文件组成"等扁平列表的处理不稳定，容易产生错误的父子关系
        # LLM生成的目录结构更准确、可靠
        extracted_count = 0
        logger.info(f"ExtractV2: 跳过augment，直接使用LLM生成目录（更准确、可靠）")
        debug_log.write(f"跳过augment，直接使用LLM生成\n")
        debug_log.flush()
        
        # === LLM 生成模式 ===
        generation_mode = "llm"
        
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
        
        # 5. 如果是混合模式，合并快速节点和LLM节点
        # ❌ 已禁用：不再使用固定划分
        # if generation_mode == "hybrid" and fast_nodes:
        #     logger.info(f"ExtractV2: Merging fast nodes ({len(fast_nodes)}) with LLM nodes ({len(nodes)})")
        #     # 简单策略：优先使用快速节点，LLM节点作为补充
        #     nodes = fast_nodes + nodes
        
        logger.info(f"ExtractV2: generate_directory done nodes={len(nodes)}, mode={generation_mode}")
        
        # 5. 目录增强 - 已在阶段1完成，不再重复执行
        # ❌ 已禁用：augment 已经在阶段1执行过了
        # try:
        #     logger.info(f"ExtractV2: Attempting directory augmentation for project={project_id}")
        #     
        #     # 读取 tender_project_info
        #     tender_info = self.dao.get_project_info(project_id)
        #     if tender_info and tender_info.get("schema_version") == "tender_info_v3":
        #         from app.works.tender.directory_augment_v1 import augment_directory_from_tender_info_v3
        #         
        #         augment_result = augment_directory_from_tender_info_v3(
        #             project_id=project_id,
        #             pool=self.pool,
        #             tender_info=tender_info
        #         )
        #         
        #         logger.info(
        #             f"ExtractV2: Directory augmentation done - "
        #             f"added={augment_result['added_count']}, "
        #             f"titles={augment_result['enhanced_titles'][:5]}"
        #         )
        # except Exception as e:
        #     logger.warning(f"ExtractV2: Directory augmentation failed (non-fatal): {e}")
        
        # ✨ 6. 规则细化 - 基于招标要求细化评分标准、资格审查等节点（新增阶段4）
        refinement_stats = {}
        try:
            if enable_refinement:
                logger.info(f"ExtractV2: Starting rule-based refinement for project={project_id}")
                
                from app.works.tender.directory_refinement_rule import refine_directory_from_requirements
                
                refinement_result = refine_directory_from_requirements(
                    project_id=project_id,
                    pool=self.pool,
                    nodes=nodes,
                    enable_refinement=True,
                )
                
                # 更新节点列表
                nodes = refinement_result["refined_nodes"]
                refinement_stats = refinement_result["stats"]
                
                logger.info(
                    f"ExtractV2: Rule-based refinement done - "
                    f"added={refinement_result['added_count']} nodes, "
                    f"total={len(nodes)}, "
                    f"refined_parents={refinement_result['refined_parents']}"
                )
            else:
                logger.info(f"ExtractV2: Rule-based refinement disabled")
                refinement_stats = {"enabled": False}
        except Exception as e:
            logger.warning(f"ExtractV2: Rule-based refinement failed (non-fatal): {e}")
            refinement_stats = {"error": str(e)}
        
        # ✨ 7. LLM括号解析 - 解析L3节点的括号说明，生成L4子节点（新增阶段4-B）
        bracket_parsing_stats = {}
        try:
            if enable_bracket_parsing:
                logger.info(f"ExtractV2: Starting LLM-based bracket parsing for project={project_id}")
                
                from app.works.tender.directory_bracket_parser import parse_brackets_with_llm
                
                bracket_result = await parse_brackets_with_llm(
                    nodes=nodes,
                    llm=self.llm,
                    model_id=model_id,
                    enable_parsing=True,
                )
                
                # 更新节点列表
                nodes = bracket_result["enhanced_nodes"]
                bracket_parsing_stats = bracket_result["stats"]
                
                logger.info(
                    f"ExtractV2: LLM bracket parsing done - "
                    f"added={bracket_result['added_count']} L4 nodes, "
                    f"total={len(nodes)}, "
                    f"parsed_parents={bracket_result['parsed_parents']}"
                )
            else:
                logger.info(f"ExtractV2: LLM bracket parsing disabled")
                bracket_parsing_stats = {"enabled": False}
        except Exception as e:
            logger.warning(f"ExtractV2: LLM bracket parsing failed (non-fatal): {e}")
            bracket_parsing_stats = {"error": str(e)}
        
        # ✨ 8. 格式范本匹配与填充 - 自动识别并填充格式范本到节点正文（新增阶段5）
        template_matching_stats = {}
        try:
            if enable_template_matching:
                logger.info(f"ExtractV2: Starting template matching and auto-fill for project={project_id}")
                
                from app.works.tender.template_matcher import match_templates_to_nodes, auto_fill_template_bodies
                
                # 8.1 匹配范本到节点
                match_result = await match_templates_to_nodes(
                    nodes=nodes,
                    project_id=project_id,
                    pool=self.pool,
                    llm=self.llm,
                    model_id=model_id,
                    enable_matching=True,
                )
                
                matches = match_result.get("matches", [])
                match_stats = match_result.get("stats", {})
                
                # 8.2 自动填充匹配的范本
                fill_result = {}
                if matches:
                    fill_result = await auto_fill_template_bodies(
                        matches=matches,
                        project_id=project_id,
                        pool=self.pool,
                    )
                    
                    logger.info(
                        f"ExtractV2: Template auto-fill done - "
                        f"{fill_result.get('filled_count', 0)}/{len(matches)} nodes filled"
                    )
                
                template_matching_stats = {
                    "enabled": True,
                    **match_stats,
                    **fill_result,
                }
            else:
                logger.info(f"ExtractV2: Template matching disabled")
                template_matching_stats = {"enabled": False}
        except Exception as e:
            logger.warning(f"ExtractV2: Template matching failed (non-fatal): {e}")
            template_matching_stats = {"error": str(e)}
        
        # 9. 保存节点到数据库（如果是LLM生成模式）
        if generation_mode == "llm" and nodes:
            try:
                logger.info(f"ExtractV2: Saving {len(nodes)} LLM-generated nodes to database...")
                self._save_nodes_to_db(project_id, nodes)
                logger.info(f"ExtractV2: Successfully saved {len(nodes)} nodes")
            except Exception as e:
                logger.error(f"ExtractV2: Failed to save nodes to database: {e}")
                # 不抛出异常，继续返回结果
        
        # 10. 返回结果
        return {
            "data": {"nodes": nodes},
            "evidence_chunk_ids": result.evidence_chunk_ids,
            "evidence_spans": result.evidence_spans,
            "retrieval_trace": result.retrieval_trace.__dict__ if result.retrieval_trace else {},
            "generation_mode": generation_mode,
            "fast_stats": fast_stats if generation_mode in ["fast", "hybrid"] else {},
            "refinement_stats": refinement_stats,
            "bracket_parsing_stats": bracket_parsing_stats,
            "template_matching_stats": template_matching_stats,  # ✨ 新增：范本填充统计
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
    
    async def extract_requirements_v2(
        self,
        project_id: str,
        model_id: Optional[str],
        checklist_template: str = "engineering",
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        抽取招标要求 (v2) - 框架式自主提取
        
        ✨ 新方法：系统定框架，LLM自主分析识别所有要求
        
        优势：
        1. 灵活性高：不受预设问题限制，能捕捉特殊和独特要求
        2. 完整性强：LLM主动搜索，不易遗漏
        3. 结构化输出：仍保持维度、类型等结构，便于审核
        4. 智能过滤：自动排除合同条款和格式范例
        
        Args:
            project_id: 项目ID
            model_id: 模型ID（默认使用全局配置）
            checklist_template: （已废弃，保留参数兼容性）
            run_id: 运行ID（可选）
        
        Returns:
            {
                "count": 提取的要求数量,
                "requirements": [...],
                "extraction_method": "framework_autonomous",
                "schema_version": "requirements_v2_framework"
            }
        """
        logger.info(
            f"ExtractV2: extract_requirements_v2 start (framework mode) "
            f"project_id={project_id}"
        )
        
        try:
            # 1. 使用框架式Prompt Builder
            from .framework_prompt_builder import FrameworkPromptBuilder
            
            prompt_builder = FrameworkPromptBuilder()
            logger.info("Using simplified 3-stage high-recall retrieval strategy (universal)")
            
            # 2. 检索招标文件上下文
            logger.info("Retrieving tender document context with simplified 3-stage + expansion...")
            
            # 🎯 优化策略：简洁+高效+通用
            # 核心原则（经验总结）：
            # 1. 简洁query（每个query不超过4-5个核心词，避免语义稀释）
            # 2. 大范围检索（top_k保持400/300，不降低）
            # 3. 邻近扩展（确保上下文完整，解决表格切分问题）
            # 4. 让LLM处理更多context（600 chunks），给予更多自主权
            
            # 🎯 V4.0优化：5阶段检索 - 废标项全覆盖
            # 目标：确保所有类型的废标项都能被检索到
            
            # 阶段1：明确废标关键词（扩充版）
            logger.info("Stage 1/5: Explicit rejection keywords (expanded)...")
            stage1_chunks = await self.retriever.retrieve(
                query="废标 否决 无效 拒绝 作废 取消资格 不予受理 不合格 不响应 投标无效",
                project_id=project_id,
                doc_types=["tender"],
                top_k=800,
            )
            logger.info(f"Stage 1: Retrieved {len(stage1_chunks)} explicit rejection chunks")
            
            # 阶段2：实质性响应和资格要求（新增）
            logger.info("Stage 2/5: Substantive response & qualification requirements...")
            stage2_chunks = await self.retriever.retrieve(
                query="实质性响应 实质性要求 不允许偏离 投标人须 资格条件 投标人应 投标人必须",
                project_id=project_id,
                doc_types=["tender"],
                top_k=600,
            )
            logger.info(f"Stage 2: Retrieved {len(stage2_chunks)} substantive/qualification chunks")
            
            # 阶段3：特殊标记符号（新增专门检索）
            logger.info("Stage 3/5: Special markers (▲★* symbols)...")
            stage3_chunks = await self.retriever.retrieve(
                query="▲ ★ * 带▲ 带★ 星号 标注 不允许负偏离",
                project_id=project_id,
                doc_types=["tender"],
                top_k=400,
            )
            logger.info(f"Stage 3: Retrieved {len(stage3_chunks)} special marker chunks")
            
            # 阶段4：重要章节和评分标准
            logger.info("Stage 4/5: Important chapters and scoring standards...")
            stage4_chunks = await self.retriever.retrieve(
                query="投标人须知 评审办法 评分标准 技术要求 采购需求 磋商需求",
                project_id=project_id,
                doc_types=["tender"],
                top_k=800,
            )
            logger.info(f"Stage 4: Retrieved {len(stage4_chunks)} chapter/scoring chunks")
            
            # 阶段5：负面表述和程序要求
            logger.info("Stage 5/5: Negative expressions and procedural requirements...")
            stage5_chunks = await self.retriever.retrieve(
                query="不得 禁止 严禁 投标保证金 样品 原件 签字盖章 最高限价 控制价",
                project_id=project_id,
                doc_types=["tender"],
                top_k=600,
            )
            logger.info(f"Stage 5: Retrieved {len(stage5_chunks)} negative/procedural chunks")
            
            # 合并去重（优先级：stage1 > stage2 > stage3 > stage4 > stage5）
            seen_ids = set()
            initial_chunks = []
            
            for chunk in stage1_chunks:
                if chunk.chunk_id not in seen_ids:
                    initial_chunks.append(chunk)
                    seen_ids.add(chunk.chunk_id)
            
            for chunk in stage2_chunks:
                if chunk.chunk_id not in seen_ids:
                    initial_chunks.append(chunk)
                    seen_ids.add(chunk.chunk_id)
            
            for chunk in stage3_chunks:
                if chunk.chunk_id not in seen_ids:
                    initial_chunks.append(chunk)
                    seen_ids.add(chunk.chunk_id)
            
            for chunk in stage4_chunks:
                if chunk.chunk_id not in seen_ids:
                    initial_chunks.append(chunk)
                    seen_ids.add(chunk.chunk_id)
            
            for chunk in stage5_chunks:
                if chunk.chunk_id not in seen_ids:
                    initial_chunks.append(chunk)
                    seen_ids.add(chunk.chunk_id)
            
            logger.info(f"Combined: {len(initial_chunks)} unique chunks from 5 stages before expansion")
            
            # 🎯 V3.9优化：添加稳定排序，消除检索层不确定性（解决35/46波动问题）
            # 排序键：(score DESC, chunk_id ASC) 确保相似度相同时按chunk_id排序（确定性）
            initial_chunks.sort(key=lambda x: (
                -getattr(x, 'score', 0),  # 按相似度降序
                x.chunk_id  # 相似度相同时，按chunk_id升序（确定性第二排序键）
            ))
            logger.info("Applied stable sorting by (score DESC, chunk_id ASC) to ensure deterministic retrieval")
            
            # 🔑 关键优化：邻近chunk扩展（解决上下文截断问题）
            logger.info("Expanding with adjacent chunks for complete context...")
            context_chunks = await self._expand_with_adjacent_chunks(
                initial_chunks, 
                project_id, 
                expansion_window=2  # 前后各扩展2个chunk（解决"外，其他工作不得分包。"类截断问题）
            )
            logger.info(f"After expansion: {len(context_chunks)} chunks (added {len(context_chunks) - len(initial_chunks)} adjacent)")
            
            # 注意：扩展后不再排序，因为SimpleChunk没有score属性，保持文档自然顺序
            
            # 拼接上下文（使用实际segment_id作为标记）
            # 🚀 V4.0优化：送入LLM 1000个chunks（平衡容量和token限制）
            max_chunks = min(1000, len(context_chunks))  # 使用前1000个chunks
            context_text = "\n\n".join([
                f"[SEG:{chunk.chunk_id}] {chunk.text}"
                for i, chunk in enumerate(context_chunks[:max_chunks])
            ])
            
            logger.info(f"Using {max_chunks} chunks for LLM extraction (out of {len(context_chunks)} retrieved, 5-stage strategy)")
            
            # 构建segment_id映射表（用于后续evidence验证）
            segment_id_map = {chunk.chunk_id: chunk for chunk in context_chunks[:max_chunks]}
            
            if len(context_text) < 100:
                logger.warning("Context text too short, may not have enough information")
            
            # 🎯 新增：规则引擎预提取（Phase 3优化）
            logger.info("Running rule-based extraction first...")
            from .rule_extractor import TenderRuleExtractor
            
            rule_extractor = TenderRuleExtractor()
            rule_results = rule_extractor.extract(context_text, max_results=200)
            rule_requirements = rule_extractor.convert_to_requirements(rule_results)
            
            logger.info(f"Rule engine extracted {len(rule_requirements)} requirements with 100% confidence")
            
            # 3. 构建Prompt并调用LLM（框架式自主提取）
            prompt = prompt_builder.build_prompt(context_text)
            
            # 估算token数量（1 token ≈ 4个字符，中文更高效）
            estimated_tokens = len(prompt) // 3  # 保守估计
            logger.info(
                f"Built framework prompt: {len(prompt)} chars, "
                f"~{estimated_tokens} tokens (estimated), "
                f"chunks: {max_chunks}"
            )
            
            if estimated_tokens > 100000:
                logger.warning(
                    f"⚠️ Prompt可能太长 (~{estimated_tokens} tokens)，"
                    f"如果遇到max_tokens错误，请减少max_chunks"
                )
            
            # 调用LLM进行自主提取
            messages = [{"role": "user", "content": prompt}]
            llm_response = await self.llm.achat(
                messages=messages,
                model_id=model_id,
                response_format={"type": "json_object"},
                temperature=0.0,  # 🎯 设置为0以确保完全确定性，消除提取数量波动
                max_tokens=20000,  # 🚀 平衡token限制：足够提取大量要求，同时避免超过上下文限制
            )
            
            # 提取content
            llm_output = llm_response.get("choices", [{}])[0].get("message", {}).get("content")
            if llm_output is None:
                llm_output = "[]"  # Fallback to empty array
                logger.warning("LLM returned None content, using empty array")
            
            logger.info(f"Got LLM response, length: {len(llm_output)} chars")
            
            # 4. 解析LLM返回的要求列表
            try:
                llm_requirements = prompt_builder.parse_llm_response(llm_output)
                logger.info(f"Parsed {len(llm_requirements)} requirements from LLM")
            except Exception as e:
                logger.error(f"Failed to parse LLM response: {e}")
                return {
                    "count": 0,
                    "requirements": [],
                    "error": f"LLM response parsing failed: {str(e)}",
                    "schema_version": "requirements_v2_framework"
                }
            
            # 🎯 合并规则引擎结果和LLM结果
            logger.info(f"Merging rule-based ({len(rule_requirements)}) and LLM-based ({len(llm_requirements)}) results...")
            
            # 合并并去重（规则结果优先，置信度更高）
            merged_requirements = self._merge_rule_and_llm_results(rule_requirements, llm_requirements)
            
            logger.info(
                f"After merging: {len(merged_requirements)} requirements "
                f"(rule: {len(rule_requirements)}, llm: {len(llm_requirements)}, "
                f"deduplicated: {len(rule_requirements) + len(llm_requirements) - len(merged_requirements)})"
            )
            
            # 使用合并后的结果
            llm_requirements = merged_requirements
            
            # 5. 验证并转换为数据库格式
            # 获取文档版本ID
            doc_version_id = await self._get_doc_version_id(project_id, "tender")
            
            requirements = prompt_builder.convert_to_db_format(
                llm_requirements=llm_requirements,
                project_id=project_id,
                doc_version_id=doc_version_id or 0,
            )
            
            logger.info(f"Converted to DB format: {len(requirements)} requirements")
            
            # 6. 去重（放开限制：关闭后端去重，信任LLM的判断）
            # 原逻辑：seen_texts = {} 基于前100字符去重
            # 新逻辑：完全信任LLM，Prompt中已有去重指导，不在后端强制去重
            logger.info(f"Skipping backend deduplication, total requirements: {len(requirements)}")
            
            # 7. 后处理：推断eval_method, must_reject等字段
            from .requirement_postprocessor import generate_bid_response_extraction_guide
            
            for req in requirements:
                # 推断审核方法和权重
                eval_method, must_reject, expected_evidence, rubric, weight = self._infer_routing_fields(req)
                
                req["eval_method"] = req.get("eval_method") or eval_method
                req["must_reject"] = req.get("must_reject") or must_reject
                if expected_evidence and not req.get("expected_evidence_json"):
                    req["expected_evidence_json"] = expected_evidence
                if rubric:
                    req["rubric_json"] = rubric
                if weight is not None:
                    req["weight"] = weight
            
            logger.info(f"Applied eval_method inference to {len(requirements)} requirements")
            
            # 8. 保存到数据库
            logger.info("Saving requirements to database...")
            
            import uuid
            from psycopg.types.json import Json
            
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    # 先删除该项目的旧requirements（避免重复）
                    cur.execute("DELETE FROM tender_requirements WHERE project_id = %s", (project_id,))
                    logger.info(f"Deleted old requirements for project {project_id}")
                    
                    for req in requirements:
                        # 处理JSONB字段
                        value_schema = req.get("value_schema_json")
                        if value_schema and not isinstance(value_schema, Json):
                            value_schema = Json(value_schema)
                        
                        expected_evidence_json = req.get("expected_evidence_json")
                        if expected_evidence_json and not isinstance(expected_evidence_json, Json):
                            expected_evidence_json = Json(expected_evidence_json)
                        
                        rubric_json = req.get("rubric_json")
                        if rubric_json and not isinstance(rubric_json, Json):
                            rubric_json = Json(rubric_json)
                        
                        # 映射字段名：requirement_type -> req_type, is_mandatory -> is_hard
                        req_type = req.get("requirement_type") or req.get("req_type", "semantic")
                        is_hard = req.get("is_mandatory") or req.get("is_hard", False)
                        requirement_id = req.get("item_id") or req.get("requirement_id", f"auto_{uuid.uuid4().hex[:8]}")
                        
                        # 合并meta_json到value_schema_json
                        meta_json = req.get("meta_json", {})
                        if meta_json:
                            # 提取value_schema的原始dict（如果已经是Json对象，需要先获取其内容）
                            if value_schema:
                                # 如果value_schema是Json对象，取其obj属性；如果是dict，直接使用
                                if isinstance(value_schema, Json):
                                    combined_schema = dict(value_schema.obj) if hasattr(value_schema, 'obj') else {}
                                elif isinstance(value_schema, dict):
                                    combined_schema = dict(value_schema)
                                else:
                                    combined_schema = {}
                            else:
                                combined_schema = {}
                            
                            # 合并meta信息
                            combined_schema["meta"] = meta_json
                            value_schema = Json(combined_schema)
                        elif not value_schema:
                            # 如果没有value_schema也没有meta_json，设置为None
                            value_schema = None
                        
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
                            requirement_id,
                            req.get("dimension", "other"),
                            req_type,
                            req.get("requirement_text", ""),
                            is_hard,
                            req.get("allow_deviation", True),
                            value_schema,
                            req.get("evidence_chunk_ids", []),
                            req.get("eval_method", "SEMANTIC"),
                            req.get("must_reject", False),
                            expected_evidence_json,
                            rubric_json,
                            req.get("weight", 1.0),
                        ))
                    conn.commit()
            
            logger.info(f"ExtractV2: Saved {len(requirements)} requirements to DB")
            
            # 9. 生成extraction_guide（用于后续投标响应抽取）
            logger.info("Generating extraction guide for bid responses...")
            try:
                extraction_guide = generate_bid_response_extraction_guide(requirements)
                
                # 保存到tender_projects.meta_json
                await self._update_project_meta(project_id, {
                    "extraction_guide": extraction_guide
                })
                
                logger.info(f"Extraction guide generated: {len(extraction_guide.get('categories', []))} categories")
            except Exception as e:
                logger.warning(f"Failed to generate extraction guide: {e}")
            
            # 10. 统计维度分布
            dimension_stats = {}
            for req in requirements:
                dim = req.get("dimension", "other")
                dimension_stats[dim] = dimension_stats.get(dim, 0) + 1
            
            logger.info(
                f"ExtractV2: extract_requirements_v2 complete - "
                f"{len(requirements)} requirements extracted, "
                f"dimensions: {dimension_stats}"
            )
            
            return {
                "count": len(requirements),
                "requirements": requirements,
                "dimension_distribution": dimension_stats,
                "extraction_method": "framework_autonomous",
                "schema_version": "requirements_v2_framework",
            }
        
        except Exception as e:
            logger.error(f"ExtractV2: extract_requirements_v2 failed: {e}", exc_info=True)
            raise
    
    async def _get_project_name(self, project_id: str) -> str:
        """获取项目名称"""
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT name FROM tender_projects WHERE project_id = %s",
                        (project_id,)
                    )
                    row = cur.fetchone()
                    
                    if row:
                        return row[0]
        except Exception as e:
            logger.warning(f"Failed to get project name: {e}")
        
        return "本项目"
    
    async def _get_doc_version_id(self, project_id: str, doc_type: str) -> Optional[int]:
        """获取文档版本ID"""
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id FROM doc_versions WHERE project_id = %s AND doc_type = %s ORDER BY uploaded_at DESC LIMIT 1",
                        (project_id, doc_type)
                    )
                    row = cur.fetchone()
                    
                    if row:
                        return row[0]
        except Exception as e:
            logger.warning(f"Failed to get doc_version_id: {e}")
        
        return None
    
    def _merge_rule_and_llm_results(
        self,
        rule_requirements: List[Dict],
        llm_requirements: List[Dict]
    ) -> List[Dict]:
        """
        合并规则引擎和LLM的提取结果，智能去重
        
        策略：
        1. 规则提取的结果优先（置信度100%）
        2. LLM提取的结果如果与规则结果高度相似，则丢弃
        3. LLM提取的独特结果保留
        
        Args:
            rule_requirements: 规则引擎提取的要求
            llm_requirements: LLM提取的要求
            
        Returns:
            合并后的要求列表
        """
        from difflib import SequenceMatcher
        
        def text_similarity(a: str, b: str) -> float:
            """计算两个文本的相似度"""
            return SequenceMatcher(None, a.lower(), b.lower()).ratio()
        
        # 开始合并
        merged = []
        
        # 1. 先添加所有规则结果（100%保留）
        for req in rule_requirements:
            req["extraction_source"] = "RULE"
            merged.append(req)
        
        # 2. 检查每个LLM结果
        for llm_req in llm_requirements:
            llm_text = llm_req.get("requirement_text", "")
            
            # 检查是否与规则结果重复
            is_duplicate = False
            for rule_req in rule_requirements:
                rule_text = rule_req.get("requirement_text", "")
                
                # 如果相似度>80%，认为是重复
                similarity = text_similarity(llm_text, rule_text)
                if similarity > 0.8:
                    is_duplicate = True
                    logger.debug(
                        f"LLM result is duplicate of rule result (similarity={similarity:.2f}): "
                        f"{llm_text[:50]}..."
                    )
                    break
            
            # 如果不重复，添加到结果中
            if not is_duplicate:
                llm_req["extraction_source"] = "LLM"
                merged.append(llm_req)
        
        return merged
    
    async def _expand_with_adjacent_chunks(
        self,
        chunks: List[Any],
        project_id: str,
        expansion_window: int = 1
    ) -> List[Any]:
        """
        扩展chunks以包含邻近的chunks，解决上下文截断问题
        
        Args:
            chunks: 初始检索到的chunks
            project_id: 项目ID
            expansion_window: 前后各扩展几个chunk（默认1）
        
        Returns:
            扩展后的chunks列表（按position排序，去重）
        """
        if not chunks:
            return chunks
        
        # 收集需要扩展的chunk_ids
        chunk_ids_to_expand = [chunk.chunk_id for chunk in chunks]
        
        # 从数据库查询这些chunks的position和doc_version_id
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    # 查询chunks的position信息
                    cur.execute(
                        """
                        SELECT id, doc_version_id, position, content_text
                        FROM doc_segments
                        WHERE id = ANY(%s)
                        ORDER BY doc_version_id, position
                        """,
                        (chunk_ids_to_expand,)
                    )
                    rows = cur.fetchall()
                    
                    if not rows:
                        return chunks
                    
                    # 构建position映射
                    chunk_info = {}
                    for row in rows:
                        chunk_info[row[0]] = {
                            'doc_version_id': row[1],
                            'position': row[2],
                            'content_text': row[3]
                        }
                    
                    # 计算需要的position范围
                    positions_to_fetch = set()
                    doc_versions = set()
                    for chunk_id, info in chunk_info.items():
                        doc_version_id = info['doc_version_id']
                        position = info['position']
                        doc_versions.add(doc_version_id)
                        
                        # 添加邻近positions
                        for offset in range(-expansion_window, expansion_window + 1):
                            positions_to_fetch.add((doc_version_id, position + offset))
                    
                    # 查询所有需要的chunks
                    expanded_chunks = []
                    for doc_version_id, position in positions_to_fetch:
                        cur.execute(
                            """
                            SELECT id, content_text
                            FROM doc_segments
                            WHERE doc_version_id = %s AND position = %s
                            """,
                            (doc_version_id, position)
                        )
                        row = cur.fetchone()
                        if row:
                            # 创建简单的chunk对象
                            class SimpleChunk:
                                def __init__(self, chunk_id, text, pos):
                                    self.chunk_id = chunk_id
                                    self.text = text
                                    self.position = pos
                            
                            expanded_chunks.append(SimpleChunk(row[0], row[1], position))
                    
                    # 按position排序
                    expanded_chunks.sort(key=lambda c: c.position)
                    
                    # 去重（保留第一次出现的）
                    seen_ids = set()
                    unique_chunks = []
                    for chunk in expanded_chunks:
                        if chunk.chunk_id not in seen_ids:
                            unique_chunks.append(chunk)
                            seen_ids.add(chunk.chunk_id)
                    
                    return unique_chunks
                    
        except Exception as e:
            logger.warning(f"Failed to expand chunks: {e}, returning original chunks")
            return chunks
    
    async def _update_project_meta(self, project_id: str, meta_update: Dict[str, Any]):
        """更新项目meta_json"""
        from psycopg.types.json import Json
        
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE tender_projects
                        SET meta_json = COALESCE(meta_json, '{}'::jsonb) || %s::jsonb
                        WHERE id = %s
                        """,
                        (Json(meta_update), project_id)
                    )
                conn.commit()
                
                logger.info(f"Updated project meta for {project_id}")
        except Exception as e:
            logger.error(f"Failed to update project meta: {e}")
    
    async def _supplement_requirements_fulltext(
        self,
        project_id: str,
        model_id: Optional[str],
        existing_requirements: List[Dict[str, Any]],
        context_chunks: List[Any],
    ) -> List[Dict[str, Any]]:
        """
        P1优化：全文补充提取Checklist未覆盖的招标要求
        
        策略：
        1. 让LLM全文扫描招标文件
        2. 识别Checklist未覆盖的要求
        3. 特别关注：技术参数表、功能清单、特殊条款、附件要求、隐含要求
        
        Args:
            project_id: 项目ID
            model_id: 模型ID
            existing_requirements: 已提取的要求列表
            context_chunks: 检索到的上下文chunks
        
        Returns:
            补充的要求列表
        """
        logger.info(f"[补充提取] 开始全文扫描，已有 {len(existing_requirements)} 条要求")
        
        try:
            # 1. 构建已提取要求的摘要（用于去重）
            existing_summary = []
            for req in existing_requirements[:50]:  # 限制摘要长度
                dim = req.get("dimension", "")
                text = req.get("requirement_text", "")[:60]
                existing_summary.append(f"[{dim}] {text}")
            
            existing_text = "\n".join(existing_summary)
            
            # 2. 准备全文上下文（使用更多chunks）
            fulltext_context = "\n\n".join([
                f"[SEG:{chunk.chunk_id}] {chunk.text}"
                for chunk in context_chunks[:150]  # 扩展到150个chunks
            ])
            
            # 3. 构建补充提取prompt
            supplement_prompt = f"""# 招标要求补充提取任务

## 背景
已通过标准清单提取了 {len(existing_requirements)} 条招标要求，现需要全文扫描招标文件，识别遗漏的要求。

## 已提取要求摘要（前50条）
{existing_text}

## 招标文件全文
{fulltext_context}

## 任务要求
请全文扫描招标文件，识别以下**未被现有清单覆盖的要求**：

### 重点关注（高频遗漏）
1. **技术参数表、功能清单**：详细的技术指标、性能要求
2. **特殊条款、补充说明**：合同特殊条款、附加要求
3. **附件清单**：必须提供的附件、证明材料
4. **评分项隐含要求**：评分标准中隐含的交付物要求
5. **投标书目录结构要求**：章节组成、格式要求
6. **偏离表要求**：技术/商务偏离表
7. **样品、演示要求**：如有
8. **特定资质/认证要求**：行业特定资质

### 输出格式
返回JSON数组，**只包含新发现的、未被已提取要求覆盖的条目**：

```json
{{
  "supplement_requirements": [
    {{
      "dimension": "qualification|technical|business|price|doc_structure|schedule_quality|other",
      "req_type": "具体类型",
      "requirement_text": "要求内容（详细且完整）",
      "is_hard": true/false,
      "eval_method": "PRESENCE|NUMERIC|EXACT_MATCH|SEMANTIC",
      "evidence_segment_ids": ["seg_xxx", "seg_yyy"],
      "reasoning": "为什么这是一个新要求（未被已提取清单覆盖）"
    }}
  ]
}}
```

### 去重原则
- **仔细对比已提取清单**：如果某要求已被覆盖（即使表述不同），**不要重复提取**
- **宁缺毋滥**：不确定是否重复时，选择不提取
- **聚焦特殊性**：优先提取特殊、具体的要求，而非通用要求

### 示例
✅ 应该补充：
- "提供XX品牌认证证书或同等产品认证"（特定认证要求）
- "技术方案应包含系统架构图、数据流图、部署拓扑图"（具体交付物）
- "投标书须提供原厂授权书原件"（特定文件要求）

❌ 不应补充（已被清单覆盖）：
- "营业执照"（清单qual_001已覆盖）
- "资质证书"（清单qual_002已覆盖）
- "投标总价"（清单price_001已覆盖）

请开始分析并输出JSON。"""

            # 4. 调用LLM
            messages = [{"role": "user", "content": supplement_prompt}]
            llm_response = await self.llm.achat(
                messages=messages,
                model_id=model_id,
                response_format={"type": "json_object"},
                temperature=0.0,  # 🎯 设置为0以确保完全确定性
                max_tokens=4096,
            )
            
            # 5. 解析响应
            import json
            llm_output = llm_response.get("choices", [{}])[0].get("message", {}).get("content")
            if not llm_output:
                logger.warning("[补充提取] LLM返回空内容")
                return []
            
            try:
                result_data = json.loads(llm_output)
                supplement_items = result_data.get("supplement_requirements", [])
            except json.JSONDecodeError as e:
                logger.error(f"[补充提取] JSON解析失败: {e}")
                return []
            
            if not supplement_items:
                logger.info("[补充提取] 未发现额外要求")
                return []
            
            logger.info(f"[补充提取] LLM返回 {len(supplement_items)} 条补充要求")
            
            # 6. 转换为标准格式
            import uuid
            supplement_requirements = []
            
            for idx, item in enumerate(supplement_items):
                requirement_id = f"supplement_{idx+1:03d}"
                
                supplement_requirements.append({
                    "project_id": project_id,
                    "requirement_id": requirement_id,
                    "dimension": item.get("dimension", "other"),
                    "req_type": item.get("req_type", "other"),
                    "requirement_text": item.get("requirement_text", ""),
                    "is_hard": item.get("is_hard", False),
                    "allow_deviation": not item.get("is_hard", False),
                    "eval_method": item.get("eval_method", "SEMANTIC"),
                    "must_reject": False,
                    "evidence_chunk_ids": item.get("evidence_segment_ids", []),
                    "meta_json": {
                        "source": "fulltext_supplement",
                        "reasoning": item.get("reasoning", ""),
                    }
                })
            
            logger.info(f"[补充提取] 成功转换 {len(supplement_requirements)} 条补充要求")
            return supplement_requirements
            
        except Exception as e:
            logger.error(f"[补充提取] 失败: {e}", exc_info=True)
            return []
    
    def _save_nodes_to_db(self, project_id: str, nodes: List[Dict[str, Any]]):
        """
        将节点列表保存到 tender_directory_nodes 表
        
        参考 directory_augment_v1.py 的实现
        
        ⚠️ 重要：正确计算 order_no，确保子节点紧跟在父节点之后
        """
        import hashlib
        import json
        
        # ✨ 步骤1：重新计算 order_no，确保显示顺序正确
        # 原因：LLM返回的节点是扁平列表，子节点可能与父节点不相邻
        # 目标：Level 1节点按顺序排列，每个Level 1的子节点紧跟其后
        
        # 先为所有节点生成ID（如果没有）
        for i, node in enumerate(nodes):
            if not node.get("id"):
                id_str = f"{project_id}_{node.get('title', '')}_{node.get('level', 0)}_{i}"
                node["id"] = f"dn_{hashlib.md5(id_str.encode()).hexdigest()[:16]}"
        
        # 建立 title -> id 映射（用于 parent_ref 解析）
        title_to_id = {node.get("title"): node.get("id") for node in nodes if node.get("title")}
        
        # 解析 parent_id
        for node in nodes:
            if not node.get("parent_id") and node.get("parent_ref"):
                parent_title = node.get("parent_ref")
                node["parent_id"] = title_to_id.get(parent_title)
        
        # 重新计算 order_no：先Level 1，再每个Level 1的子节点
        new_order = 1
        for node in nodes:
            if node.get("level") == 1:  # Level 1 节点
                node["_computed_order_no"] = new_order
                new_order += 1
                
                # 找到这个Level 1节点的所有子节点
                node_id = node.get("id")
                for child in nodes:
                    if child.get("parent_id") == node_id:
                        child["_computed_order_no"] = new_order
                        new_order += 1
        
        # 对于没有被分配order_no的节点（孤立节点），按原顺序分配
        for node in nodes:
            if "_computed_order_no" not in node:
                node["_computed_order_no"] = new_order
                new_order += 1
                logger.warning(f"Node '{node.get('title')}' (level={node.get('level')}) has no parent, assigned order_no={new_order-1}")
        
        # ✨ 步骤2：保存到数据库
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                for node in nodes:
                    node_id = node.get("id")
                    parent_id = node.get("parent_id")
                    
                    # 构建 meta_json
                    meta_json = {
                        "notes": node.get("notes", ""),
                        "volume": node.get("volume", ""),
                        "template_chunk_ids": node.get("template_chunk_ids", []),
                    }
                    if node.get("parent_ref"):
                        meta_json["parent_ref"] = node.get("parent_ref")
                    
                    # INSERT节点
                    cur.execute("""
                        INSERT INTO tender_directory_nodes (
                            id, project_id, parent_id, order_no, level, numbering,
                            title, is_required, source, evidence_chunk_ids, meta_json,
                            created_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            title = EXCLUDED.title,
                            parent_id = EXCLUDED.parent_id,
                            order_no = EXCLUDED.order_no,
                            level = EXCLUDED.level,
                            numbering = EXCLUDED.numbering,
                            is_required = EXCLUDED.is_required,
                            source = EXCLUDED.source,
                            evidence_chunk_ids = EXCLUDED.evidence_chunk_ids,
                            meta_json = EXCLUDED.meta_json,
                            updated_at = CURRENT_TIMESTAMP
                    """, [
                        node_id,
                        project_id,
                        parent_id,
                        node.get("_computed_order_no"),  # ✅ 使用重新计算的 order_no
                        node.get("level", 1),
                        node.get("numbering", ""),
                        node.get("title", "未命名"),
                        node.get("required", True) or node.get("is_required", True),
                        node.get("source", "LLM_GENERATED"),
                        node.get("evidence_chunk_ids", []),
                        json.dumps(meta_json, ensure_ascii=False)
                    ])
                
                conn.commit()
                logger.info(f"_save_nodes_to_db: Committed {len(nodes)} nodes for project={project_id} with corrected order_no")
    
