import React, { useMemo, useState } from "react";
import type { TenderReviewItem } from "../../types/tender";
import { getStatus, getStatusText, getStatusColor } from "../../types/reviewUtils";

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
  const [sourceFilter, setSourceFilter] = useState<"all" | "compare" | "rule" | "v3">("all");
  const [kw, setKw] = useState("");

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
      
      // 来源筛选
      if (sourceFilter !== "all") {
        const itemSource = it.source || "v3"; // 默认为 v3
        if (itemSource !== sourceFilter) return false;
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
  }, [items, resultFilter, sourceFilter, kw]);

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
        <div style={{ fontWeight: 600 }}>审核一览</div>

        <select className="sidebar-select" style={{ minWidth: 140 }} value={resultFilter} onChange={(e) => setResultFilter(e.target.value as any)}>
          <option value="all">全部结果</option>
          <option value="pending">待复核</option>
          <option value="fail">不合格</option>
          <option value="risk">风险</option>
          <option value="pass">通过</option>
        </select>

        <select className="sidebar-select" style={{ minWidth: 140 }} value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value as any)}>
          <option value="all">全部来源</option>
          <option value="v3">V3流水线</option>
          <option value="compare">对比审核</option>
          <option value="rule">规则审核</option>
        </select>

        <input
          placeholder="搜索维度/要求/响应/备注/规则ID"
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
              <th style={{ width: 90 }}>来源</th>
              <th style={{ width: 110 }}>维度</th>
              <th style={{ width: 90 }}>状态</th>
              <th style={{ width: 110 }}>评估器</th>
              <th style={{ width: 70 }}>硬性</th>
              <th>招标要求</th>
              <th>投标响应</th>
              <th style={{ width: 220 }}>证据</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((it) => {
              const itemSource = it.source || "v3";
              const reqText = it.requirement_text || it.tender_requirement || "-";
              const respText = it.response_text || it.bid_response || "-";
              const isHard = it.rigid !== undefined ? it.rigid : (it.is_hard || false);
              
              return (
                <tr key={it.id}>
                  <td>
                    {itemSource === "rule" ? (
                      <span className="tender-badge" style={{ background: "#8b5cf6", color: "white", fontSize: "11px" }}>
                        规则
                      </span>
                    ) : itemSource === "v3" ? (
                      <span className="tender-badge" style={{ background: "#10b981", color: "white", fontSize: "11px" }}>
                        V3
                      </span>
                    ) : (
                      <span className="tender-badge" style={{ background: "#6366f1", color: "white", fontSize: "11px" }}>
                        对比
                      </span>
                    )}
                    {it.rule_id && (
                      <div style={{ fontSize: "10px", color: "#64748b", marginTop: "2px" }}>
                        {it.rule_id.substring(0, 10)}
                      </div>
                    )}
                  </td>
                  <td>{it.dimension || "其他"}</td>
                  <td>{badge(it)}</td>
                  <td>
                    <span style={{ fontSize: "12px", color: "#64748b" }}>
                      {it.evaluator || "-"}
                    </span>
                  </td>
                  <td>{isHard ? <span className="tender-badge required">硬性</span> : "-"}</td>
                  <td className="tender-cell">{reqText}</td>
                  <td className="tender-cell">{respText}</td>
                  <td>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      {it.tender_evidence_chunk_ids?.length > 0 && (
                        <button className="link-button" onClick={() => onOpenEvidence(it.tender_evidence_chunk_ids)}>
                          招标证据({it.tender_evidence_chunk_ids.length})
                        </button>
                      )}
                      {it.bid_evidence_chunk_ids?.length > 0 && (
                        <button className="link-button" onClick={() => onOpenEvidence(it.bid_evidence_chunk_ids)}>
                          投标证据({it.bid_evidence_chunk_ids.length})
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={8} className="kb-empty" style={{ textAlign: "center", padding: 20 }}>
                  暂无数据
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
