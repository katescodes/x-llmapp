"""
一体化审核服务 - 提取响应 + 审核判断一次完成
"""
import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class UnifiedAuditService:
    """
    一体化审核服务：
    - 读取招标要求
    - LLM提取投标响应 + 审核判断（一次完成）
    - 保存响应数据（供其他用途）
    - 保存审核结果（供前端展示）
    - 返回完整审核报告
    """
    
    def __init__(self, pool: Any, llm_orchestrator: Any, retriever: Any):
        self.pool = pool
        self.llm = llm_orchestrator
        self.retriever = retriever
    
    async def run_unified_audit(
        self,
        project_id: str,
        bidder_name: str,
        model_id: Optional[str] = None,
        run_id: Optional[str] = None,
        custom_rule_pack_ids: Optional[List[str]] = None  # ✨ 新增参数
    ) -> Dict[str, Any]:
        """
        执行一体化审核
        
        Args:
            project_id: 项目ID
            bidder_name: 投标人名称
            model_id: LLM模型ID
            run_id: 运行ID
            custom_rule_pack_ids: ✨ 自定义规则包ID列表（可选）
        
        Returns:
            完整审核报告
        """
        logger.info(f"UnifiedAudit: start project_id={project_id}, bidder={bidder_name}")
        
        # 1. 加载招标要求
        tender_requirements = self._load_requirements(project_id)
        if not tender_requirements:
            raise ValueError(f"未找到招标要求，请先提取招标要求。项目ID: {project_id}")
        
        logger.info(f"Loaded {len(tender_requirements)} tender requirements")
        
        # ✨ 1.5. 加载并合并自定义规则包（如果指定）
        virtual_requirements = []
        if custom_rule_pack_ids:
            logger.info(f"UnifiedAudit: Loading {len(custom_rule_pack_ids)} custom rule packs")
            from app.works.tender.review_v3_service import ReviewV3Service
            
            # 借用ReviewV3Service的规则转换逻辑
            review_service = ReviewV3Service(self.pool, self.llm)
            virtual_requirements = review_service._load_and_convert_custom_rules(
                custom_rule_pack_ids, project_id
            )
            logger.info(f"UnifiedAudit: Loaded {len(virtual_requirements)} custom rules as virtual requirements")
        
        # 合并要求：自定义规则在前（优先级更高）
        requirements = virtual_requirements + tender_requirements
        logger.info(f"UnifiedAudit: Total {len(requirements)} requirements ({len(tender_requirements)} tender + {len(virtual_requirements)} custom)")
        
        # 2. 调用框架式提取器（含审核判断）
        from app.works.tender.framework_bid_response_extractor import FrameworkBidResponseExtractor
        
        extractor = FrameworkBidResponseExtractor(
            llm_orchestrator=self.llm,
            retriever=self.retriever
        )
        
        responses = await extractor.extract_all_responses(
            project_id=project_id,
            requirements=requirements,
            model_id=model_id
        )
        
        logger.info(f"Extracted and audited {len(responses)} responses")
        
        # 3. 分类统计
        stats = self._calculate_stats(responses)
        
        # 4. 保存数据
        # 注：暂时只保存到审核表，因为tender_bid_response_items表结构不同
        # 审核表tender_review_items中的bid_response字段已包含响应内容
        self._save_audit_results(project_id, bidder_name, responses, requirements)
        
        # 5. 生成审核报告
        report = self._generate_report(
            project_id=project_id,
            bidder_name=bidder_name,
            requirements=requirements,
            responses=responses,
            stats=stats
        )
        
        logger.info(f"UnifiedAudit: complete, {stats['pass_count']} PASS, {stats['fail_count']} FAIL")
        
        return report
    
    def _load_requirements(self, project_id: str) -> List[Dict[str, Any]]:
        """加载招标要求"""
        import psycopg.rows
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute("""
                    SELECT 
                        id, project_id, requirement_id, dimension, req_type,
                        requirement_text, is_hard, value_schema_json,
                        evidence_chunk_ids, eval_method, must_reject,
                        expected_evidence_json, rubric_json, weight
                    FROM tender_requirements 
                    WHERE project_id = %s
                    ORDER BY dimension, requirement_id
                """, (project_id,))
                
                rows = cur.fetchall()
                logger.info(f"Loaded {len(rows)} requirements from database")
                if rows and len(rows) > 0:
                    logger.debug(f"First requirement: dimension={rows[0].get('dimension')}, req_id={rows[0].get('requirement_id')}")
                return rows if rows else []
    
    def _calculate_stats(self, responses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """统计审核结果"""
        stats = {
            "total": len(responses),
            "pass_count": 0,
            "fail_count": 0,
            "pending_count": 0,
            "missing_count": 0,
            "high_confidence_count": 0,
            "low_confidence_count": 0
        }
        
        for resp in responses:
            status = resp.get("review_status", "PENDING")
            confidence = resp.get("confidence", 0.0)
            
            if status == "PASS":
                stats["pass_count"] += 1
            elif status == "FAIL":
                stats["fail_count"] += 1
            elif status == "MISSING":
                stats["missing_count"] += 1
            else:
                stats["pending_count"] += 1
            
            if confidence >= 0.85:
                stats["high_confidence_count"] += 1
            else:
                stats["low_confidence_count"] += 1
        
        return stats
    
    def _save_responses(
        self,
        project_id: str,
        bidder_name: str,
        responses: List[Dict[str, Any]]
    ):
        """保存投标响应数据"""
        from psycopg.types.json import Json
        
        # 先删除旧数据
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM tender_bid_response_items 
                    WHERE project_id = %s AND bidder_name = %s
                """, (project_id, bidder_name))
                
                saved_count = 0
                for resp in responses:
                    response_text = resp.get("response_text")
                    if not response_text:
                        continue  # 跳过null响应
                    
                    # 确保normalized_fields是Json对象
                    normalized_fields = resp.get("normalized_fields") or {}
                    if not isinstance(normalized_fields, Json):
                        normalized_fields = Json(normalized_fields) if normalized_fields else Json({})
                    
                    # 确保evidence_segment_ids是列表
                    evidence_ids = resp.get("evidence_segment_ids") or []
                    if isinstance(evidence_ids, str):
                        evidence_ids = []
                    if not isinstance(evidence_ids, list):
                        evidence_ids = list(evidence_ids) if evidence_ids else []
                    
                    cur.execute("""
                        INSERT INTO tender_bid_response_items (
                            id, project_id, bidder_name, requirement_id,
                            response_text, normalized_fields_json,
                            evidence_segment_ids, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    """, (
                        str(uuid.uuid4()),
                        project_id,
                        bidder_name,
                        resp.get("requirement_id"),
                        response_text,
                        normalized_fields,
                        evidence_ids
                    ))
                    saved_count += 1
                
                conn.commit()
                logger.info(f"Saved {saved_count} responses to bid_response_items")
    
    def _save_audit_results(
        self,
        project_id: str,
        bidder_name: str,
        responses: List[Dict[str, Any]],
        requirements: List[Dict[str, Any]]
    ):
        """保存审核结果"""
        from psycopg.types.json import Json
        
        # 创建requirement_id到requirement的映射
        req_map = {req.get("requirement_id"): req for req in requirements}
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                # 先删除该投标人的旧审核记录
                cur.execute("""
                    DELETE FROM tender_review_items 
                    WHERE project_id = %s AND bidder_name = %s
                """, (project_id, bidder_name))
                
                for resp in responses:
                    req_id = resp.get("requirement_id")
                    requirement = req_map.get(req_id, {})
                    
                    # 如果找不到requirement，为框架式提取的维度生成描述性文本
                    if not requirement or not requirement.get("requirement_text"):
                        fallback_names = {
                            "price": "投标总价",
                            "honor_awards": "企业荣誉和奖项",
                            "performance": "类似项目业绩",
                            "technical_indicators": "技术指标",
                            "implementation_plan": "实施方案",
                            "after_sales_service": "售后服务方案",
                            "qualification": "资质要求",
                            "personnel": "人员配置",
                            "schedule": "项目进度计划",
                        }
                        fallback_text = fallback_names.get(req_id, f"要求项：{req_id}")
                        if not requirement:
                            requirement = {}
                        if not requirement.get("requirement_text"):
                            requirement["requirement_text"] = fallback_text
                            logger.debug(f"Generated fallback requirement_text for {req_id}: {fallback_text}")
                    
                    # 确定状态和结论
                    review_status = resp.get("review_status", "PENDING")
                    review_conclusion = resp.get("review_conclusion", "")
                    confidence = resp.get("confidence", 0.0)
                    risk_level = resp.get("risk_level", "medium")
                    
                    # 映射result字段
                    result_map = {
                        "PASS": "通过",
                        "FAIL": "不合规",
                        "PENDING": "待审核",
                        "MISSING": "缺失"
                    }
                    result_text = result_map.get(review_status, "待审核")
                    
                    # 准备证据JSON (必须是数组格式以匹配API schema)
                    evidence_json = Json([{
                        "confidence": confidence,
                        "risk_level": risk_level,
                        "source": "llm_unified",
                        "normalized_fields": resp.get("normalized_fields", {})
                    }])
                    
                    # 映射status字段
                    status_map = {
                        "PASS": "pass",
                        "FAIL": "fail",
                        "PENDING": "pending",
                        "MISSING": "missing"
                    }
                    status = status_map.get(review_status, "pending")
                    
                    # 确保is_hard是布尔类型
                    is_hard = requirement.get("is_hard")
                    if isinstance(is_hard, str):
                        is_hard = is_hard.lower() in ('true', 't', '1', 'yes')
                    elif is_hard is None:
                        is_hard = False
                    
                    # 确保数组字段是列表类型
                    tender_evidence = requirement.get("evidence_chunk_ids") or []
                    if isinstance(tender_evidence, str):
                        tender_evidence = []
                    if not isinstance(tender_evidence, list):
                        tender_evidence = list(tender_evidence) if tender_evidence else []
                    
                    bid_evidence = resp.get("evidence_segment_ids") or []
                    if isinstance(bid_evidence, str):
                        bid_evidence = []
                    if not isinstance(bid_evidence, list):
                        bid_evidence = list(bid_evidence) if bid_evidence else []
                    
                    cur.execute("""
                        INSERT INTO tender_review_items (
                            id, project_id, dimension, requirement_id,
                            tender_requirement, bidder_name, bid_response,
                            result, is_hard, remark,
                            tender_evidence_chunk_ids, bid_evidence_chunk_ids,
                            status, severity, evaluator, evidence_json,
                            created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """, (
                        str(uuid.uuid4()),
                        project_id,
                        requirement.get("dimension", "other"),
                        req_id,
                        requirement.get("requirement_text", ""),
                        bidder_name,
                        resp.get("response_text") or "",
                        result_text,
                        bool(is_hard),
                        review_conclusion or f"LLM一体化审核: {review_status}",
                        tender_evidence,
                        bid_evidence,
                        status,
                        risk_level.lower(),
                        "llm_unified",
                        evidence_json
                    ))
                
                conn.commit()
                logger.info(f"Saved {len(responses)} audit results to tender_review_items")
    
    def _generate_report(
        self,
        project_id: str,
        bidder_name: str,
        requirements: List[Dict[str, Any]],
        responses: List[Dict[str, Any]],
        stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成审核报告"""
        # 按维度分组
        by_dimension = {}
        for resp in responses:
            req_id = resp.get("requirement_id")
            req = next((r for r in requirements if r.get("requirement_id") == req_id), {})
            dim = req.get("dimension", "other")
            
            if dim not in by_dimension:
                by_dimension[dim] = []
            
            by_dimension[dim].append({
                "requirement_id": req_id,
                "requirement_text": req.get("requirement_text", ""),
                "response_text": resp.get("response_text"),
                "review_status": resp.get("review_status"),
                "review_conclusion": resp.get("review_conclusion"),
                "confidence": resp.get("confidence", 0.0),
                "risk_level": resp.get("risk_level"),
                "evidence_segment_ids": resp.get("evidence_segment_ids", [])
            })
        
        return {
            "project_id": project_id,
            "bidder_name": bidder_name,
            "audit_method": "unified_llm",
            "timestamp": datetime.now().isoformat(),
            "statistics": stats,
            "by_dimension": by_dimension,
            "summary": {
                "total_requirements": stats["total"],
                "pass_rate": stats["pass_count"] / stats["total"] if stats["total"] > 0 else 0,
                "high_confidence_rate": stats["high_confidence_count"] / stats["total"] if stats["total"] > 0 else 0,
                "need_manual_review": stats["pending_count"] + stats["low_confidence_count"]
            }
        }

