import React, { useMemo, useState } from "react";

export type ReviewItem = {
  id: string;
  source?: string; // "compare" | "rule"
  dimension: string;
  requirement_text?: string;
  response_text?: string;
  result: "pass" | "risk" | "fail";
  remark?: string;
  rigid: boolean;
  rule_id?: string; // 规则ID（仅规则审核）
  tender_evidence_chunk_ids: string[];
  bid_evidence_chunk_ids: string[];
};

export default function ReviewTable({
  items,
  onOpenEvidence,
}: {
  items: ReviewItem[];
  onOpenEvidence: (chunkIds: string[]) => void;
}) {
  const [resultFilter, setResultFilter] = useState<"all" | "pass" | "risk" | "fail">("all");
  const [sourceFilter, setSourceFilter] = useState<"all" | "compare" | "rule">("all");
  const [kw, setKw] = useState("");

  const filtered = useMemo(() => {
    const k = kw.trim().toLowerCase();
    return (items || []).filter((it) => {
      // 结果筛选
      if (resultFilter !== "all" && it.result !== resultFilter) return false;
      // 来源筛选
      if (sourceFilter !== "all") {
        const itemSource = it.source || "compare";
        if (itemSource !== sourceFilter) return false;
      }
      // 关键词筛选
      if (!k) return true;
      return (
        (it.dimension || "").toLowerCase().includes(k) ||
        (it.requirement_text || "").toLowerCase().includes(k) ||
        (it.response_text || "").toLowerCase().includes(k) ||
        (it.remark || "").toLowerCase().includes(k) ||
        (it.rule_id || "").toLowerCase().includes(k)
      );
    });
  }, [items, resultFilter, sourceFilter, kw]);

  const badge = (r: ReviewItem["result"]) => {
    if (r === "pass") return <span className="tender-badge pass">通过</span>;
    if (r === "risk") return <span className="tender-badge risk">风险</span>;
    return <span className="tender-badge fail">不合格</span>;
  };

  return (
    <div className="source-card">
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ fontWeight: 600 }}>审核一览</div>

        <select className="sidebar-select" style={{ minWidth: 140 }} value={resultFilter} onChange={(e) => setResultFilter(e.target.value as any)}>
          <option value="all">全部结果</option>
          <option value="fail">不合格</option>
          <option value="risk">风险</option>
          <option value="pass">通过</option>
        </select>

        <select className="sidebar-select" style={{ minWidth: 140 }} value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value as any)}>
          <option value="all">全部来源</option>
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
              <th style={{ width: 110 }}>结果</th>
              <th style={{ width: 70 }}>硬性</th>
              <th>招标要求</th>
              <th>投标响应</th>
              <th style={{ width: 220 }}>证据</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((it) => {
              const itemSource = it.source || "compare";
              return (
                <tr key={it.id}>
                  <td>
                    {itemSource === "rule" ? (
                      <span className="tender-badge" style={{ background: "#8b5cf6", color: "white", fontSize: "11px" }}>
                        规则
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
                  <td>{badge(it.result)}</td>
                  <td>{it.rigid ? <span className="tender-badge required">硬性</span> : "-"}</td>
                  <td className="tender-cell">{it.requirement_text || "-"}</td>
                  <td className="tender-cell">{it.response_text || "-"}</td>
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
                <td colSpan={7} className="kb-empty" style={{ textAlign: "center", padding: 20 }}>
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
