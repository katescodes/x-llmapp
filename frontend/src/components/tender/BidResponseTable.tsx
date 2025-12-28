import React, { useMemo, useState } from "react";

export type BidResponse = {
  id: string;
  bidder_name: string;
  dimension: string;
  response_type: string;
  response_text: string;
  extracted_value_json?: any;
  evidence_chunk_ids: string[];
  created_at?: string;
};

export type BidResponseStats = {
  bidder_name: string;
  dimension: string;
  count: number;
};

export default function BidResponseTable({
  responses,
  stats,
  onOpenEvidence,
}: {
  responses: BidResponse[];
  stats: BidResponseStats[];
  onOpenEvidence: (chunkIds: string[]) => void;
}) {
  const [dimensionFilter, setDimensionFilter] = useState<string>("all");
  const [kw, setKw] = useState("");

  // 获取所有唯一的维度
  const dimensions = useMemo(() => {
    const dims = new Set<string>();
    responses.forEach((r) => dims.add(r.dimension || "其他"));
    return Array.from(dims).sort();
  }, [responses]);

  const filtered = useMemo(() => {
    const k = kw.trim().toLowerCase();
    return (responses || []).filter((it) => {
      // 维度筛选
      if (dimensionFilter !== "all" && it.dimension !== dimensionFilter) return false;
      // 关键词筛选
      if (!k) return true;
      return (
        (it.dimension || "").toLowerCase().includes(k) ||
        (it.response_type || "").toLowerCase().includes(k) ||
        (it.response_text || "").toLowerCase().includes(k) ||
        (it.bidder_name || "").toLowerCase().includes(k)
      );
    });
  }, [responses, dimensionFilter, kw]);

  const typeBadge = (type: string) => {
    const typeMap: Record<string, { bg: string; text: string }> = {
      text: { bg: "#3b82f6", text: "文本" },
      document_ref: { bg: "#8b5cf6", text: "文档引用" },
      structured: { bg: "#10b981", text: "结构化" },
      number: { bg: "#f59e0b", text: "数值" },
    };
    const info = typeMap[type] || { bg: "#64748b", text: type };
    return (
      <span
        className="tender-badge"
        style={{ background: info.bg, color: "white", fontSize: "11px" }}
      >
        {info.text}
      </span>
    );
  };

  return (
    <div className="source-card">
      {/* 统计信息 */}
      {stats.length > 0 && (
        <div
          className="kb-doc-meta"
          style={{
            marginBottom: "16px",
            padding: "12px",
            backgroundColor: "#f0fdf4",
            borderRadius: "4px",
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: "8px", color: "#166534" }}>
            📊 抽取统计
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "12px" }}>
            {stats.map((stat, idx) => (
              <div
                key={idx}
                style={{
                  fontSize: "13px",
                  color: "#15803d",
                  padding: "4px 8px",
                  backgroundColor: "white",
                  borderRadius: "4px",
                  border: "1px solid #bbf7d0",
                }}
              >
                {stat.dimension}: <strong>{stat.count}</strong> 条
              </div>
            ))}
          </div>
          <div
            style={{
              marginTop: "8px",
              paddingTop: "8px",
              borderTop: "1px solid #bbf7d0",
              fontWeight: 600,
              color: "#166534",
            }}
          >
            总计: {stats.reduce((sum, s) => sum + s.count, 0)} 条投标响应数据
          </div>
        </div>
      )}

      {/* 筛选和搜索 */}
      <div
        style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}
      >
        <div style={{ fontWeight: 600 }}>投标响应详情</div>

        <select
          className="sidebar-select"
          style={{ minWidth: 140 }}
          value={dimensionFilter}
          onChange={(e) => setDimensionFilter(e.target.value)}
        >
          <option value="all">全部维度</option>
          {dimensions.map((dim) => (
            <option key={dim} value={dim}>
              {dim}
            </option>
          ))}
        </select>

        <input
          placeholder="搜索维度/类型/内容/投标人"
          value={kw}
          onChange={(e) => setKw(e.target.value)}
          style={{ flex: 1, minWidth: 220 }}
        />
        <div className="kb-doc-meta">共 {filtered.length} 条</div>
      </div>

      {/* 表格 */}
      <div className="tender-table-wrap" style={{ marginTop: 12 }}>
        <table className="tender-table">
          <thead>
            <tr>
              <th style={{ width: 50 }}>#</th>
              <th style={{ width: 120 }}>投标人</th>
              <th style={{ width: 110 }}>维度</th>
              <th style={{ width: 90 }}>类型</th>
              <th>响应内容</th>
              <th style={{ width: 120 }}>证据</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((it, idx) => {
              return (
                <tr key={it.id}>
                  <td style={{ textAlign: "center", color: "#64748b" }}>{idx + 1}</td>
                  <td>
                    <div
                      style={{
                        fontSize: "13px",
                        color: "#334155",
                        fontWeight: 500,
                      }}
                    >
                      {it.bidder_name || "-"}
                    </div>
                  </td>
                  <td>
                    <span
                      className="tender-badge"
                      style={{
                        background: "#e0f2fe",
                        color: "#0369a1",
                        fontSize: "12px",
                      }}
                    >
                      {it.dimension || "其他"}
                    </span>
                  </td>
                  <td>{typeBadge(it.response_type || "text")}</td>
                  <td className="tender-cell">
                    <div
                      style={{
                        maxHeight: "100px",
                        overflowY: "auto",
                        whiteSpace: "pre-wrap",
                        fontSize: "13px",
                        lineHeight: "1.5",
                      }}
                    >
                      {it.response_text || "-"}
                    </div>
                  </td>
                  <td>
                    {it.evidence_chunk_ids?.length > 0 ? (
                      <button
                        className="link-button"
                        onClick={() => onOpenEvidence(it.evidence_chunk_ids)}
                        style={{ fontSize: "12px" }}
                      >
                        查看证据 ({it.evidence_chunk_ids.length})
                      </button>
                    ) : (
                      <span style={{ color: "#94a3b8", fontSize: "12px" }}>无</span>
                    )}
                  </td>
                </tr>
              );
            })}
            {filtered.length === 0 && (
              <tr>
                <td
                  colSpan={6}
                  className="kb-empty"
                  style={{ textAlign: "center", padding: 20 }}
                >
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

