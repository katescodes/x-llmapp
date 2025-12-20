/**
 * 风险列表组件
 * 显示风险列表，支持选中和证据查看
 */
import React from 'react';
import { TenderRisk } from '../../types/tender';

export interface RiskListProps {
  items: TenderRisk[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onOpenEvidence: (chunkIds: string[]) => void;
}

export default function RiskList(props: RiskListProps): JSX.Element {
  const { items, selectedId, onSelect, onOpenEvidence } = props;

  if (items.length === 0) {
    return (
      <div className="kb-empty" style={{ padding: '24px', textAlign: 'center' }}>
        暂无风险记录
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      {items.map((risk) => {
        const isSelected = risk.id === selectedId;
        
        return (
          <div
            key={risk.id}
            className={`risk-row ${isSelected ? 'active' : ''}`}
            onClick={() => onSelect(risk.id)}
            style={{
              display: 'grid',
              gridTemplateColumns: 'auto auto 1fr auto auto',
              gap: '8px',
              alignItems: 'center',
              padding: '10px 12px',
              borderRadius: '8px',
              border: isSelected
                ? '1px solid rgba(96, 165, 250, 0.8)'
                : '1px solid rgba(148, 163, 184, 0.2)',
              background: isSelected
                ? 'rgba(37, 99, 235, 0.25)'
                : 'rgba(15, 23, 42, 0.6)',
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            {/* 类型 badge */}
            <span
              style={{
                fontSize: '11px',
                padding: '2px 6px',
                borderRadius: '4px',
                border: risk.risk_type === 'mustReject'
                  ? '1px solid rgba(239, 68, 68, 0.5)'
                  : '1px solid rgba(148, 163, 184, 0.4)',
                color: risk.risk_type === 'mustReject' ? '#ef4444' : '#94a3b8',
                whiteSpace: 'nowrap',
              }}
            >
              {risk.risk_type === 'mustReject' ? '废标' : '注意'}
            </span>

            {/* 严重度 badge */}
            {risk.severity && (
              <span
                style={{
                  fontSize: '11px',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  border:
                    risk.severity === 'high'
                      ? '1px solid rgba(239, 68, 68, 0.5)'
                      : risk.severity === 'medium'
                      ? '1px solid rgba(251, 191, 36, 0.5)'
                      : '1px solid rgba(148, 163, 184, 0.4)',
                  color:
                    risk.severity === 'high'
                      ? '#ef4444'
                      : risk.severity === 'medium'
                      ? '#fbbf24'
                      : '#94a3b8',
                  whiteSpace: 'nowrap',
                }}
              >
                {risk.severity === 'high' ? '高' : risk.severity === 'medium' ? '中' : '低'}
              </span>
            )}

            {/* 标题 */}
            <div
              className="line-clamp-2"
              style={{
                fontSize: '13px',
                fontWeight: isSelected ? 600 : 500,
                color: '#e5e7eb',
                lineHeight: '1.4',
              }}
            >
              {risk.title}
            </div>

            {/* 标签 */}
            {risk.tags && risk.tags.length > 0 && (
              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', maxWidth: '150px' }}>
                {risk.tags.slice(0, 3).map((tag, idx) => (
                  <span
                    key={idx}
                    style={{
                      fontSize: '10px',
                      padding: '2px 5px',
                      borderRadius: '3px',
                      background: 'rgba(148, 163, 184, 0.15)',
                      color: '#94a3b8',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {tag}
                  </span>
                ))}
                {risk.tags.length > 3 && (
                  <span
                    style={{
                      fontSize: '10px',
                      color: '#94a3b8',
                    }}
                  >
                    +{risk.tags.length - 3}
                  </span>
                )}
              </div>
            )}

            {/* 证据按钮 */}
            {risk.evidence_chunk_ids && risk.evidence_chunk_ids.length > 0 && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenEvidence(risk.evidence_chunk_ids);
                }}
                className="link-button"
                style={{
                  fontSize: '12px',
                  padding: '4px 8px',
                  border: '1px solid rgba(148, 163, 184, 0.3)',
                  borderRadius: '4px',
                  whiteSpace: 'nowrap',
                }}
              >
                证据({risk.evidence_chunk_ids.length})
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
