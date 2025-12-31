"""
Step 7: 报告导出增强 - 使用 evidence_json

为审核报告导出增加证据定位功能
"""
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class ReviewReportEnhancer:
    """审核报告增强器 - 添加证据引用"""
    
    def __init__(self, pool: Any):
        self.pool = pool
    
    def enhance_review_items_for_export(
        self,
        project_id: str,
        bidder_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        增强审核项以用于导出
        
        添加格式化的证据引用字符串：
        - "第X页：引用片段..."
        - "见第X-Y页"
        
        Returns:
            增强后的审核项列表，每项包含 evidence_summary 字段
        """
        # 1. 加载审核项
        review_items = self._load_review_items(project_id, bidder_name)
        logger.info(f"ReportEnhancer: Loaded {len(review_items)} review items")
        
        # 2. 增强每个审核项
        enhanced_items = []
        for item in review_items:
            enhanced = self._enhance_item(item)
            enhanced_items.append(enhanced)
        
        # 3. 分组：PENDING 项单独汇总
        pending_items = [it for it in enhanced_items if it.get("status") == "PENDING"]
        
        logger.info(f"ReportEnhancer: {len(pending_items)} PENDING items need manual review")
        
        return {
            "all_items": enhanced_items,
            "pending_items": pending_items,
            "stats": self._calculate_stats(enhanced_items)
        }
    
    def _load_review_items(self, project_id: str, bidder_name: Optional[str]) -> List[Dict]:
        """加载审核项"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                if bidder_name:
                    cur.execute("""
                        SELECT id, requirement_id, dimension, clause_title,
                               tender_requirement, bid_response, result, status,
                               is_hard, remark, evaluator,
                               rule_trace_json, computed_trace_json, evidence_json
                        FROM tender_review_items
                        WHERE project_id = %s AND bidder_name = %s
                        ORDER BY dimension, requirement_id
                    """, (project_id, bidder_name))
                else:
                    cur.execute("""
                        SELECT id, requirement_id, dimension, clause_title,
                               tender_requirement, bid_response, result, status,
                               is_hard, remark, evaluator, bidder_name,
                               rule_trace_json, computed_trace_json, evidence_json
                        FROM tender_review_items
                        WHERE project_id = %s
                        ORDER BY bidder_name, dimension, requirement_id
                    """, (project_id,))
                
                rows = cur.fetchall()
                return [dict(row) for row in rows]
    
    def _enhance_item(self, item: Dict) -> Dict:
        """增强单个审核项"""
        evidence_json = item.get("evidence_json", [])
        
        # 格式化证据引用
        evidence_summary = self._format_evidence(evidence_json)
        
        # 添加增强字段
        item["evidence_summary"] = evidence_summary
        item["has_evidence"] = bool(evidence_json)
        
        # 如果是 PENDING，添加提示
        if item.get("status") == "PENDING":
            item["review_note"] = "【需人工复核】" + (item.get("remark") or "")
        
        return item
    
    def _format_evidence(self, evidence_json: Any) -> str:
        """
        格式化证据为可读字符串
        
        格式：第X页：引用片段（限100字）
        """
        if not evidence_json or not isinstance(evidence_json, list):
            return "（无证据定位）"
        
        evidence_lines = []
        for idx, ev in enumerate(evidence_json[:3]):  # 最多显示3条
            if not isinstance(ev, dict):
                continue
            
            page_start = ev.get("page_start")
            page_end = ev.get("page_end")
            quote = ev.get("quote", "")
            segment_id = ev.get("segment_id", "")
            chunk_id = ev.get("chunk_id", "")
            
            # 构建引用字符串
            parts = []
            
            # 页码部分
            if page_start:
                if page_end and page_end != page_start:
                    parts.append(f"第{page_start}-{page_end}页")
                else:
                    parts.append(f"第{page_start}页")
            
            # 引用内容（截断到100字）
            if quote:
                quote_short = quote[:100] + "..." if len(quote) > 100 else quote
                quote_short = quote_short.replace("\n", " ")
                parts.append(f'"{quote_short}"')
            elif segment_id or chunk_id:
                parts.append(f"[{segment_id or chunk_id}]")
            
            if parts:
                evidence_lines.append("、".join(parts))
        
        if not evidence_lines:
            return "（无证据定位）"
        
        # 如果有多条，用换行分隔
        if len(evidence_lines) > 1:
            return "\n".join(f"{i+1}. {line}" for i, line in enumerate(evidence_lines))
        else:
            return evidence_lines[0]
    
    def _calculate_stats(self, items: List[Dict]) -> Dict:
        """计算统计"""
        total = len(items)
        status_counts = {}
        
        for item in items:
            status = item.get("status", "UNKNOWN")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "total": total,
            "pass": status_counts.get("PASS", 0),
            "fail": status_counts.get("FAIL", 0),
            "warn": status_counts.get("WARN", 0),
            "pending": status_counts.get("PENDING", 0),
        }
    
    def generate_pending_summary(self, pending_items: List[Dict]) -> str:
        """
        生成人工复核清单（文本格式）
        
        用于报告末尾附录
        """
        if not pending_items:
            return "无需人工复核的项目。"
        
        lines = [
            "=" * 60,
            f"人工复核清单（共 {len(pending_items)} 项）",
            "=" * 60,
            ""
        ]
        
        for idx, item in enumerate(pending_items, 1):
            lines.append(f"{idx}. 【{item.get('dimension', 'unknown')}】{item.get('clause_title', '未命名')}")
            lines.append(f"   要求：{item.get('tender_requirement', '')[:80]}...")
            lines.append(f"   响应：{item.get('bid_response', '')[:80]}...")
            lines.append(f"   原因：{item.get('remark', '未提供')}")
            lines.append(f"   证据：{item.get('evidence_summary', '无')}")
            lines.append("")
        
        return "\n".join(lines)


# 便捷函数
def get_enhanced_review_report(pool: Any, project_id: str, bidder_name: Optional[str] = None) -> Dict:
    """
    获取增强后的审核报告数据
    
    Usage:
        report_data = get_enhanced_review_report(pool, project_id, bidder_name)
        
        # 在导出模块中使用
        for item in report_data["all_items"]:
            print(f"{item['clause_title']}: {item['evidence_summary']}")
        
        # 添加人工复核清单
        pending_summary = report_data["pending_summary"]
    """
    enhancer = ReviewReportEnhancer(pool)
    result = enhancer.enhance_review_items_for_export(project_id, bidder_name)
    
    # 生成人工复核清单文本
    pending_summary = enhancer.generate_pending_summary(result["pending_items"])
    
    return {
        "all_items": result["all_items"],
        "pending_items": result["pending_items"],
        "pending_summary": pending_summary,
        "stats": result["stats"]
    }

