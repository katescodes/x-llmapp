"""
有效规则集构建器 (Effective Ruleset Builder)

合并系统内置规则和用户自定义规则，生成最终的有效规则集
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EffectiveRulesetBuilder:
    """有效规则集构建器"""
    
    def __init__(self, pool: Any):
        self.pool = pool
    
    def build_effective_ruleset(
        self,
        project_id: str,
        include_system_defaults: bool = True,
        include_project_rules: bool = True,
        custom_rule_pack_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        构建有效规则集
        
        规则合并策略：
        1. 加载系统内置规则（is_system_default=true）
        2. 加载项目级自定义规则（project_id匹配）
        3. 加载自定义规则包（custom_rule_pack_ids）
        4. 按 priority 升序排序（数字越小优先级越高）
        5. 同 rule_key 的规则，项目级/自定义覆盖系统级
        
        Args:
            project_id: 项目ID
            include_system_defaults: 是否包含系统内置规则
            include_project_rules: 是否包含项目自定义规则
            custom_rule_pack_ids: 自定义规则包ID列表（可选）
        
        Returns:
            有效规则列表，按 priority 升序排序
        """
        logger.info(
            f"EffectiveRuleset: Building ruleset for project={project_id}, "
            f"system={include_system_defaults}, project={include_project_rules}"
        )
        
        all_rules = []
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                # 1. 加载系统内置规则（pack_type = 'system'）
                if include_system_defaults:
                    cur.execute("""
                        SELECT r.id, r.rule_key, r.rule_name, r.dimension, 
                               r.evaluator, r.severity, r.condition_json, r.is_hard,
                               rp.pack_name as rule_pack_name
                        FROM tender_rules r
                        JOIN tender_rule_packs rp ON r.rule_pack_id = rp.id
                        WHERE rp.pack_type = 'system'
                          AND rp.is_active = true
                        ORDER BY rp.priority ASC, r.rule_key ASC
                    """)
                    
                    system_rules = cur.fetchall()
                    for row in system_rules:
                        all_rules.append({
                            "id": row['id'],
                            "rule_key": row['rule_key'],
                            "name": row['rule_name'],
                            "dimension": row['dimension'],
                            "evaluator": row['evaluator'],
                            "severity": row['severity'],
                            "condition_json": row['condition_json'],
                            "is_hard": row['is_hard'],
                            "rule_pack_name": row['rule_pack_name'],
                            "source": "system_default"
                        })
                
                # 2. 加载项目级自定义规则（project_id = 当前项目）
                if include_project_rules:
                    cur.execute("""
                        SELECT r.id, r.rule_key, r.rule_name, r.dimension,
                               r.evaluator, r.severity, r.condition_json, r.is_hard,
                               rp.pack_name as rule_pack_name
                        FROM tender_rules r
                        JOIN tender_rule_packs rp ON r.rule_pack_id = rp.id
                        WHERE rp.project_id = %s
                          AND rp.is_active = true
                        ORDER BY rp.priority ASC, r.rule_key ASC
                    """, (project_id,))
                    
                    project_rules = cur.fetchall()
                    for row in project_rules:
                        all_rules.append({
                            "id": row['id'],
                            "rule_key": row['rule_key'],
                            "name": row['rule_name'],
                            "dimension": row['dimension'],
                            "evaluator": row['evaluator'],
                            "severity": row['severity'],
                            "condition_json": row['condition_json'],
                            "is_hard": row['is_hard'],
                            "rule_pack_name": row['rule_pack_name'],
                            "source": "project_custom"
                        })
                
                # 3. 加载用户选择的自定义规则包中的规则
                if custom_rule_pack_ids:
                    from psycopg.sql import SQL, Identifier
                    placeholders = ','.join(['%s'] * len(custom_rule_pack_ids))
                    cur.execute(f"""
                        SELECT r.id, r.rule_key, r.rule_name, r.dimension,
                               r.evaluator, r.severity, r.condition_json, r.is_hard,
                               rp.pack_name as rule_pack_name
                        FROM tender_rules r
                        JOIN tender_rule_packs rp ON r.rule_pack_id = rp.id
                        WHERE rp.id IN ({placeholders})
                          AND rp.is_active = true
                        ORDER BY rp.priority ASC, r.rule_key ASC
                    """, tuple(custom_rule_pack_ids))
                    
                    custom_rules = cur.fetchall()
                    logger.info(f"EffectiveRuleset: Loaded {len(custom_rules)} rules from {len(custom_rule_pack_ids)} custom rule packs")
                    for row in custom_rules:
                        all_rules.append({
                            "id": row['id'],
                            "rule_key": row['rule_key'],
                            "name": row['rule_name'],
                            "dimension": row['dimension'],
                            "evaluator": row['evaluator'],
                            "severity": row['severity'],
                            "condition_json": row['condition_json'],
                            "is_hard": row['is_hard'],
                            "rule_pack_name": row['rule_pack_name'],
                            "source": "user_selected_custom"
                        })
        
        # 4. 去重：同 rule_key 的规则，项目级/用户选择覆盖系统级
        effective_rules = self._deduplicate_by_rule_key(all_rules)
        
        # 5. 去重：按 rule_key 去重，优先级：user_selected_custom > project_custom > system_default
        seen_keys = set()
        effective_rules = []
        for rule in all_rules:
            if rule["rule_key"] not in seen_keys:
                effective_rules.append(rule)
                seen_keys.add(rule["rule_key"])
        
        logger.info(
            f"EffectiveRuleset: Built ruleset with {len(effective_rules)} rules "
            f"(system={sum(1 for r in effective_rules if r['source'] == 'system_default')}, "
            f"project={sum(1 for r in effective_rules if r['source'] == 'project_custom')}, "
            f"custom={sum(1 for r in effective_rules if r['source'] == 'user_selected_custom')})"
        )
        
        return effective_rules
    
    def _deduplicate_by_rule_key(self, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        按 rule_key 去重，项目级/用户选择覆盖系统级
        
        策略：
        - 同 rule_key 的规则，优先级: user_selected_custom > project_custom > system_default
        - 保留优先级最高的规则
        """
        rule_map = {}
        source_priority = {
            "user_selected_custom": 3,
            "project_custom": 2,
            "system_default": 1
        }
        
        for rule in rules:
            rule_key = rule["rule_key"]
            
            if rule_key not in rule_map:
                rule_map[rule_key] = rule
            else:
                # 根据source优先级决定是否覆盖
                current_priority = source_priority.get(rule["source"], 0)
                existing_priority = source_priority.get(rule_map[rule_key]["source"], 0)
                if current_priority > existing_priority:
                    rule_map[rule_key] = rule
                    logger.info(f"EffectiveRuleset: Rule '{rule_key}' overridden by {rule['source']}")
        
        return list(rule_map.values())
        """
        按 rule_key 去重，项目级覆盖系统级
        
        策略：
        - 同 rule_key 的规则，保留 source='project_custom' 的
        - 如果只有系统级，则保留系统级
        """
        rule_map = {}
        
        for rule in rules:
            rule_key = rule["rule_key"]
            
            if rule_key not in rule_map:
                rule_map[rule_key] = rule
            else:
                # 如果当前是项目级，覆盖系统级
                if rule["source"] == "project_custom":
                    if rule_map[rule_key]["source"] == "system_default":
                        logger.info(
                            f"EffectiveRuleset: Overriding system rule '{rule_key}' "
                            f"with project custom rule"
                        )
                        rule_map[rule_key] = rule
                    else:
                        # 两个都是项目级，保留 priority 更小的
                        if rule["priority"] < rule_map[rule_key]["priority"]:
                            rule_map[rule_key] = rule
                # 如果当前是系统级，且已有项目级，不覆盖
                elif rule["source"] == "system_default" and rule_map[rule_key]["source"] == "project_custom":
                    pass  # 保留项目级
                # 两个都是系统级，保留 priority 更小的
                elif rule["priority"] < rule_map[rule_key]["priority"]:
                    rule_map[rule_key] = rule
        
        return list(rule_map.values())
    
    def get_rules_by_type(
        self,
        project_id: str,
        rule_type: str
    ) -> List[Dict[str, Any]]:
        """
        获取指定类型的有效规则
        
        Args:
            project_id: 项目ID
            rule_type: 规则类型（deterministic | semantic_llm）
        
        Returns:
            指定类型的规则列表
        """
        effective_rules = self.build_effective_ruleset(project_id)
        return [r for r in effective_rules if r["rule_type"] == rule_type]

