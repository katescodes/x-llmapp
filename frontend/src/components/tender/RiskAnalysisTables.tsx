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
  const [consequenceFilter, setConsequenceFilter] = useState<string>('all');

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

  // 维度颜色
  const getDimensionColor = (dimension: string) => {
    switch (dimension) {
      case 'qualification':
        return '#ef4444';
      case 'price':
        return '#f59e0b';
      case 'technical':
        return '#3b82f6';
      case 'business':
      case 'commercial':
        return '#8b5cf6';
      case 'doc_structure':
      case 'format':
        return '#06b6d4';
      case 'bid_security':
        return '#ec4899';
      case 'schedule_quality':
        return '#10b981';
      case 'scoring':
        return '#fbbf24';
      default:
        return '#94a3b8';
    }
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
      case '废标/无效':
      case 'reject':
        return '#ef4444';
      case '关键要求':
      case 'hard_requirement':
        return '#f97316';
      case '扣分':
      case 'score_loss':
        return '#fbbf24';
      case '加分':
        return '#10b981';
      default:
        return '#94a3b8';
    }
  };

  // 合并两个表的数据
  const allRows = [...data.must_reject_table, ...data.checklist_table];
  
  // 根据consequence筛选
  const filteredRows = consequenceFilter === 'all' 
    ? allRows 
    : allRows.filter(row => row.consequence === consequenceFilter);
  
  // 获取实际存在的consequence类型（用于下拉框选项）
  const availableConsequences = Array.from(new Set(allRows.map(row => row.consequence).filter(Boolean)));

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
        <StatCard label="废标/无效" value={data.stats.veto_count || 0} color="#ef4444" />
        <StatCard label="关键要求" value={data.stats.critical_count || 0} color="#f97316" />
        <StatCard label="扣分" value={data.stats.deduct_count || 0} color="#fbbf24" />
        <StatCard label="加分" value={data.stats.bonus_count || 0} color="#10b981" />
      </div>

      {/* 招标要求列表（合并表格） */}
      <div>
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between',
          marginBottom: '12px',
        }}>
        <h3
          style={{
            fontSize: '16px',
            fontWeight: 600,
            color: '#e5e7eb',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span
            style={{
              width: '4px',
              height: '16px',
                background: '#60a5fa',
              borderRadius: '2px',
            }}
          />
            招标要求列表
          <span style={{ fontSize: '14px', color: '#94a3b8', fontWeight: 400 }}>
              (共{allRows.length}条，显示{filteredRows.length}条)
          </span>
        </h3>

          {/* 类别筛选 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <label style={{ fontSize: '14px', color: '#94a3b8' }}>类别：</label>
            <select
              value={consequenceFilter}
              onChange={(e) => setConsequenceFilter(e.target.value)}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: '1px solid #374151',
                background: '#1f2937',
                color: '#e5e7eb',
                fontSize: '14px',
                cursor: 'pointer',
              }}
            >
              <option value="all">全部</option>
              {availableConsequences.map(consequence => (
                <option key={consequence} value={consequence}>{consequence}</option>
              ))}
            </select>
          </div>
        </div>

        {filteredRows.length === 0 ? (
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
                  <th style={thStyle}>类别</th>
                  <th style={thStyle}>严重性</th>
                  <th style={thStyle}>招标要求</th>
                  <th style={{...thStyle, minWidth: '300px'}}>原文证据</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((row) => (
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
                    <td style={{ ...tdStyle, maxWidth: '400px' }}>
                      <div>
                        <div
                          style={{
                            color: '#94a3b8',
                            fontSize: '12px',
                            lineHeight: '1.4',
                            display: expandedRows.has(`evidence_${row.id}`) ? 'block' : '-webkit-box',
                            WebkitLineClamp: expandedRows.has(`evidence_${row.id}`) ? 'unset' : 3,
                            WebkitBoxOrient: 'vertical',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                          title={row.evidence_text || ''}
                        >
                          {row.evidence_text || '暂无原文证据'}
                        </div>
                        {row.evidence_text && row.evidence_text.length > 150 && (
                          <button
                            onClick={() => toggleExpand(`evidence_${row.id}`)}
                            className="link-button"
                            style={{ fontSize: '11px', marginTop: '4px', color: '#60a5fa' }}
                          >
                            {expandedRows.has(`evidence_${row.id}`) ? '收起' : '展开'}
                          </button>
                        )}
                      </div>
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

