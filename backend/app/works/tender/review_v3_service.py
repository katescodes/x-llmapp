"""
审核服务 V3 - requirements × response + 规则引擎

完全重写的审核逻辑：
1. 从 tender_requirements 读取基准要求
2. 从 tender_bid_response_items 读取投标响应
3. 应用确定性规则引擎
4. 应用语义LLM规则引擎
5. 生成 tender_review_items
"""
import logging
import uuid
from typing import Any, Dict, List, Optional

from app.services.dao.tender_dao import TenderDAO
from app.works.tender.rules.effective_ruleset import EffectiveRulesetBuilder
from app.works.tender.rules.deterministic_engine import DeterministicRuleEngine
from app.works.tender.rules.semantic_llm_engine import SemanticLLMRuleEngine
from app.works.tender.rules.basic_requirement_evaluator import BasicRequirementEvaluator
from app.works.tender.rules.dimension_batch_llm_reviewer import DimensionBatchLLMReviewer

logger = logging.getLogger(__name__)


class ReviewV3Service:
    """审核服务 V3 - requirements × response + 规则引擎"""
    
    def __init__(self, pool: Any, llm_orchestrator: Any = None):
        self.pool = pool
        self.llm = llm_orchestrator
        self.dao = TenderDAO(pool)
        
        # 初始化规则引擎
        self.ruleset_builder = EffectiveRulesetBuilder(pool)
        self.deterministic_engine = DeterministicRuleEngine()
        self.semantic_engine = SemanticLLMRuleEngine(llm_orchestrator)
        self.basic_evaluator = BasicRequirementEvaluator()  # 基础要求评估器
        self.llm_semantic_reviewer = DimensionBatchLLMReviewer(llm_orchestrator)  # LLM语义审核器
    
    async def run_review_v3(
        self,
        project_id: str,
        bidder_name: str,
        model_id: Optional[str] = None,
        custom_rule_pack_ids: Optional[List[str]] = None,
        run_id: Optional[str] = None,
        use_llm_semantic: bool = False,  # 新增：是否使用LLM语义审核
    ) -> Dict[str, Any]:
        """
        运行审核 V3
        
        Args:
            project_id: 项目ID
            bidder_name: 投标人名称
            model_id: LLM模型ID
            custom_rule_pack_ids: 自定义规则包ID列表（可选）
            run_id: 运行ID（可选）
            use_llm_semantic: 是否使用LLM语义审核（可选，默认False）
        
        Returns:
            {
                "total_review_items": 50,
                "pass_count": 30,
                "fail_count": 15,
                "warn_count": 5,
                "review_mode": "LLM_SEMANTIC" | "CUSTOM_RULES" | "BASIC_REQUIREMENTS_ONLY",
                "items": [...]
            }
        """
        logger.info(f"ReviewV3: run_review start project_id={project_id}, bidder={bidder_name}")
        
        # 1. 读取招标要求
        requirements = self._get_requirements(project_id)
        logger.info(f"ReviewV3: Loaded {len(requirements)} requirements")
        
        # 2. 读取投标响应
        responses = self._get_responses(project_id, bidder_name)
        logger.info(f"ReviewV3: Loaded {len(responses)} responses for bidder={bidder_name}")
        
        if not requirements:
            logger.warning(f"ReviewV3: No requirements found for project={project_id}")
            return {
                "total_review_items": 0,
                "pass_count": 0,
                "fail_count": 0,
                "warn_count": 0,
                "items": []
            }
        
        if not responses:
            logger.warning(f"ReviewV3: No responses found for bidder={bidder_name}")
            # 如果没有响应，所有硬性要求都视为FAIL
            return await self._handle_no_responses(project_id, bidder_name, requirements)
        
        # 3. 构建有效规则集
        # 如果没有传规则包ID，自动加载所有激活的共享规则包
        use_custom_rules = True
        if not custom_rule_pack_ids:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id FROM tender_rule_packs 
                        WHERE project_id IS NULL 
                          AND is_active = true 
                          AND pack_type = 'custom'
                        ORDER BY priority DESC, created_at DESC
                    """)
                    rows = cur.fetchall()
                    custom_rule_pack_ids = [row['id'] for row in rows]
                    if custom_rule_pack_ids:
                        logger.info(f"ReviewV3: Auto-selected {len(custom_rule_pack_ids)} shared rule packs")
                    else:
                        logger.info("ReviewV3: No custom rule packs found, will use basic requirement evaluation")
                        use_custom_rules = False
        
        # 审核模式判断
        review_mode = "BASIC_REQUIREMENTS_ONLY"  # 默认模式
        
        if use_llm_semantic:
            # 模式：LLM语义审核
            logger.info("ReviewV3: Mode=LLM_SEMANTIC, using dimension batch LLM reviewer")
            review_mode = "LLM_SEMANTIC"
            
            # 直接使用LLM语义审核
            all_results = await self.llm_semantic_reviewer.review(
                requirements=requirements,
                responses=responses,
                model_id=model_id
            )
            
            effective_rules = []  # LLM语义模式不使用规则
            
        elif use_custom_rules and custom_rule_pack_ids:
            # 模式A：使用自定义规则进行审核
            effective_rules = self.ruleset_builder.build_effective_ruleset(
                project_id, 
                custom_rule_pack_ids=custom_rule_pack_ids
            )
            logger.info(f"ReviewV3: Mode=CUSTOM_RULES, loaded {len(effective_rules)} rules")
            review_mode = "CUSTOM_RULES"
            
            # 4. 分离确定性规则和语义LLM规则
            deterministic_rules = [r for r in effective_rules if r.get("evaluator") == "deterministic"]
            semantic_rules = [r for r in effective_rules if r.get("evaluator") == "semantic_llm"]
            
            logger.info(
                f"ReviewV3: deterministic_rules={len(deterministic_rules)}, "
                f"semantic_rules={len(semantic_rules)}"
            )
            
            # 5. 执行规则引擎
            deterministic_results = self.deterministic_engine.evaluate_rules(
                rules=deterministic_rules,
                requirements=requirements,
                responses=responses
            )
            logger.info(f"ReviewV3: Deterministic engine produced {len(deterministic_results)} results")
            
            semantic_results = await self.semantic_engine.evaluate_rules(
                rules=semantic_rules,
                requirements=requirements,
                responses=responses,
                model_id=model_id
            )
            logger.info(f"ReviewV3: Semantic engine produced {len(semantic_results)} results")
            
            # 6. 基础要求评估（补充）
            basic_results = self.basic_evaluator.evaluate_requirements(
                requirements=requirements,
                responses=responses
            )
            logger.info(f"ReviewV3: Basic evaluator produced {len(basic_results)} results")
            
            # 合并：规则结果 + 基础评估结果
            all_results = deterministic_results + semantic_results + basic_results
        else:
            # 模式B：只使用基础要求评估（无自定义规则）
            logger.info("ReviewV3: Mode=BASIC_REQUIREMENTS_ONLY")
            effective_rules = []
            review_mode = "BASIC_REQUIREMENTS_ONLY"
            
            # 4. 执行基础要求评估
            basic_results = self.basic_evaluator.evaluate_requirements(
                requirements=requirements,
                responses=responses
            )
            logger.info(f"ReviewV3: Basic evaluator produced {len(basic_results)} results")
            
            all_results = basic_results
        
        # 7. 落库到 tender_review_items
        self._save_review_items(project_id, bidder_name, all_results)
        
        # 8. 统计
        stats = self._calculate_stats(all_results)
        
        logger.info(
            f"ReviewV3: run_review done - "
            f"total={stats['total_review_items']}, "
            f"pass={stats['pass_count']}, "
            f"fail={stats['fail_count']}, "
            f"warn={stats['warn_count']}, "
            f"mode={review_mode}"
        )
        
        return {
            "requirement_count": len(requirements),
            "response_count": len(responses),
            "rule_count": len(effective_rules),
            "finding_count": len(all_results),
            "review_mode": review_mode,
            **stats,
            "items": all_results
        }
    
    def _get_requirements(self, project_id: str) -> List[Dict[str, Any]]:
        """从 tender_requirements 读取招标要求"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, project_id, requirement_id, dimension, req_type,
                           requirement_text, is_hard, allow_deviation, value_schema_json,
                           evidence_chunk_ids
                    FROM tender_requirements
                    WHERE project_id = %s
                    ORDER BY dimension, requirement_id
                """, (project_id,))
                
                rows = cur.fetchall()
                return [
                    {
                        "id": row['id'],
                        "project_id": row['project_id'],
                        "requirement_id": row['requirement_id'],
                        "dimension": row['dimension'],
                        "req_type": row['req_type'],
                        "requirement_text": row['requirement_text'],
                        "is_hard": row['is_hard'],
                        "allow_deviation": row['allow_deviation'],
                        "value_schema_json": row['value_schema_json'],
                        "evidence_chunk_ids": row['evidence_chunk_ids']
                    }
                    for row in rows
                ]
    
    def _get_responses(self, project_id: str, bidder_name: str) -> List[Dict[str, Any]]:
        """从 tender_bid_response_items 读取投标响应"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, project_id, bidder_name, dimension, response_type,
                           response_text, extracted_value_json, evidence_chunk_ids
                    FROM tender_bid_response_items
                    WHERE project_id = %s AND bidder_name = %s
                    ORDER BY dimension
                """, (project_id, bidder_name))
                
                rows = cur.fetchall()
                return [
                    {
                        "id": row['id'],
                        "project_id": row['project_id'],
                        "bidder_name": row['bidder_name'],
                        "dimension": row['dimension'],
                        "response_type": row['response_type'],
                        "response_text": row['response_text'],
                        "extracted_value_json": row['extracted_value_json'],
                        "evidence_chunk_ids": row['evidence_chunk_ids']
                    }
                    for row in rows
                ]
    
    async def _handle_no_responses(
        self,
        project_id: str,
        bidder_name: str,
        requirements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """处理没有响应的情况：所有硬性要求都视为FAIL"""
        results = []
        
        for req in requirements:
            if req.get("is_hard", False):
                results.append({
                    "rule_id": None,
                    "rule_key": "no_response",
                    "requirement_id": req["requirement_id"],
                    "result": "FAIL",
                    "reason": f"未提供响应：{req.get('requirement_text', '')[:100]}",
                    "severity": "critical",
                    "evaluator": "system",
                    "dimension": req.get("dimension", "other")
                })
        
        # 落库
        self._save_review_items(project_id, bidder_name, results)
        
        stats = self._calculate_stats(results)
        
        return {
            **stats,
            "items": results
        }
    
    def _save_review_items(
        self,
        project_id: str,
        bidder_name: str,
        results: List[Dict[str, Any]]
    ):
        """保存审核结果到 tender_review_items"""
        if not results:
            return
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                # 先删除该投标人的旧审核结果
                cur.execute("""
                    DELETE FROM tender_review_items
                    WHERE project_id = %s AND bidder_name = %s
                """, (project_id, bidder_name))
                
                # 插入新结果
                for result in results:
                    item_id = str(uuid.uuid4())
                    
                    # 映射字段到表结构
                    tender_requirement = result.get("requirement_text", "")
                    bid_response_text = ""  # 暂时留空，后续可以从responses中查找
                    remark = result.get("reason", "")
                    
                    cur.execute("""
                        INSERT INTO tender_review_items (
                            id, project_id, bidder_name, dimension,
                            tender_requirement, bid_response, result, remark,
                            is_hard, rule_id, requirement_id, severity, evaluator
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        item_id,
                        project_id,
                        bidder_name,
                        result.get("dimension", "other"),
                        tender_requirement,
                        bid_response_text,
                        result.get("result", "FAIL"),
                        remark,
                        result.get("is_hard", False),
                        result.get("rule_id"),
                        result.get("requirement_id"),
                        result.get("severity", "medium"),
                        result.get("evaluator", "system")
                    ))
            
            conn.commit()
        
        logger.info(f"ReviewV3: Saved {len(results)} review items to database")
    
    def _calculate_stats(self, results: List[Dict[str, Any]]) -> Dict[str, int]:
        """计算统计信息"""
        total = len(results)
        pass_count = sum(1 for r in results if r.get("result", "").upper() == "PASS")
        fail_count = sum(1 for r in results if r.get("result", "").upper() == "FAIL")
        warn_count = sum(1 for r in results if r.get("result", "").upper() in ["WARN", "RISK"])
        
        return {
            "total_review_items": total,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "warn_count": warn_count
        }

