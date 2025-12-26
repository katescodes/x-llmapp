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

from app.works.tender.dao import TenderDAO
from app.works.tender.rules.effective_ruleset import EffectiveRulesetBuilder
from app.works.tender.rules.deterministic_engine import DeterministicRuleEngine
from app.works.tender.rules.semantic_llm_engine import SemanticLLMRuleEngine

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
    
    async def run_review_v3(
        self,
        project_id: str,
        bidder_name: str,
        model_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        运行审核 V3
        
        Args:
            project_id: 项目ID
            bidder_name: 投标人名称
            model_id: LLM模型ID
            run_id: 运行ID（可选）
        
        Returns:
            {
                "total_review_items": 50,
                "pass_count": 30,
                "fail_count": 15,
                "warn_count": 5,
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
        effective_rules = self.ruleset_builder.build_effective_ruleset(project_id)
        logger.info(f"ReviewV3: Built effective ruleset with {len(effective_rules)} rules")
        
        # 4. 分离确定性规则和语义LLM规则
        deterministic_rules = [r for r in effective_rules if r["rule_type"] == "deterministic"]
        semantic_rules = [r for r in effective_rules if r["rule_type"] == "semantic_llm"]
        
        logger.info(
            f"ReviewV3: deterministic_rules={len(deterministic_rules)}, "
            f"semantic_rules={len(semantic_rules)}"
        )
        
        # 5. 执行确定性规则
        deterministic_results = self.deterministic_engine.evaluate_rules(
            rules=deterministic_rules,
            requirements=requirements,
            responses=responses
        )
        logger.info(f"ReviewV3: Deterministic engine produced {len(deterministic_results)} results")
        
        # 6. 执行语义LLM规则
        semantic_results = await self.semantic_engine.evaluate_rules(
            rules=semantic_rules,
            requirements=requirements,
            responses=responses,
            model_id=model_id
        )
        logger.info(f"ReviewV3: Semantic engine produced {len(semantic_results)} results")
        
        # 7. 合并结果
        all_results = deterministic_results + semantic_results
        
        # 8. 落库到 tender_review_items
        self._save_review_items(project_id, bidder_name, all_results)
        
        # 9. 统计
        stats = self._calculate_stats(all_results)
        
        logger.info(
            f"ReviewV3: run_review done - "
            f"total={stats['total_review_items']}, "
            f"pass={stats['pass_count']}, "
            f"fail={stats['fail_count']}, "
            f"warn={stats['warn_count']}"
        )
        
        return {
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
                        "id": row[0],
                        "project_id": row[1],
                        "requirement_id": row[2],
                        "dimension": row[3],
                        "req_type": row[4],
                        "requirement_text": row[5],
                        "is_hard": row[6],
                        "allow_deviation": row[7],
                        "value_schema_json": row[8],
                        "evidence_chunk_ids": row[9]
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
                        "id": row[0],
                        "project_id": row[1],
                        "bidder_name": row[2],
                        "dimension": row[3],
                        "response_type": row[4],
                        "response_text": row[5],
                        "extracted_value_json": row[6],
                        "evidence_chunk_ids": row[7]
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
                    
                    cur.execute("""
                        INSERT INTO tender_review_items (
                            id, project_id, bidder_name, dimension,
                            item_type, result, description,
                            rule_id, requirement_id, severity, evaluator
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        item_id,
                        project_id,
                        bidder_name,
                        result.get("dimension", "other"),
                        result.get("rule_key", "unknown"),  # item_type
                        result.get("result", "FAIL"),
                        result.get("reason", ""),  # description
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

