"""
风险分析服务 - 从 tender_requirements 聚合生成风险分析两张表
"""
import logging
import re
from typing import Any, Dict, List
from psycopg_pool import ConnectionPool

from ..schemas.risk_analysis import (
    RiskRow,
    ChecklistRow,
    RiskAnalysisStats,
    RiskAnalysisResponse,
)

logger = logging.getLogger(__name__)


# 维度优先级映射
DIMENSION_PRIORITY = {
    "qualification": 1,
    "price": 2,
    "doc_structure": 3,
    "bid_security": 4,
    "technical": 5,
    "business": 6,
    "schedule_quality": 7,
    "other": 8,
}

# 要求类型优先级映射
REQ_TYPE_PRIORITY = {
    "must_provide": 1,
    "must_not_deviate": 2,
    "threshold": 3,
    "format": 4,
    "scoring": 5,
    "other": 6,
}

# 后果优先级映射
CONSEQUENCE_PRIORITY = {
    "reject": 1,
    "hard_requirement": 2,
    "score_loss": 3,
}

# 严重性优先级映射
SEVERITY_PRIORITY = {
    "high": 1,
    "medium": 2,
    "low": 3,
}


class RiskAnalysisService:
    """风险分析服务"""
    
    def __init__(self, pool: ConnectionPool):
        self.pool = pool
    
    def build_risk_analysis(self, project_id: str) -> RiskAnalysisResponse:
        """
        构建风险分析数据
        
        Args:
            project_id: 项目ID
            
        Returns:
            RiskAnalysisResponse: 包含两张表和统计信息
        """
        # 1. 从数据库读取 tender_requirements
        requirements = self._get_requirements(project_id)
        
        if not requirements:
            return RiskAnalysisResponse(
                must_reject_table=[],
                checklist_table=[],
                stats=RiskAnalysisStats(
                    total_requirements=0,
                    must_reject_count=0,
                    checklist_count=0,
                    high_severity_count=0,
                    medium_severity_count=0,
                    low_severity_count=0,
                )
            )
        
        # 2. 分类处理
        must_reject_table = []
        checklist_table = []
        
        for req in requirements:
            if req["is_hard"]:
                # 硬性要求 -> must_reject_table
                risk_row = self._build_risk_row(req)
                must_reject_table.append(risk_row)
            else:
                # 软性要求 -> checklist_table
                checklist_row = self._build_checklist_row(req)
                checklist_table.append(checklist_row)
                
                # ❌ 已删除：自动生成的偏离提醒（冗余信息，用户体验差）
                # 如果招标文件明确有偏离说明，应该在提取时就包含在 requirement_text 中
                # 不应该在前端显示时自动追加
                # if req["allow_deviation"]:
                #     extra_row = self._build_deviation_reminder(req)
                #     if extra_row:
                #         checklist_table.append(extra_row)
        
        # 3. 排序
        must_reject_table = self._sort_risk_table(must_reject_table)
        checklist_table = self._sort_checklist_table(checklist_table)
        
        # 4. 统计
        stats = self._calculate_stats(
            total=len(requirements),
            must_reject=must_reject_table,
            checklist=checklist_table,
        )
        
        return RiskAnalysisResponse(
            must_reject_table=must_reject_table,
            checklist_table=checklist_table,
            stats=stats,
        )
    
    def _get_requirements(self, project_id: str) -> List[Dict[str, Any]]:
        """从数据库读取招标要求"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, requirement_id, dimension, req_type,
                           requirement_text, is_hard, allow_deviation,
                           value_schema_json, evidence_chunk_ids
                    FROM tender_requirements
                    WHERE project_id = %s
                    ORDER BY dimension, requirement_id
                """, (project_id,))
                
                rows = cur.fetchall()
                return [
                    {
                        "id": row['id'],
                        "requirement_id": row['requirement_id'],
                        "dimension": row['dimension'],
                        "req_type": row['req_type'],
                        "requirement_text": row['requirement_text'],
                        "is_hard": row['is_hard'],
                        "allow_deviation": row['allow_deviation'],
                        "value_schema_json": row['value_schema_json'],
                        "evidence_chunk_ids": row.get('evidence_chunk_ids') or [],
                    }
                    for row in rows
                ]
    
    def _infer_consequence(self, requirement_text: str, dimension: str) -> str:
        """
        推断后果类型
        
        Args:
            requirement_text: 要求文本
            dimension: 维度
            
        Returns:
            consequence: reject|hard_requirement|score_loss
        """
        text = requirement_text.lower()
        
        # 1. 明确否决/无效
        if re.search(r'(废标|无效投标|视为无效|否决|不予评审|将被拒绝|拒绝)', requirement_text):
            return "reject"
        
        # 2. 扣分/罚则
        if re.search(r'(扣分|不得分|扣除|扣减|罚|违约金)', requirement_text):
            return "score_loss"
        
        # 3. 默认：硬性要求
        return "hard_requirement"
    
    def _infer_severity(self, consequence: str, dimension: str, req_type: str) -> str:
        """
        推断严重性
        
        Args:
            consequence: 后果类型
            dimension: 维度
            req_type: 要求类型
            
        Returns:
            severity: high|medium|low
        """
        # reject -> high
        if consequence == "reject":
            return "high"
        
        # hard_requirement
        if consequence == "hard_requirement":
            if dimension in ["qualification", "price", "doc_structure"]:
                return "high"
            else:
                return "medium"
        
        # score_loss -> low（但 business 中的罚则可设 medium）
        if consequence == "score_loss":
            if dimension == "business":
                return "medium"
            else:
                return "low"
        
        return "medium"
    
    def _generate_suggestion(self, req_type: str, dimension: str, consequence: str) -> str:
        """
        生成建议
        
        Args:
            req_type: 要求类型
            dimension: 维度
            consequence: 后果类型
            
        Returns:
            suggestion: 建议文本
        """
        if req_type == "must_provide":
            return "准备并按要求签章提交对应材料；缺失可能导致资格/符合性审查不通过。"
        
        elif req_type == "threshold":
            return "确保承诺/参数/报价满足阈值要求；必要时在响应表中明确填写数值。"
        
        elif req_type == "must_not_deviate":
            return '不得偏离，响应中避免"原则上/视情况/按需"等保留表述；必要时出偏离表说明（若允许）。'
        
        elif req_type == "format":
            return "按要求制作份数、装订、签字盖章/电子签章；否则可能被判无效投标。"
        
        elif req_type == "scoring":
            return "这是得分点：按评分档位准备证明材料与描述，避免漏项导致不得分。"
        
        else:
            # 根据 consequence 生成通用建议
            if consequence == "reject":
                return "务必满足此项要求，否则将被视为无效投标。"
            elif consequence == "score_loss":
                return "注意满足此项要求，否则可能扣分或产生违约责任。"
            else:
                return "这是关键硬性要求，不满足可能导致废标或重大风险。"
    
    def _build_risk_row(self, req: Dict[str, Any]) -> RiskRow:
        """构建废标项行"""
        consequence = self._infer_consequence(req["requirement_text"], req["dimension"])
        severity = self._infer_severity(consequence, req["dimension"], req["req_type"])
        suggestion = self._generate_suggestion(req["req_type"], req["dimension"], consequence)
        
        return RiskRow(
            id=req["id"],
            requirement_id=req["requirement_id"],
            dimension=req["dimension"],
            req_type=req["req_type"],
            requirement_text=req["requirement_text"],
            allow_deviation=req["allow_deviation"],
            value_schema_json=req["value_schema_json"],
            evidence_chunk_ids=req["evidence_chunk_ids"],
            consequence=consequence,
            severity=severity,
            suggestion=suggestion,
        )
    
    def _build_checklist_row(self, req: Dict[str, Any]) -> ChecklistRow:
        """构建注意事项行 - 与 RiskRow 保持一致的字段结构"""
        # 软性要求也需要推断consequence
        consequence = self._infer_consequence(req["requirement_text"], req["dimension"])
        
        # 软性要求的 severity 通常较低
        if req["req_type"] == "scoring":
            severity = "low"
        elif consequence == "score_loss":
            severity = "medium"
        else:
            severity = "medium"
        
        # suggestion
        suggestion = self._generate_suggestion(req["req_type"], req["dimension"], consequence)
        
        return ChecklistRow(
            id=req["id"],
            requirement_id=req["requirement_id"],
            dimension=req["dimension"],
            req_type=req["req_type"],
            requirement_text=req["requirement_text"],
            allow_deviation=req["allow_deviation"],
            value_schema_json=req["value_schema_json"],
            evidence_chunk_ids=req["evidence_chunk_ids"],
            consequence=consequence,
            severity=severity,
            suggestion=suggestion,
        )
    
    def _build_deviation_reminder(self, req: Dict[str, Any]) -> ChecklistRow:
        """构建偏离提醒行（已废弃，保留以防需要）"""
        return ChecklistRow(
            id=f"{req['id']}_deviation",
            requirement_id=f"{req['requirement_id']}_deviation",
            dimension=req["dimension"],
            req_type="other",
            requirement_text=f"针对「{req['requirement_text'][:30]}...」，允许正偏离（如工期短于要求），但需提供相应保障措施/资源计划。",
            allow_deviation=True,
            value_schema_json=None,
            evidence_chunk_ids=req["evidence_chunk_ids"],
            consequence="score_loss",
            severity="low",
            suggestion="如计划优于招标要求（正偏离），需在响应中明确说明并提供保障措施。",
        )
    
    def _infer_category(self, req: Dict[str, Any]) -> str:
        """推断类别"""
        req_type = req["req_type"]
        dimension = req["dimension"]
        text = req["requirement_text"].lower()
        
        if req_type == "scoring":
            return "得分点"
        
        if "保证金" in req["requirement_text"]:
            return "保证金说明"
        
        if dimension == "qualification":
            return "资格条件"
        elif dimension == "technical":
            return "技术要求"
        elif dimension == "business":
            return "商务条款"
        elif dimension == "price":
            return "价格要求"
        elif dimension == "doc_structure":
            return "文档格式"
        elif dimension == "schedule_quality":
            return "进度质量"
        else:
            return "其他注意事项"
    
    def _sort_risk_table(self, table: List[RiskRow]) -> List[RiskRow]:
        """排序废标项表"""
        return sorted(table, key=lambda x: (
            DIMENSION_PRIORITY.get(x.dimension, 99),
            REQ_TYPE_PRIORITY.get(x.req_type, 99),
            CONSEQUENCE_PRIORITY.get(x.consequence, 99),
        ))
    
    def _sort_checklist_table(self, table: List[ChecklistRow]) -> List[ChecklistRow]:
        """排序注意事项表"""
        return sorted(table, key=lambda x: (
            SEVERITY_PRIORITY.get(x.severity, 99),
            0 if x.req_type != "scoring" else 1,  # scoring 放最后
        ))
    
    def _calculate_stats(
        self,
        total: int,
        must_reject: List[RiskRow],
        checklist: List[ChecklistRow],
    ) -> RiskAnalysisStats:
        """计算统计信息"""
        high_count = sum(1 for r in must_reject if r.severity == "high")
        medium_count = sum(1 for r in must_reject if r.severity == "medium")
        low_count = sum(1 for r in must_reject if r.severity == "low")
        
        # checklist 也计入 severity 统计
        high_count += sum(1 for r in checklist if r.severity == "high")
        medium_count += sum(1 for r in checklist if r.severity == "medium")
        low_count += sum(1 for r in checklist if r.severity == "low")
        
        return RiskAnalysisStats(
            total_requirements=total,
            must_reject_count=len(must_reject),
            checklist_count=len(checklist),
            high_severity_count=high_count,
            medium_severity_count=medium_count,
            low_severity_count=low_count,
        )

