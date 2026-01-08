import React, { useMemo, useState } from "react";
import type { TenderReviewItem } from "../../types/tender";
import { getStatus, getStatusText, getStatusColor } from "../../types/reviewUtils";
import EvidenceDrawer from "./EvidenceDrawer";

// 维度中文映射（扩展版）
const DIMENSION_MAP: Record<string, string> = {
  qualification: "资格条件",
  technical: "技术参数",
  commercial: "商务条款",
  business: "商务条款",
  price: "价格报价",
  doc_structure: "文档结构",
  schedule_quality: "工期质量",
  format: "格式要求",
  scoring: "评分标准",
  consistency: "一致性",
  custom_rule: "自定义",
  other: "其他",
};

// 兼容旧版本的 ReviewItem（用于内部类型，实际数据用 TenderReviewItem）
export type ReviewItem = TenderReviewItem & {
  source?: string; // "compare" | "rule" | "v3"
  requirement_text?: string; // 兼容旧字段名
  response_text?: string; // 兼容旧字段名
  rigid?: boolean; // 兼容旧字段名
  rule_id?: string; // 规则ID（仅规则审核）
};

export default function ReviewTable({
  items,
  onOpenEvidence,
}: {
  items: ReviewItem[];
  onOpenEvidence: (chunkIds: string[]) => void;
}) {
  const [resultFilter, setResultFilter] = useState<"all" | "pass" | "risk" | "fail" | "pending">("all");
  const [kw, setKw] = useState("");
  
  // Step F-Frontend-4: Drawer state
  const [selectedItem, setSelectedItem] = useState<ReviewItem | null>(null);

  const filtered = useMemo(() => {
    const k = kw.trim().toLowerCase();
    return (items || []).filter((it) => {
      // 结果筛选（支持新 status 和旧 result）
      if (resultFilter !== "all") {
        const status = getStatus(it).toLowerCase();
        const legacyResult = it.result || "risk";
        
        // 映射：pending → pending, pass → pass, fail → fail, warn/risk → risk
        if (resultFilter === "pending" && status !== "pending") return false;
        if (resultFilter === "pass" && status !== "pass") return false;
        if (resultFilter === "fail" && status !== "fail") return false;
        if (resultFilter === "risk" && status !== "warn" && legacyResult !== "risk") return false;
      }
      
      // 关键词筛选
      if (!k) return true;
      const reqText = it.requirement_text || it.tender_requirement || "";
      const respText = it.response_text || it.bid_response || "";
      return (
        (it.dimension || "").toLowerCase().includes(k) ||
        reqText.toLowerCase().includes(k) ||
        respText.toLowerCase().includes(k) ||
        (it.remark || "").toLowerCase().includes(k) ||
        (it.rule_id || "").toLowerCase().includes(k) ||
        (it.evaluator || "").toLowerCase().includes(k)
      );
    });
  }, [items, resultFilter, kw]);

  const badge = (item: ReviewItem) => {
    const status = getStatus(item);
    const color = getStatusColor(status);
    const text = getStatusText(status);
    
    // 映射到 tender-badge 类名
    let badgeClass = "tender-badge ";
    if (status === "PASS") badgeClass += "pass";
    else if (status === "FAIL") badgeClass += "fail";
    else if (status === "WARN") badgeClass += "risk";
    else badgeClass += "pending"; // PENDING 用新样式
    
    return <span className={badgeClass}>{text}</span>;
  };

  return (
    <div className="source-card">
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ fontWeight: 600 }}>审核一览（V3流水线）</div>

        <select className="sidebar-select" style={{ minWidth: 140 }} value={resultFilter} onChange={(e) => setResultFilter(e.target.value as any)}>
          <option value="all">全部结果</option>
          <option value="pending">待复核</option>
          <option value="fail">不合格</option>
          <option value="risk">风险</option>
          <option value="pass">通过</option>
        </select>

        <input
          placeholder="搜索维度/要求/响应/备注"
          value={kw}
          onChange={(e) => setKw(e.target.value)}
          style={{ flex: 1, minWidth: 220 }}
        />
        <div className="kb-doc-meta">共 {filtered.length} 条</div>
      </div>

      <div className="tender-table-wrap" style={{ marginTop: 12 }}>
        <table className="tender-table">
          <thead>
            <tr>
              <th style={{ width: 110 }}>维度</th>
              <th style={{ width: 90 }}>状态</th>
              <th style={{ width: 70 }}>硬性</th>
              <th>招标要求</th>
              <th>投标响应</th>
              <th style={{ width: 220 }}>证据</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((it) => {
              const reqText = it.requirement_text || it.tender_requirement || "-";
              const respText = it.response_text || it.bid_response || "-";
              const isHard = it.rigid !== undefined ? it.rigid : (it.is_hard || false);
              
              return (
                <tr key={it.id}>
                  <td>{DIMENSION_MAP[it.dimension || ""] || it.dimension || "其他"}</td>
                  <td>{badge(it)}</td>
                  <td>{isHard ? <span className="tender-badge required">硬性</span> : "-"}</td>
                  <td className="tender-cell">{reqText}</td>
                  <td className="tender-cell">{respText}</td>
                  <td>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      {/* Step F-Frontend-4: 查看证据按钮 */}
                      <button 
                        className="link-button" 
                        onClick={() => setSelectedItem(it)}
                        style={{ fontWeight: 500 }}
                      >
                        🔍 查看证据
                      </button>
                      
                      {/* 兼容旧版：chunk_ids 查看 */}
                      {it.tender_evidence_chunk_ids?.length > 0 && (
                        <button className="link-button" onClick={() => onOpenEvidence(it.tender_evidence_chunk_ids)}>
                          招标({it.tender_evidence_chunk_ids.length})
                        </button>
                      )}
                      {it.bid_evidence_chunk_ids?.length > 0 && (
                        <button className="link-button" onClick={() => onOpenEvidence(it.bid_evidence_chunk_ids)}>
                          投标({it.bid_evidence_chunk_ids.length})
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="kb-empty" style={{ textAlign: "center", padding: 20 }}>
                  暂无数据
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      
      {/* Step F-Frontend-4: Evidence Drawer */}
      <EvidenceDrawer 
        item={selectedItem}
        isOpen={!!selectedItem}
        onClose={() => setSelectedItem(null)}
      />
    </div>
  );
}
