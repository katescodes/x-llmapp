"""
自定义规则服务
负责自定义规则的创建、查询、删除以及AI分析
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from app.services.llm_client import llm_json

logger = logging.getLogger(__name__)


class CustomRuleService:
    """自定义规则服务"""
    
    def __init__(self, pool):
        self.pool = pool
    
    def _get_cursor(self):
        """获取数据库游标的辅助方法"""
        return self.pool.connection()
    
    def create_rule_pack(
        self,
        project_id: str,
        pack_name: str,
        rule_requirements: str,
        model_id: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        创建自定义规则包
        
        1. 使用 AI 分析用户输入的规则要求
        2. 生成结构化规则
        3. 保存到数据库
        
        Args:
            project_id: 项目ID
            pack_name: 规则包名称
            rule_requirements: 规则要求文本（用户输入）
            model_id: 使用的模型ID
            owner_id: 所有者ID
            
        Returns:
            创建的规则包信息
        """
        logger.info(f"创建自定义规则包: {pack_name} (project_id={project_id})")
        
        # 1. AI 分析规则要求
        rules_data = self._analyze_rule_requirements(rule_requirements, model_id)
        
        # 2. 创建规则包
        pack_id = str(uuid.uuid4())
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tender_rule_packs (
                        id, pack_name, pack_type, project_id, priority, is_active
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, pack_name, pack_type, project_id, priority, is_active, created_at, updated_at
                    """,
                    (pack_id, pack_name, "custom", project_id, 10, True),
                )
                row = cur.fetchone()
        
        # 3. 批量插入规则
        if rules_data:
            self._batch_insert_rules(pack_id, rules_data)
        
        # 4. 返回规则包信息
        rule_pack = self.get_rule_pack(pack_id)
        
        logger.info(f"规则包创建成功: {pack_id}, 规则数量: {len(rules_data)}")
        
        return rule_pack
    
    def _analyze_rule_requirements(
        self,
        rule_requirements: str,
        model_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        使用 AI 分析规则要求，生成结构化规则
        
        Args:
            rule_requirements: 规则要求文本
            model_id: 模型ID
            
        Returns:
            规则列表
        """
        logger.info("开始 AI 分析规则要求")
        
        # 构建 Prompt
        prompt = self._build_rule_analysis_prompt(rule_requirements)
        
        try:
            # 调用 LLM
            result = llm_json(
                prompt=prompt,
                model_id=model_id,
                temperature=0.2,
                max_tokens=4000,
            )
            
            # 提取规则列表
            rules = result.get("rules", [])
            
            logger.info(f"AI 分析完成，生成 {len(rules)} 条规则")
            
            return rules
            
        except Exception as e:
            logger.error(f"AI 分析规则失败: {e}")
            # 返回空列表，不阻塞创建流程
            return []
    
    def _build_rule_analysis_prompt(self, rule_requirements: str) -> str:
        """构建规则分析 Prompt"""
        return f"""你是一个招投标审核规则分析专家。用户输入了一段规则要求文本，你需要将其转换为结构化的审核规则。

# 任务
分析用户输入的规则要求，生成结构化的审核规则列表。

# 规则要求文本
{rule_requirements}

# 输出格式
请输出严格的 JSON 格式（无任何额外文字或 markdown 标记）：

```json
{{
  "rules": [
    {{
      "rule_key": "unique_key_1",
      "rule_name": "规则名称",
      "dimension": "qualification|technical|business|price|doc_structure|schedule_quality|other",
      "evaluator": "deterministic|semantic_llm",
      "condition_json": {{
        "type": "检查类型（如: threshold_check, must_provide, must_not_deviate, format_check等）",
        "description": "规则描述",
        "parameters": {{
          "key1": "value1"
        }}
      }},
      "severity": "low|medium|high",
      "is_hard": true|false
    }}
  ]
}}
```

# 字段说明
- rule_key: 规则唯一标识，使用下划线命名（如: qual_registration_check）
- rule_name: 规则名称，简短清晰
- dimension: 规则适用维度
  - qualification: 资格审查
  - technical: 技术规格
  - business: 商务条款
  - price: 价格/报价
  - doc_structure: 文档结构/格式
  - schedule_quality: 进度/质量
  - other: 其他
- evaluator: 执行器类型
  - deterministic: 确定性判断（数值比较、格式检查等）
  - semantic_llm: LLM 语义判断（需要理解语义）
- condition_json: 条件配置（JSON对象）
  - type: 检查类型
  - description: 规则描述
  - parameters: 参数配置
- severity: 严重程度（low/medium/high）
- is_hard: 是否硬性规则（true=废标项，false=扣分项）

# 示例
输入："投标人必须具有有效的营业执照，且注册资本不低于500万元"
输出：
```json
{{
  "rules": [
    {{
      "rule_key": "qual_business_license",
      "rule_name": "营业执照检查",
      "dimension": "qualification",
      "evaluator": "semantic_llm",
      "condition_json": {{
        "type": "must_provide",
        "description": "投标人必须提供有效的营业执照",
        "parameters": {{
          "document_type": "营业执照",
          "validity_check": true
        }}
      }},
      "severity": "high",
      "is_hard": true
    }},
    {{
      "rule_key": "qual_registered_capital",
      "rule_name": "注册资本检查",
      "dimension": "qualification",
      "evaluator": "deterministic",
      "condition_json": {{
        "type": "threshold_check",
        "description": "注册资本不低于500万元",
        "parameters": {{
          "field": "registered_capital",
          "operator": ">=",
          "value": 5000000,
          "unit": "元"
        }}
      }},
      "severity": "high",
      "is_hard": true
    }}
  ]
}}
```

# 注意事项
1. 每条规则应该是原子性的，只检查一个具体的要求
2. 尽量将复杂的要求拆分成多条简单规则
3. 数值比较用 deterministic，语义理解用 semantic_llm
4. 废标项（硬性要求）设置 is_hard=true
5. 输出必须是有效的 JSON，不要包含注释或额外文字

现在开始分析：
"""
    
    def _batch_insert_rules(
        self,
        pack_id: str,
        rules_data: List[Dict[str, Any]],
    ):
        """批量插入规则"""
        if not rules_data:
            return
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                for rule in rules_data:
                    rule_id = str(uuid.uuid4())
                    
                    cur.execute(
                        """
                        INSERT INTO tender_rules (
                            id, rule_pack_id, rule_key, rule_name, dimension,
                            evaluator, condition_json, severity, is_hard
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            rule_id,
                            pack_id,
                            rule.get("rule_key", f"rule_{rule_id[:8]}"),
                            rule.get("rule_name", "未命名规则"),
                            rule.get("dimension", "other"),
                            rule.get("evaluator", "semantic_llm"),
                            json.dumps(rule.get("condition_json", {})),
                            rule.get("severity", "medium"),
                            rule.get("is_hard", False),
                        ),
                    )
    
    def list_rule_packs(
        self,
        project_id: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        列出自定义规则包
        
        Args:
            project_id: 项目ID（可选）
            owner_id: 所有者ID（可选）
            
        Returns:
            规则包列表
        """
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                sql = """
                SELECT 
                    rp.*,
                    COUNT(r.id) as rule_count
                FROM tender_rule_packs rp
                LEFT JOIN tender_rules r ON r.rule_pack_id = rp.id
                WHERE rp.pack_type = 'custom'
                """
                params = []
                
                if project_id:
                    sql += " AND rp.project_id = %s"
                    params.append(project_id)
                
                sql += " GROUP BY rp.id ORDER BY rp.created_at DESC"
                
                cur.execute(sql, params)
                rows = cur.fetchall()
        
        return [dict(row) for row in rows]
    
    def get_rule_pack(self, pack_id: str) -> Optional[Dict[str, Any]]:
        """获取单个规则包详情"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 
                        rp.*,
                        COUNT(r.id) as rule_count
                    FROM tender_rule_packs rp
                    LEFT JOIN tender_rules r ON r.rule_pack_id = rp.id
                    WHERE rp.id = %s
                    GROUP BY rp.id
                    """,
                    (pack_id,),
                )
                row = cur.fetchone()
        
        return dict(row) if row else None
    
    def delete_rule_pack(self, pack_id: str):
        """删除规则包（级联删除所有规则）"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM tender_rule_packs WHERE id = %s",
                    (pack_id,),
                )
        
        logger.info(f"规则包已删除: {pack_id}")
    
    def list_rules(self, pack_id: str) -> List[Dict[str, Any]]:
        """列出规则包中的所有规则"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM tender_rules
                    WHERE rule_pack_id = %s
                    ORDER BY created_at
                    """,
                    (pack_id,),
                )
                rows = cur.fetchall()
        
        return [dict(row) for row in rows]
    
    def get_effective_rules_for_project(
        self,
        project_id: str,
        selected_pack_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取项目的有效规则集
        
        合并规则包的规则，按优先级处理覆盖
        
        Args:
            project_id: 项目ID
            selected_pack_ids: 选中的规则包ID列表（可选）
            
        Returns:
            有效规则列表
        """
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                sql = """
                SELECT r.*
                FROM tender_rules r
                INNER JOIN tender_rule_packs rp ON rp.id = r.rule_pack_id
                WHERE rp.is_active = true
                """
                params = []
                
                if selected_pack_ids:
                    sql += " AND rp.id = ANY(%s)"
                    params.append(selected_pack_ids)
                else:
                    # 默认：内置规则 + 项目自定义规则
                    sql += """ AND (
                        rp.pack_type = 'builtin'
                        OR (rp.pack_type = 'custom' AND rp.project_id = %s)
                    )
                    """
                    params.append(project_id)
                
                sql += " ORDER BY rp.priority DESC, r.created_at"
                
                cur.execute(sql, params)
                rows = cur.fetchall()
        
        # 去重：同 rule_key 保留高优先级的
        rules_dict = {}
        for row in rows:
            rule = dict(row)
            rule_key = rule["rule_key"]
            
            if rule_key not in rules_dict:
                rules_dict[rule_key] = rule
        
        return list(rules_dict.values())

