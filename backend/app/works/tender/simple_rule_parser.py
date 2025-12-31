"""
简化规则解析器 - 让用户只需输入规则文本即可参与审核

用户输入格式示例：
```
维度：资格条件
规则：投标人注册资本不得低于1000万元
类型：硬性
严重程度：高
```

或简化格式：
```
投标人注册资本不得低于1000万元（硬性要求）
```
"""
import logging
import re
import uuid
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class SimpleRuleParser:
    """简化规则解析器"""
    
    # 维度关键词映射
    DIMENSION_KEYWORDS = {
        "资格": "qualification",
        "qualification": "qualification",
        "技术": "technical",
        "technical": "technical",
        "商务": "business",
        "business": "business",
        "报价": "price",
        "价格": "price",
        "price": "price",
        "工期": "schedule_quality",
        "质量": "schedule_quality",
        "schedule": "schedule_quality",
        "文档": "doc_structure",
        "格式": "doc_structure",
        "doc": "doc_structure",
        "其他": "other",
        "other": "other",
    }
    
    # 硬性要求关键词
    HARD_KEYWORDS = ["硬性", "必须", "强制", "不得", "严禁", "不允许", "废标", "拒绝"]
    
    # 严重程度关键词
    SEVERITY_KEYWORDS = {
        "低": "low",
        "中": "medium",
        "高": "high",
        "critical": "critical",
        "严重": "high",
    }
    
    def parse_simple_rules(self, rule_text: str) -> List[Dict[str, Any]]:
        """
        解析简化规则文本
        
        支持两种格式：
        1. 结构化格式（包含维度、规则、类型等字段）
        2. 自由文本格式（系统自动推断）
        
        Args:
            rule_text: 规则文本（可以是多条规则，用换行分隔）
        
        Returns:
            规则列表
        """
        rules = []
        
        # 按空行分隔多条规则
        rule_blocks = re.split(r'\n\s*\n', rule_text.strip())
        
        for block in rule_blocks:
            if not block.strip():
                continue
            
            rule = self._parse_single_rule(block.strip())
            if rule:
                rules.append(rule)
        
        logger.info(f"解析了 {len(rules)} 条规则")
        return rules
    
    def _parse_single_rule(self, text: str) -> Optional[Dict[str, Any]]:
        """解析单条规则"""
        # 尝试结构化格式
        structured = self._try_parse_structured(text)
        if structured:
            return structured
        
        # 降级：自由文本格式
        return self._parse_freetext(text)
    
    def _try_parse_structured(self, text: str) -> Optional[Dict[str, Any]]:
        """尝试解析结构化格式"""
        lines = text.split('\n')
        
        fields = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 匹配 "字段：值" 格式
            match = re.match(r'(维度|规则|类型|严重程度|说明|标签)[:：]\s*(.+)', line)
            if match:
                key, value = match.groups()
                fields[key] = value.strip()
        
        # 必须有"规则"字段
        if "规则" not in fields:
            return None
        
        rule_check = fields["规则"]
        
        # 推断维度
        dimension = "other"
        if "维度" in fields:
            dimension = self._infer_dimension(fields["维度"])
        else:
            dimension = self._infer_dimension(rule_check)
        
        # 推断是否硬性
        is_hard = False
        if "类型" in fields:
            is_hard = any(kw in fields["类型"] for kw in ["硬性", "强制", "必须"])
        else:
            is_hard = self._is_hard_requirement(rule_check)
        
        # 推断严重程度
        severity = "medium"
        if "严重程度" in fields:
            severity = self._infer_severity(fields["严重程度"])
        elif is_hard:
            severity = "high"
        
        # 提取标签
        tags = []
        if "标签" in fields:
            tags = [t.strip() for t in fields["标签"].split(',')]
        
        return {
            "rule_key": f"custom_{uuid.uuid4().hex[:8]}",
            "rule_name": rule_check[:50],  # 使用规则文本前50字作为名称
            "dimension": dimension,
            "check": rule_check,
            "rigid": is_hard,
            "severity": severity,
            "tags": tags,
            "description": fields.get("说明", ""),
        }
    
    def _parse_freetext(self, text: str) -> Dict[str, Any]:
        """解析自由文本格式"""
        # 推断维度
        dimension = self._infer_dimension(text)
        
        # 推断是否硬性
        is_hard = self._is_hard_requirement(text)
        
        # 推断严重程度
        severity = "high" if is_hard else "medium"
        
        # 提取可能的标签（从文本中识别关键词）
        tags = self._extract_tags(text)
        
        return {
            "rule_key": f"custom_{uuid.uuid4().hex[:8]}",
            "rule_name": text[:50],
            "dimension": dimension,
            "check": text,
            "rigid": is_hard,
            "severity": severity,
            "tags": tags,
            "description": "",
        }
    
    def _infer_dimension(self, text: str) -> str:
        """从文本推断维度"""
        text_lower = text.lower()
        
        # 资格条件关键词
        if any(kw in text for kw in ["资格", "资质", "营业执照", "注册资本", "业绩", "人员", "证书"]):
            return "qualification"
        
        # 技术要求关键词
        if any(kw in text for kw in ["技术", "参数", "性能", "规格", "方案", "设备"]):
            return "technical"
        
        # 商务条款关键词
        if any(kw in text for kw in ["商务", "质保", "售后", "服务", "培训", "交付"]):
            return "business"
        
        # 报价关键词
        if any(kw in text for kw in ["报价", "价格", "总价", "单价", "费用", "成本"]):
            return "price"
        
        # 工期质量关键词
        if any(kw in text for kw in ["工期", "进度", "质量", "验收", "交付时间"]):
            return "schedule_quality"
        
        # 文档格式关键词
        if any(kw in text for kw in ["文档", "格式", "装订", "签字", "盖章", "份数"]):
            return "doc_structure"
        
        return "other"
    
    def _is_hard_requirement(self, text: str) -> bool:
        """判断是否硬性要求"""
        return any(kw in text for kw in self.HARD_KEYWORDS)
    
    def _infer_severity(self, text: str) -> str:
        """推断严重程度"""
        for keyword, severity in self.SEVERITY_KEYWORDS.items():
            if keyword in text.lower():
                return severity
        return "medium"
    
    def _extract_tags(self, text: str) -> List[str]:
        """从文本提取标签"""
        tags = []
        
        # 预定义标签关键词
        tag_keywords = {
            "资质": ["资质", "证书", "认证"],
            "业绩": ["业绩", "案例", "项目"],
            "资金": ["注册资本", "资金", "财务"],
            "报价": ["报价", "价格"],
            "工期": ["工期", "进度"],
            "质量": ["质量", "标准"],
            "服务": ["服务", "售后"],
        }
        
        for tag, keywords in tag_keywords.items():
            if any(kw in text for kw in keywords):
                tags.append(tag)
        
        return tags
    
    def save_rules_to_pack(
        self,
        pool,
        project_id: str,
        pack_name: str,
        rules: List[Dict[str, Any]],
        owner_id: Optional[str] = None,
    ) -> str:
        """
        将解析的规则保存到规则包
        
        Args:
            pool: 数据库连接池
            project_id: 项目ID
            pack_name: 规则包名称
            rules: 规则列表
            owner_id: 所有者ID
        
        Returns:
            规则包ID
        """
        import uuid as uuid_lib
        from psycopg.types.json import Json
        
        pack_id = str(uuid_lib.uuid4())
        
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # 1. 创建规则包
                cur.execute("""
                    INSERT INTO tender_rule_packs (
                        id, pack_name, pack_type, project_id, priority, is_active
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    pack_id,
                    pack_name,
                    "custom",
                    project_id,
                    100,  # 高优先级
                    True,
                ))
                
                # 2. 保存规则
                for rule in rules:
                    rule_id = str(uuid_lib.uuid4())
                    
                    # 构建condition_json（用于审核引擎）
                    condition_json = {
                        "check_type": "semantic" if rule["rigid"] else "soft",
                        "check_description": rule["check"],
                    }
                    
                    # 推断evaluator类型
                    evaluator = "semantic_llm"
                    if any(kw in rule["check"] for kw in ["不得低于", "不得高于", "等于", "大于", "小于"]):
                        evaluator = "deterministic"
                    
                    cur.execute("""
                        INSERT INTO tender_rules (
                            id, rule_pack_id, rule_key, rule_name, dimension,
                            evaluator, condition_json, severity, is_hard
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        rule_id,
                        pack_id,
                        rule["rule_key"],
                        rule["rule_name"],
                        rule["dimension"],
                        evaluator,
                        Json(condition_json),
                        rule["severity"],
                        rule["rigid"],
                    ))
            
            conn.commit()
        
        logger.info(f"保存了 {len(rules)} 条规则到规则包 {pack_id}")
        return pack_id


def create_rules_from_text(
    pool,
    project_id: str,
    rule_text: str,
    pack_name: Optional[str] = None,
    owner_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    便捷函数：从文本创建规则并保存
    
    Args:
        pool: 数据库连接池
        project_id: 项目ID
        rule_text: 规则文本
        pack_name: 规则包名称（可选）
        owner_id: 所有者ID
    
    Returns:
        {
            "pack_id": "规则包ID",
            "rules_count": 3,
            "rules": [...]
        }
    """
    parser = SimpleRuleParser()
    
    # 解析规则
    rules = parser.parse_simple_rules(rule_text)
    
    if not rules:
        raise ValueError("未能从文本中解析出有效规则")
    
    # 生成规则包名称
    if not pack_name:
        pack_name = f"自定义规则_{len(rules)}条"
    
    # 保存到数据库
    pack_id = parser.save_rules_to_pack(
        pool=pool,
        project_id=project_id,
        pack_name=pack_name,
        rules=rules,
        owner_id=owner_id,
    )
    
    return {
        "pack_id": pack_id,
        "pack_name": pack_name,
        "rules_count": len(rules),
        "rules": rules,
    }

