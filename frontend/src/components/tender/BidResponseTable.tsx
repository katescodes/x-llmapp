/**
 * 投标响应表格组件
 * 样式与 RiskAnalysisTables 保持一致
 */
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

// 维度标签映射
const DIMENSION_LABELS: Record<string, string> = {
  qualification: "资格",
  commercial: "商务",
  technical: "技术",
  other: "其他",
};

// 响应类型标签映射
const RESPONSE_TYPE_LABELS: Record<string, string> = {
  text: "文本",
  document_ref: "文档引用",
  structured: "结构化",
  number: "数值",
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
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const toggleExpand = (id: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

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

  // 响应类型颜色映射
  const getResponseTypeColor = (type: string) => {
    switch (type) {
      case "structured":
        return "#10b981";
      case "number":
        return "#f59e0b";
      case "document_ref":
        return "#8b5cf6";
      case "text":
      default:
        return "#60a5fa";
    }
  };

  // 计算总统计
  const totalCount = stats.reduce((sum, s) => sum + s.count, 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {/* 统计卡片 */}
      {stats.length > 0 && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
            gap: "12px",
          }}
        >
          <StatCard label="总响应数" value={totalCount} color="#60a5fa" />
          {stats.slice(0, 5).map((stat, idx) => (
            <StatCard
              key={idx}
              label={DIMENSION_LABELS[stat.dimension] || stat.dimension}
              value={stat.count}
              color={
                stat.dimension === "qualification"
                  ? "#ef4444"
                  : stat.dimension === "commercial"
                  ? "#fbbf24"
                  : "#10b981"
              }
            />
          ))}
        </div>
      )}

      {/* 表格 */}
      <div>
        <h3
          style={{
            fontSize: "16px",
            fontWeight: 600,
            color: "#e5e7eb",
            marginBottom: "12px",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <span
            style={{
              width: "4px",
              height: "16px",
              background: "#60a5fa",
              borderRadius: "2px",
            }}
          />
          投标响应详情
          <span style={{ fontSize: "14px", color: "#94a3b8", fontWeight: 400 }}>
            ({filtered.length})
          </span>
        </h3>

        {/* 筛选和搜索 */}
        <div
          style={{
            display: "flex",
            gap: "12px",
            alignItems: "center",
            flexWrap: "wrap",
            marginBottom: "12px",
          }}
        >
          <select
            className="sidebar-select"
            style={{
              minWidth: 140,
              padding: "6px 10px",
              background: "rgba(15, 23, 42, 0.6)",
              border: "1px solid rgba(148, 163, 184, 0.3)",
              borderRadius: "6px",
              color: "#e5e7eb",
              fontSize: "13px",
            }}
            value={dimensionFilter}
            onChange={(e) => setDimensionFilter(e.target.value)}
          >
            <option value="all">全部维度</option>
            {dimensions.map((dim) => (
              <option key={dim} value={dim}>
                {DIMENSION_LABELS[dim] || dim}
              </option>
            ))}
          </select>

          <input
            placeholder="搜索维度/类型/内容/投标人"
            value={kw}
            onChange={(e) => setKw(e.target.value)}
            style={{
              flex: 1,
              minWidth: 220,
              padding: "6px 12px",
              background: "rgba(15, 23, 42, 0.6)",
              border: "1px solid rgba(148, 163, 184, 0.3)",
              borderRadius: "6px",
              color: "#e5e7eb",
              fontSize: "13px",
            }}
          />
        </div>

        {filtered.length === 0 ? (
          <div
            className="kb-empty"
            style={{
              padding: "24px",
              textAlign: "center",
              background: "rgba(15, 23, 42, 0.6)",
              borderRadius: "8px",
            }}
          >
            暂无投标响应数据
          </div>
        ) : (
          <div className="source-card" style={{ padding: "0" }}>
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: "13px",
              }}
            >
              <thead
                style={{
                  background: "rgba(15, 23, 42, 0.8)",
                }}
              >
                <tr>
                  <th style={thStyle}>投标人</th>
                  <th style={thStyle}>维度</th>
                  <th style={thStyle}>类型</th>
                  <th style={thStyle}>响应内容</th>
                  <th style={thStyle}>证据</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((it) => (
                  <tr
                    key={it.id}
                    style={{
                      borderBottom: "1px solid rgba(148, 163, 184, 0.1)",
                      background: "rgba(15, 23, 42, 0.4)",
                    }}
                  >
                    <td style={tdStyle}>
                      <div
                        style={{
                          fontSize: "13px",
                          color: "#e5e7eb",
                          fontWeight: 500,
                        }}
                      >
                        {it.bidder_name || "-"}
                      </div>
                    </td>
                    <td style={tdStyle}>
                      <span
                        style={{
                          fontSize: "11px",
                          padding: "2px 6px",
                          borderRadius: "4px",
                          background: "rgba(96, 165, 250, 0.15)",
                          color: "#60a5fa",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {DIMENSION_LABELS[it.dimension] || it.dimension || "其他"}
                      </span>
                    </td>
                    <td style={tdStyle}>
                      <span
                        style={{
                          fontSize: "11px",
                          padding: "2px 6px",
                          borderRadius: "4px",
                          border: `1px solid ${getResponseTypeColor(it.response_type || "text")}40`,
                          color: getResponseTypeColor(it.response_type || "text"),
                          whiteSpace: "nowrap",
                        }}
                      >
                        {RESPONSE_TYPE_LABELS[it.response_type] || it.response_type || "文本"}
                      </span>
                    </td>
                    <td style={{ ...tdStyle, maxWidth: "400px" }}>
                      <div>
                        <div
                          style={{
                            color: "#e5e7eb",
                            lineHeight: "1.4",
                            display: expandedRows.has(it.id) ? "block" : "-webkit-box",
                            WebkitLineClamp: expandedRows.has(it.id) ? "unset" : 3,
                            WebkitBoxOrient: "vertical",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "pre-wrap",
                          }}
                        >
                          {it.response_text || "-"}
                        </div>
                        {it.response_text && it.response_text.length > 150 && (
                          <button
                            onClick={() => toggleExpand(it.id)}
                            className="link-button"
                            style={{ fontSize: "11px", marginTop: "4px", color: "#60a5fa" }}
                          >
                            {expandedRows.has(it.id) ? "收起" : "展开"}
                          </button>
                        )}
                      </div>
                    </td>
                    <td style={tdStyle}>
                      {it.evidence_chunk_ids?.length > 0 ? (
                        <button
                          onClick={() => onOpenEvidence(it.evidence_chunk_ids)}
                          className="link-button"
                          style={{
                            fontSize: "11px",
                            padding: "3px 6px",
                            border: "1px solid rgba(148, 163, 184, 0.3)",
                            borderRadius: "4px",
                          }}
                        >
                          证据({it.evidence_chunk_ids.length})
                        </button>
                      ) : (
                        <span style={{ color: "#94a3b8", fontSize: "11px" }}>-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// 统计卡片子组件
function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div
      className="source-card"
      style={{
        padding: "12px 16px",
        display: "flex",
        flexDirection: "column",
        gap: "4px",
      }}
    >
      <div style={{ fontSize: "12px", color: "#94a3b8" }}>{label}</div>
      <div style={{ fontSize: "24px", fontWeight: 600, color }}>{value}</div>
    </div>
  );
}

// 表头样式
const thStyle: React.CSSProperties = {
  padding: "10px 12px",
  textAlign: "left",
  fontSize: "12px",
  fontWeight: 600,
  color: "#94a3b8",
  borderBottom: "1px solid rgba(148, 163, 184, 0.2)",
  whiteSpace: "nowrap",
};

// 表格单元格样式
const tdStyle: React.CSSProperties = {
  padding: "10px 12px",
  verticalAlign: "top",
};

