/**
 * 风险识别工具栏组件
 * 提供筛选、搜索、排序功能
 */
import React from 'react';

export type RiskTypeTab = 'all' | 'mustReject' | 'other';
export type Severity = 'all' | 'high' | 'medium' | 'low';
export type SortKey = 'severity' | 'default';

export interface RiskFilters {
  typeTab: RiskTypeTab;
  severity: Severity;
  keyword: string;
  sort: SortKey;
}

export interface RiskToolbarProps {
  filters: RiskFilters;
  onChange: (patch: Partial<RiskFilters>) => void;
  summary: {
    mustReject: number;
    other: number;
    total: number;
  };
}

export default function RiskToolbar(props: RiskToolbarProps): JSX.Element {
  const { filters, onChange, summary } = props;

  return (
    <div style={{ borderBottom: '1px solid rgba(148, 163, 184, 0.2)', paddingBottom: '12px', marginBottom: '12px' }}>
      {/* Tabs - 类型筛选 */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', flexWrap: 'wrap' }}>
        <button
          onClick={() => onChange({ typeTab: 'all' })}
          className={filters.typeTab === 'all' ? 'pill-button' : 'link-button'}
          style={{
            padding: filters.typeTab === 'all' ? '6px 12px' : '6px 8px',
            border: filters.typeTab === 'all' ? '1px solid rgba(96, 165, 250, 0.8)' : 'none',
            borderRadius: '999px',
          }}
        >
          全部 ({summary.total})
        </button>
        <button
          onClick={() => onChange({ typeTab: 'mustReject' })}
          className={filters.typeTab === 'mustReject' ? 'pill-button' : 'link-button'}
          style={{
            padding: filters.typeTab === 'mustReject' ? '6px 12px' : '6px 8px',
            border: filters.typeTab === 'mustReject' ? '1px solid rgba(96, 165, 250, 0.8)' : 'none',
            borderRadius: '999px',
          }}
        >
          ⚠️ 必须废标 ({summary.mustReject})
        </button>
        <button
          onClick={() => onChange({ typeTab: 'other' })}
          className={filters.typeTab === 'other' ? 'pill-button' : 'link-button'}
          style={{
            padding: filters.typeTab === 'other' ? '6px 12px' : '6px 8px',
            border: filters.typeTab === 'other' ? '1px solid rgba(96, 165, 250, 0.8)' : 'none',
            borderRadius: '999px',
          }}
        >
          注意事项 ({summary.other})
        </button>
      </div>

      {/* 搜索和筛选 */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '8px', flexWrap: 'wrap' }}>
        <input
          type="text"
          placeholder="搜索标题/描述/标签..."
          value={filters.keyword}
          onChange={(e) => onChange({ keyword: e.target.value })}
          className="sidebar-select"
          style={{
            flex: '1 1 200px',
            minWidth: '150px',
            marginBottom: 0,
            fontSize: '13px',
          }}
        />
        
        <select
          value={filters.severity}
          onChange={(e) => onChange({ severity: e.target.value as Severity })}
          className="sidebar-select"
          style={{
            width: 'auto',
            minWidth: '100px',
            marginBottom: 0,
          }}
        >
          <option value="all">全部严重度</option>
          <option value="high">高</option>
          <option value="medium">中</option>
          <option value="low">低</option>
        </select>

        <select
          value={filters.sort}
          onChange={(e) => onChange({ sort: e.target.value as SortKey })}
          className="sidebar-select"
          style={{
            width: 'auto',
            minWidth: '120px',
            marginBottom: 0,
          }}
        >
          <option value="default">默认排序</option>
          <option value="severity">严重度优先</option>
        </select>
      </div>
    </div>
  );
}
