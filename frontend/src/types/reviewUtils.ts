/**
 * Step F: 审核结果工具函数
 * 
 * 提供前端兜底映射，防止后端字段缺失导致 UI 崩溃
 */
import type { ReviewStatus, TenderReviewItem, EvidenceItem } from './tender';

/**
 * 获取审核状态（兜底到 legacy result 字段）
 */
export function getStatus(item: TenderReviewItem): ReviewStatus {
  if (item.status) return item.status;
  
  // Legacy fallback
  if (item.result === "pass") return "PASS";
  if (item.result === "fail") return "FAIL";
  return "WARN";
}

/**
 * 按 role 分组 evidence
 */
export function splitEvidence(item: TenderReviewItem) {
  const ev = Array.isArray(item.evidence_json) ? item.evidence_json : [];
  const tender = ev.filter(e => e.role === "tender");
  const bid = ev.filter(e => e.role === "bid");
  return { tender, bid, all: ev };
}

/**
 * 格式化页码显示
 */
export function formatPageNumber(evidence: EvidenceItem): string {
  if (evidence.page_start != null) {
    if (evidence.page_end != null && evidence.page_end !== evidence.page_start) {
      return `第${evidence.page_start}-${evidence.page_end}页`;
    }
    return `第${evidence.page_start}页`;
  }
  return "无页码";
}

/**
 * 格式化 quote（截断）
 */
export function formatQuote(quote: string | null | undefined, maxLength = 200): string {
  if (!quote) return "-";
  if (quote.length <= maxLength) return quote;
  return quote.slice(0, maxLength) + "...";
}

/**
 * 获取状态标签颜色
 */
export function getStatusColor(status: ReviewStatus): string {
  switch (status) {
    case "PASS": return "success";
    case "WARN": return "warning";
    case "FAIL": return "error";
    case "PENDING": return "default";
    default: return "default";
  }
}

/**
 * 获取状态文本
 */
export function getStatusText(status: ReviewStatus): string {
  switch (status) {
    case "PASS": return "通过";
    case "WARN": return "风险";
    case "FAIL": return "失败";
    case "PENDING": return "待复核";
    default: return status;
  }
}

/**
 * 统计各状态数量
 */
export function countByStatus(items: TenderReviewItem[]) {
  const counts = {
    pass: 0,
    warn: 0,
    fail: 0,
    pending: 0,
    total: items.length,
  };
  
  items.forEach(item => {
    const status = getStatus(item);
    switch (status) {
      case "PASS":
        counts.pass++;
        break;
      case "WARN":
        counts.warn++;
        break;
      case "FAIL":
        counts.fail++;
        break;
      case "PENDING":
        counts.pending++;
        break;
    }
  });
  
  return counts;
}

