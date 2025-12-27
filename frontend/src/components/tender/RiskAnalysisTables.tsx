/**
 * 风险分析表格组件（v2）
 * 显示两张表格：废标项表 + 注意事项表
 */
import React, { useState } from 'react';
import {
  RiskAnalysisData,
  RiskRow,
  ChecklistRow,
  DIMENSION_LABELS,
  REQ_TYPE_LABELS,
  CONSEQUENCE_LABELS,
  SEVERITY_LABELS,
} from '../../types/riskAnalysis';

export interface RiskAnalysisTablesProps {
  data: RiskAnalysisData;
  onOpenEvidence: (chunkIds: string[], highlightText?: string) => void;
}

export default function RiskAnalysisTables(props: RiskAnalysisTablesProps): JSX.Element {
  const { data, onOpenEvidence } = props;
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

  // 严重性颜色
  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'high':
        return '#ef4444';
      case 'medium':
        return '#fbbf24';
      case 'low':
        return '#94a3b8';
      default:
        return '#94a3b8';
    }
  };

  // 后果类型颜色
  const getConsequenceColor = (consequence: string) => {
    switch (consequence) {
      case 'reject':
        return '#ef4444';
      case 'hard_requirement':
        return '#f97316';
      case 'score_loss':
        return '#fbbf24';
      default:
        return '#94a3b8';
    }
  };

  // 渲染值约束
  const renderValueSchema = (schema: any) => {
    if (!schema) return '-';
    
    const truncated = JSON.stringify(schema);
    if (truncated.length > 50) {
      return truncated.substring(0, 50) + '...';
    }
    return truncated;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* 统计卡片 */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
          gap: '12px',
        }}
      >
        <StatCard label="总要求数" value={data.stats.total_requirements} color="#60a5fa" />
        <StatCard label="废标项" value={data.stats.must_reject_count} color="#ef4444" />
        <StatCard label="注意事项" value={data.stats.checklist_count} color="#fbbf24" />
        <StatCard label="高严重性" value={data.stats.high_severity_count} color="#ef4444" />
        <StatCard label="中严重性" value={data.stats.medium_severity_count} color="#fbbf24" />
        <StatCard label="低严重性" value={data.stats.low_severity_count} color="#94a3b8" />
      </div>

      {/* 表1：废标项 / 关键硬性要求 */}
      <div>
        <h3
          style={{
            fontSize: '16px',
            fontWeight: 600,
            color: '#e5e7eb',
            marginBottom: '12px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span
            style={{
              width: '4px',
              height: '16px',
              background: '#ef4444',
              borderRadius: '2px',
            }}
          />
          废标项 / 关键硬性要求
          <span style={{ fontSize: '14px', color: '#94a3b8', fontWeight: 400 }}>
            ({data.must_reject_table.length})
          </span>
        </h3>

        {data.must_reject_table.length === 0 ? (
          <div
            className="kb-empty"
            style={{
              padding: '24px',
              textAlign: 'center',
              background: 'rgba(15, 23, 42, 0.6)',
              borderRadius: '8px',
            }}
          >
            暂无废标项
          </div>
        ) : (
          <div
            className="source-card"
            style={{ padding: '0' }}
          >
            <table
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: '13px',
              }}
            >
              <thead
                style={{
                  background: 'rgba(15, 23, 42, 0.8)',
                }}
              >
                <tr>
                  <th style={thStyle}>维度</th>
                  <th style={thStyle}>类型</th>
                  <th style={thStyle}>后果</th>
                  <th style={thStyle}>严重性</th>
                  <th style={thStyle}>招标要求</th>
                  <th style={thStyle}>允许偏离</th>
                  <th style={thStyle}>值约束</th>
                  <th style={thStyle}>建议</th>
                  <th style={thStyle}>证据</th>
                </tr>
              </thead>
              <tbody>
                {data.must_reject_table.map((row) => (
                  <tr
                    key={row.id}
                    style={{
                      borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
                      background: 'rgba(15, 23, 42, 0.4)',
                    }}
                  >
                    <td style={tdStyle}>
                      <span
                        style={{
                          fontSize: '11px',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          background: 'rgba(96, 165, 250, 0.15)',
                          color: '#60a5fa',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {DIMENSION_LABELS[row.dimension] || row.dimension}
                      </span>
                    </td>
                    <td style={tdStyle}>
                      <span style={{ fontSize: '12px', color: '#94a3b8' }}>
                        {REQ_TYPE_LABELS[row.req_type] || row.req_type}
                      </span>
                    </td>
                    <td style={tdStyle}>
                      <span
                        style={{
                          fontSize: '11px',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          border: `1px solid ${getConsequenceColor(row.consequence)}40`,
                          color: getConsequenceColor(row.consequence),
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {CONSEQUENCE_LABELS[row.consequence] || row.consequence}
                      </span>
                    </td>
                    <td style={tdStyle}>
                      <span
                        style={{
                          fontSize: '11px',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          border: `1px solid ${getSeverityColor(row.severity)}40`,
                          color: getSeverityColor(row.severity),
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {SEVERITY_LABELS[row.severity] || row.severity}
                      </span>
                    </td>
                    <td style={{ ...tdStyle, maxWidth: '300px' }}>
                      <div>
                        <div
                          style={{
                            color: '#e5e7eb',
                            lineHeight: '1.4',
                            display: expandedRows.has(row.id) ? 'block' : '-webkit-box',
                            WebkitLineClamp: expandedRows.has(row.id) ? 'unset' : 2,
                            WebkitBoxOrient: 'vertical',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                        >
                          {row.requirement_text}
                        </div>
                        {row.requirement_text.length > 100 && (
                          <button
                            onClick={() => toggleExpand(row.id)}
                            className="link-button"
                            style={{ fontSize: '11px', marginTop: '4px', color: '#60a5fa' }}
                          >
                            {expandedRows.has(row.id) ? '收起' : '展开'}
                          </button>
                        )}
                      </div>
                    </td>
                    <td style={tdStyle}>
                      <span
                        style={{
                          fontSize: '11px',
                          color: row.allow_deviation ? '#10b981' : '#ef4444',
                        }}
                      >
                        {row.allow_deviation ? '允许' : '不允许'}
                      </span>
                    </td>
                    <td style={{ ...tdStyle, maxWidth: '150px', fontSize: '11px', color: '#94a3b8' }}>
                      {renderValueSchema(row.value_schema_json)}
                    </td>
                    <td style={{ ...tdStyle, maxWidth: '200px', fontSize: '12px', color: '#94a3b8' }}>
                      {row.suggestion}
                    </td>
                    <td style={tdStyle}>
                      {row.evidence_chunk_ids.length > 0 && (
                        <button
                          onClick={() => onOpenEvidence(row.evidence_chunk_ids, row.requirement_text)}
                          className="link-button"
                          style={{
                            fontSize: '11px',
                            padding: '3px 6px',
                            border: '1px solid rgba(148, 163, 184, 0.3)',
                            borderRadius: '4px',
                          }}
                        >
                          证据({row.evidence_chunk_ids.length})
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 表2：注意事项 / 得分点 */}
      <div>
        <h3
          style={{
            fontSize: '16px',
            fontWeight: 600,
            color: '#e5e7eb',
            marginBottom: '12px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span
            style={{
              width: '4px',
              height: '16px',
              background: '#fbbf24',
              borderRadius: '2px',
            }}
          />
          注意事项 / 得分点
          <span style={{ fontSize: '14px', color: '#94a3b8', fontWeight: 400 }}>
            ({data.checklist_table.length})
          </span>
        </h3>

        {data.checklist_table.length === 0 ? (
          <div
            className="kb-empty"
            style={{
              padding: '24px',
              textAlign: 'center',
              background: 'rgba(15, 23, 42, 0.6)',
              borderRadius: '8px',
            }}
          >
            暂无注意事项
          </div>
        ) : (
          <div
            className="source-card"
            style={{ padding: '0' }}
          >
            <table
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: '13px',
              }}
            >
              <thead
                style={{
                  background: 'rgba(15, 23, 42, 0.8)',
                }}
              >
                <tr>
                  <th style={thStyle}>类别</th>
                  <th style={thStyle}>严重性</th>
                  <th style={thStyle}>标题/要点</th>
                  <th style={thStyle}>说明</th>
                  <th style={thStyle}>建议</th>
                  <th style={thStyle}>证据</th>
                </tr>
              </thead>
              <tbody>
                {data.checklist_table.map((row) => (
                  <tr
                    key={row.id}
                    style={{
                      borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
                      background: 'rgba(15, 23, 42, 0.4)',
                    }}
                  >
                    <td style={tdStyle}>
                      <span
                        style={{
                          fontSize: '11px',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          background: 'rgba(251, 191, 36, 0.15)',
                          color: '#fbbf24',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {row.category}
                      </span>
                    </td>
                    <td style={tdStyle}>
                      <span
                        style={{
                          fontSize: '11px',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          border: `1px solid ${getSeverityColor(row.severity)}40`,
                          color: getSeverityColor(row.severity),
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {SEVERITY_LABELS[row.severity] || row.severity}
                      </span>
                    </td>
                    <td style={{ ...tdStyle, maxWidth: '200px' }}>
                      <div style={{ color: '#e5e7eb', lineHeight: '1.4', fontWeight: 500 }}>
                        {row.title}
                      </div>
                    </td>
                    <td style={{ ...tdStyle, maxWidth: '300px' }}>
                      <div>
                        <div
                          style={{
                            color: '#94a3b8',
                            fontSize: '12px',
                            lineHeight: '1.4',
                            display: expandedRows.has(row.id) ? 'block' : '-webkit-box',
                            WebkitLineClamp: expandedRows.has(row.id) ? 'unset' : 2,
                            WebkitBoxOrient: 'vertical',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                        >
                          {row.detail}
                        </div>
                        {row.detail.length > 100 && (
                          <button
                            onClick={() => toggleExpand(row.id)}
                            className="link-button"
                            style={{ fontSize: '11px', marginTop: '4px', color: '#60a5fa' }}
                          >
                            {expandedRows.has(row.id) ? '收起' : '展开'}
                          </button>
                        )}
                      </div>
                    </td>
                    <td style={{ ...tdStyle, maxWidth: '200px', fontSize: '12px', color: '#94a3b8' }}>
                      {row.suggestion}
                    </td>
                    <td style={tdStyle}>
                      {row.evidence_chunk_ids.length > 0 && (
                        <button
                          onClick={() => onOpenEvidence(row.evidence_chunk_ids, row.requirement_text)}
                          className="link-button"
                          style={{
                            fontSize: '11px',
                            padding: '3px 6px',
                            border: '1px solid rgba(148, 163, 184, 0.3)',
                            borderRadius: '4px',
                          }}
                        >
                          证据({row.evidence_chunk_ids.length})
                        </button>
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
        padding: '12px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
      }}
    >
      <div style={{ fontSize: '12px', color: '#94a3b8' }}>{label}</div>
      <div style={{ fontSize: '24px', fontWeight: 600, color }}>{value}</div>
    </div>
  );
}

// 表头样式
const thStyle: React.CSSProperties = {
  padding: '10px 12px',
  textAlign: 'left',
  fontSize: '12px',
  fontWeight: 600,
  color: '#94a3b8',
  borderBottom: '1px solid rgba(148, 163, 184, 0.2)',
  whiteSpace: 'nowrap',
};

// 表格单元格样式
const tdStyle: React.CSSProperties = {
  padding: '10px 12px',
  verticalAlign: 'top',
};

