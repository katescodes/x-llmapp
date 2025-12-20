/**
 * 风险详情组件
 * 显示选中风险的详细信息
 */
import React from 'react';
import { TenderRisk } from '../../types/tender';

export interface RiskDetailProps {
  item: TenderRisk | null;
  onOpenEvidence: (chunkIds: string[]) => void;
}

export default function RiskDetail(props: RiskDetailProps): JSX.Element {
  const { item, onOpenEvidence } = props;

  if (!item) {
    return (
      <div className="kb-empty-state" style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        height: '100%',
        flexDirection: 'column',
        gap: '12px'
      }}>
        <div style={{ fontSize: '32px' }}>📋</div>
        <div>请选择一条风险</div>
      </div>
    );
  }

  const copyToClipboard = () => {
    const text = `
【${item.risk_type === 'mustReject' ? '必须废标' : '注意事项'}】${item.title}

${item.description || ''}

${item.suggestion ? `💡 建议：${item.suggestion}` : ''}

${item.tags.length > 0 ? `标签：${item.tags.join(', ')}` : ''}
    `.trim();
    
    navigator.clipboard.writeText(text).then(() => {
      alert('已复制到剪贴板');
    }).catch(() => {
      alert('复制失败');
    });
  };

  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      height: '100%',
      overflow: 'auto',
      padding: '16px'
    }}>
      {/* 标题区域 */}
      <div style={{ marginBottom: '16px' }}>
        <h3 style={{ 
          fontSize: '18px', 
          fontWeight: 600, 
          margin: '0 0 12px 0',
          color: '#e5e7eb',
          lineHeight: '1.4'
        }}>
          {item.title}
        </h3>
        
        {/* Badges */}
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <span
            style={{
              fontSize: '12px',
              padding: '4px 10px',
              borderRadius: '6px',
              border: item.risk_type === 'mustReject'
                ? '1px solid rgba(239, 68, 68, 0.5)'
                : '1px solid rgba(148, 163, 184, 0.4)',
              color: item.risk_type === 'mustReject' ? '#ef4444' : '#94a3b8',
            }}
          >
            {item.risk_type === 'mustReject' ? '⚠️ 必须废标' : '⚡ 注意事项'}
          </span>

          {item.severity && (
            <span
              style={{
                fontSize: '12px',
                padding: '4px 10px',
                borderRadius: '6px',
                border:
                  item.severity === 'high'
                    ? '1px solid rgba(239, 68, 68, 0.5)'
                    : item.severity === 'medium'
                    ? '1px solid rgba(251, 191, 36, 0.5)'
                    : '1px solid rgba(148, 163, 184, 0.4)',
                color:
                  item.severity === 'high'
                    ? '#ef4444'
                    : item.severity === 'medium'
                    ? '#fbbf24'
                    : '#94a3b8',
              }}
            >
              严重度: {item.severity === 'high' ? '高' : item.severity === 'medium' ? '中' : '低'}
            </span>
          )}
        </div>
      </div>

      {/* 描述 */}
      {item.description && (
        <div style={{ marginBottom: '16px' }}>
          <div style={{ 
            fontSize: '12px', 
            color: '#94a3b8', 
            marginBottom: '6px',
            fontWeight: 600
          }}>
            描述
          </div>
          <div style={{ 
            fontSize: '14px', 
            color: '#e5e7eb', 
            lineHeight: '1.6',
            whiteSpace: 'pre-wrap'
          }}>
            {item.description}
          </div>
        </div>
      )}

      {/* 建议 */}
      {item.suggestion && (
        <div style={{ marginBottom: '16px' }}>
          <div style={{ 
            fontSize: '12px', 
            color: '#94a3b8', 
            marginBottom: '6px',
            fontWeight: 600
          }}>
            💡 建议
          </div>
          <div style={{ 
            fontSize: '14px', 
            color: '#e5e7eb', 
            lineHeight: '1.6',
            whiteSpace: 'pre-wrap',
            padding: '10px',
            background: 'rgba(251, 191, 36, 0.1)',
            borderRadius: '6px',
            border: '1px solid rgba(251, 191, 36, 0.2)'
          }}>
            {item.suggestion}
          </div>
        </div>
      )}

      {/* 标签 */}
      {item.tags && item.tags.length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          <div style={{ 
            fontSize: '12px', 
            color: '#94a3b8', 
            marginBottom: '6px',
            fontWeight: 600
          }}>
            标签
          </div>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {item.tags.map((tag, idx) => (
              <span
                key={idx}
                style={{
                  fontSize: '12px',
                  padding: '4px 10px',
                  borderRadius: '6px',
                  background: 'rgba(148, 163, 184, 0.15)',
                  color: '#94a3b8',
                  border: '1px solid rgba(148, 163, 184, 0.25)',
                }}
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 底部按钮 */}
      <div style={{ 
        marginTop: 'auto', 
        paddingTop: '16px', 
        borderTop: '1px solid rgba(148, 163, 184, 0.2)',
        display: 'flex',
        gap: '8px',
        flexWrap: 'wrap'
      }}>
        {item.evidence_chunk_ids && item.evidence_chunk_ids.length > 0 && (
          <button
            onClick={() => onOpenEvidence(item.evidence_chunk_ids)}
            className="kb-create-form"
            style={{
              width: 'auto',
              marginBottom: 0,
              padding: '8px 16px',
              fontSize: '13px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            📄 查看证据 ({item.evidence_chunk_ids.length})
          </button>
        )}
        
        <button
          onClick={copyToClipboard}
          className="link-button"
          style={{
            padding: '8px 16px',
            border: '1px solid rgba(148, 163, 184, 0.4)',
            borderRadius: '8px',
            fontSize: '13px'
          }}
        >
          📋 复制内容
        </button>
      </div>
    </div>
  );
}
