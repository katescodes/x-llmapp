"""
审核服务 V3 - 固定流水线模式

使用 ReviewPipelineV3 实现分层审核：
1. Mapping: 构建候选对
2. Hard Gate: 硬性审核
3. Quant Checks: 量化检查
4. Semantic Escalation: 语义升级
5. Consistency: 一致性检查
6. Aggregate: 汇总统计

✨ 增强：支持自定义规则包集成
"""
import logging
import uuid
from typing import Any, Dict, List, Optional

from app.works.tender.review_pipeline_v3 import ReviewPipelineV3

logger = logging.getLogger(__name__)


class ReviewV3Service:
    """审核服务 V3 - 固定流水线"""
    
    def __init__(self, pool: Any, llm_orchestrator: Any = None):
        self.pool = pool
        self.llm = llm_orchestrator
        self.pipeline = ReviewPipelineV3(pool, llm_orchestrator)
    
    async def run_review_v3(
        self,
        project_id: str,
        bidder_name: str,
        model_id: Optional[str] = None,
        custom_rule_pack_ids: Optional[List[str]] = None,
        run_id: Optional[str] = None,
        use_llm_semantic: bool = True,
    ) -> Dict[str, Any]:
        """
        运行审核 V3（固定流水线）
        
        Args:
            project_id: 项目ID
            bidder_name: 投标人名称
            model_id: LLM模型ID
            custom_rule_pack_ids: ✨ 自定义规则包ID列表（启用）
            run_id: 运行ID（可选）
            use_llm_semantic: 是否使用LLM语义审核（默认True）
        
        Returns:
            {
                "total_review_items": 50,
                "pass_count": 30,
                "fail_count": 15,
                "warn_count": 5,
                "pending_count": 3,
                "review_mode": "FIXED_PIPELINE",
                "custom_rules_applied": 5,  # ✨ 新增统计
                "items": [...]
            }
        """
        logger.info(f"ReviewV3: run_review start project_id={project_id}, bidder={bidder_name}")
        logger.info(f"ReviewV3: Using FIXED_PIPELINE mode")
        
        # ✨ 加载自定义规则包（如果指定）
        virtual_requirements = []
        custom_rule_count = 0
        
        if custom_rule_pack_ids:
            logger.info(f"ReviewV3: Loading custom rule packs: {custom_rule_pack_ids}")
            virtual_requirements = self._load_and_convert_custom_rules(custom_rule_pack_ids, project_id)
            custom_rule_count = len(virtual_requirements)
            logger.info(f"ReviewV3: Loaded {custom_rule_count} custom rules as virtual requirements")
        
        # 使用固定流水线（传入虚拟requirements）
        result = await self.pipeline.run_pipeline(
            project_id=project_id,
            bidder_name=bidder_name,
            model_id=model_id,
            use_llm_semantic=use_llm_semantic,
            review_run_id=run_id,
            extra_requirements=virtual_requirements,  # ✨ 新增参数
        )
        
        return {
            "review_mode": "FIXED_PIPELINE",
            "custom_rules_applied": custom_rule_count,  # ✨ 新增统计
            **result["stats"],
            "items": result["review_items"]
        }
    
    def _load_and_convert_custom_rules(
        self,
        rule_pack_ids: List[str],
        project_id: str
    ) -> List[Dict[str, Any]]:
        """
        加载自定义规则包并转换为虚拟招标要求
        
        Args:
            rule_pack_ids: 规则包ID列表
            project_id: 项目ID
            
        Returns:
            虚拟requirements列表
        """
        virtual_requirements = []
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                # 加载所有启用的规则
                placeholders = ','.join(['%s'] * len(rule_pack_ids))
                cur.execute(f"""
                    SELECT 
                        r.id,
                        r.rule_pack_id,
                        r.rule_key,
                        r.rule_name,
                        r.dimension,
                        r.evaluator,
                        r.condition_json,
                        r.severity,
                        r.is_hard,
                        rp.pack_name
                    FROM tender_rules r
                    JOIN tender_rule_packs rp ON rp.id = r.rule_pack_id
                    WHERE r.rule_pack_id IN ({placeholders})
                      AND rp.is_active = true
                    ORDER BY rp.priority DESC, r.created_at ASC
                """, tuple(rule_pack_ids))
                
                rules = cur.fetchall()
        
        logger.info(f"ReviewV3: Found {len(rules)} active rules from {len(rule_pack_ids)} packs")
        
        for rule in rules:
            (rule_id, rule_pack_id, rule_key, rule_name, dimension, 
             evaluator, condition_json, severity, is_hard, pack_name) = rule
            
            # 转换为虚拟requirement
            virtual_req = self._convert_rule_to_requirement(
                rule_id=rule_id,
                rule_pack_id=rule_pack_id,
                rule_key=rule_key,
                rule_name=rule_name,
                dimension=dimension,
                evaluator=evaluator,
                condition_json=condition_json,
                severity=severity,
                is_hard=is_hard,
                pack_name=pack_name,
                project_id=project_id
            )
            
            virtual_requirements.append(virtual_req)
            
            logger.debug(f"ReviewV3: Converted rule {rule_key} → virtual requirement")
        
        return virtual_requirements
    
    def _convert_rule_to_requirement(
        self,
        rule_id: str,
        rule_pack_id: str,
        rule_key: str,
        rule_name: str,
        dimension: str,
        evaluator: str,
        condition_json: Dict[str, Any],
        severity: str,
        is_hard: bool,
        pack_name: str,
        project_id: str
    ) -> Dict[str, Any]:
        """
        将自定义规则转换为虚拟招标要求格式
        
        规则优先级：自定义规则 > 招标要求（用户明确）
        """
        # 生成虚拟requirement ID
        virtual_id = f"custom_{rule_id}"
        
        # ✅ 确保 condition_json 是字典类型（从数据库读取可能是字符串）
        if isinstance(condition_json, str):
            import json
            try:
                condition_json = json.loads(condition_json)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse condition_json for rule {rule_id}, using empty dict")
                condition_json = {}
        
        # 构建requirement_text
        description = condition_json.get("description", "")
        requirement_text = f"【{pack_name}】{rule_name}"
        if description:
            requirement_text += f": {description}"
        
        # 确定req_type
        if evaluator == "deterministic":
            # 确定性规则 → NUMERIC 或 PRESENCE
            check_type = condition_json.get("type", "").lower()
            if "threshold" in check_type or "比较" in check_type:
                req_type = "NUMERIC"
            elif "must_provide" in check_type or "必须提供" in check_type:
                req_type = "PRESENCE"
            else:
                req_type = "VALIDITY"
        elif evaluator == "semantic_llm":
            # 语义规则 → SEMANTIC
            req_type = "SEMANTIC"
        else:
            req_type = "SEMANTIC"  # 默认语义审核
        
        # 映射dimension
        dimension_map = {
            "qualification": "qualification",
            "technical": "technical",
            "business": "business",
            "price": "price",
            "doc_structure": "doc_structure",
            "schedule_quality": "schedule_quality",
            "other": "other"
        }
        mapped_dimension = dimension_map.get(dimension, dimension)
        
        # 构建虚拟requirement
        virtual_req = {
            "id": virtual_id,
            "project_id": project_id,
            "dimension": mapped_dimension,
            "requirement_text": requirement_text,
            "req_type": req_type,
            "is_hard": is_hard,
            "allow_deviation": False,  # 自定义规则默认不允许偏离
            "value_constraint": None,
            "evidence_chunk_ids": [],
            "normalized_fields_json": {},
            
            # ✨ 自定义规则专属字段
            "source": "custom_rule",  # 标记来源
            "rule_pack_id": rule_pack_id,
            "rule_key": rule_key,
            "rule_name": rule_name,
            "evaluator_hint": evaluator,  # 指导流水线路由
            "condition_dsl": condition_json,  # 原始DSL，供执行器使用
            "severity": severity,
            "pack_name": pack_name,
            
            # 元数据
            "meta_json": {
                "custom_rule": True,
                "priority": "high",  # 自定义规则优先级更高
                "original_rule_id": rule_id
            }
        }
        
        return virtual_req
