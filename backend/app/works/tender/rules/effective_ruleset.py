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
    ) -> List[Dict[str, Any]]:
        """
        构建有效规则集
        
        规则合并策略：
        1. 加载系统内置规则（is_system_default=true）
        2. 加载项目级自定义规则（project_id匹配）
        3. 按 priority 升序排序（数字越小优先级越高）
        4. 同 rule_key 的规则，项目级覆盖系统级
        
        Args:
            project_id: 项目ID
            include_system_defaults: 是否包含系统内置规则
            include_project_rules: 是否包含项目自定义规则
        
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
                # 1. 加载系统内置规则
                if include_system_defaults:
                    cur.execute("""
                        SELECT r.id, r.rule_key, r.name, r.description, r.priority,
                               r.severity, r.rule_type, r.condition_json, r.action_json,
                               r.is_active, rp.name as rule_pack_name
                        FROM tender_rules r
                        JOIN tender_rule_packs rp ON r.rule_pack_id = rp.id
                        WHERE rp.is_system_default = true
                          AND r.is_active = true
                        ORDER BY r.priority ASC
                    """)
                    
                    system_rules = cur.fetchall()
                    for row in system_rules:
                        all_rules.append({
                            "id": row[0],
                            "rule_key": row[1],
                            "name": row[2],
                            "description": row[3],
                            "priority": row[4],
                            "severity": row[5],
                            "rule_type": row[6],
                            "condition_json": row[7],
                            "action_json": row[8],
                            "is_active": row[9],
                            "rule_pack_name": row[10],
                            "source": "system_default"
                        })
                
                # 2. 加载项目级自定义规则
                if include_project_rules:
                    cur.execute("""
                        SELECT r.id, r.rule_key, r.name, r.description, r.priority,
                               r.severity, r.rule_type, r.condition_json, r.action_json,
                               r.is_active, rp.name as rule_pack_name
                        FROM tender_rules r
                        JOIN tender_rule_packs rp ON r.rule_pack_id = rp.id
                        WHERE rp.project_id = %s
                          AND r.is_active = true
                        ORDER BY r.priority ASC
                    """, (project_id,))
                    
                    project_rules = cur.fetchall()
                    for row in project_rules:
                        all_rules.append({
                            "id": row[0],
                            "rule_key": row[1],
                            "name": row[2],
                            "description": row[3],
                            "priority": row[4],
                            "severity": row[5],
                            "rule_type": row[6],
                            "condition_json": row[7],
                            "action_json": row[8],
                            "is_active": row[9],
                            "rule_pack_name": row[10],
                            "source": "project_custom"
                        })
        
        # 3. 去重：同 rule_key 的规则，项目级覆盖系统级
        effective_rules = self._deduplicate_by_rule_key(all_rules)
        
        # 4. 按 priority 排序
        effective_rules.sort(key=lambda r: r["priority"])
        
        logger.info(
            f"EffectiveRuleset: Built ruleset with {len(effective_rules)} rules "
            f"(system={sum(1 for r in effective_rules if r['source'] == 'system_default')}, "
            f"project={sum(1 for r in effective_rules if r['source'] == 'project_custom')})"
        )
        
        return effective_rules
    
    def _deduplicate_by_rule_key(self, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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

