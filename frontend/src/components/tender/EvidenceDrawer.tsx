/**
 * Step F-Frontend-4: 证据面板（Drawer）
 * 按 role 分组展示招标依据和投标依据
 */
import React, { useState } from 'react';
import type { TenderReviewItem, EvidenceItem } from '../../types/tender';
import { 
  splitEvidence, 
  formatPageNumber, 
  formatQuote,
  getStatus,
  getStatusText,
  getStatusColor
} from '../../types/reviewUtils';

interface EvidenceDrawerProps {
  item: TenderReviewItem | null;
  isOpen: boolean;
  onClose: () => void;
}

export default function EvidenceDrawer({ item, isOpen, onClose }: EvidenceDrawerProps) {
  const [showTrace, setShowTrace] = useState(false);
  
  if (!item || !isOpen) return null;
  
  const { tender, bid } = splitEvidence(item);
  const status = getStatus(item);
  
  const renderEvidence = (ev: EvidenceItem, index: number) => (
    <div key={`${ev.segment_id || index}`} className="evidence-item">
      <div className="evidence-meta">
        <span className="evidence-page">{formatPageNumber(ev)}</span>
        {ev.heading_path && (
          <span className="evidence-path">{ev.heading_path}</span>
        )}
        {ev.source && (
          <span className="evidence-source">来源: {ev.source}</span>
        )}
      </div>
      <div className="evidence-quote">
        {ev.quote ? formatQuote(ev.quote, 200) : <span style={{ color: '#64748b' }}>暂无引用</span>}
      </div>
    </div>
  );
  
  const copyToClipboard = (data: any) => {
    const text = JSON.stringify(data, null, 2);
    navigator.clipboard.writeText(text).then(() => {
      alert('已复制到剪贴板');
    });
  };
  
  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="drawer-header">
          <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600 }}>
            {item.clause_title || item.tender_requirement?.slice(0, 40) || '审核详情'}
            {item.clause_title && item.clause_title.length > 40 && '...'}
          </h3>
          <button 
            onClick={onClose}
            style={{ 
              background: 'none', 
              border: 'none', 
              color: '#94a3b8', 
              fontSize: '24px', 
              cursor: 'pointer',
              padding: '0 8px'
            }}
          >
            ×
          </button>
        </div>
        
        {/* Body */}
        <div className="drawer-body">
          {/* 状态与评估器 */}
          <div className="drawer-meta">
            <div>
              <span style={{ color: '#94a3b8', fontSize: '13px' }}>状态: </span>
              <span className={`tender-badge ${status.toLowerCase()}`}>
                {getStatusText(status)}
              </span>
            </div>
            <div>
              <span style={{ color: '#94a3b8', fontSize: '13px' }}>评估器: </span>
              <span style={{ color: '#e5e7eb', fontSize: '13px' }}>
                {item.evaluator || '-'}
              </span>
            </div>
            {item.dimension && (
              <div>
                <span style={{ color: '#94a3b8', fontSize: '13px' }}>维度: </span>
                <span style={{ color: '#e5e7eb', fontSize: '13px' }}>
                  {item.dimension}
                </span>
              </div>
            )}
          </div>
          
          {/* 招标要求 */}
          {item.tender_requirement && (
            <div className="drawer-section">
              <h4>📋 招标要求</h4>
              <div className="drawer-text-content">
                {item.tender_requirement}
              </div>
            </div>
          )}
          
          {/* 投标响应 */}
          {item.bid_response && (
            <div className="drawer-section">
              <h4>📝 投标响应</h4>
              <div className="drawer-text-content">
                {item.bid_response}
              </div>
            </div>
          )}
          
          {/* 招标依据 */}
          {tender.length > 0 && (
            <div className="evidence-section">
              <h4>📄 招标依据 ({tender.length})</h4>
              {tender.map(renderEvidence)}
            </div>
          )}
          
          {/* 投标依据 */}
          {bid.length > 0 && (
            <div className="evidence-section">
              <h4>📑 投标依据 ({bid.length})</h4>
              {bid.map(renderEvidence)}
            </div>
          )}
          
          {/* 空状态 */}
          {tender.length === 0 && bid.length === 0 && (
            <div className="empty-evidence">
              <div style={{ fontSize: '32px', marginBottom: '8px' }}>📭</div>
              <div>暂无证据信息</div>
            </div>
          )}
          
          {/* 备注 */}
          {item.remark && (
            <div className="drawer-section">
              <h4>💬 备注</h4>
              <div className="drawer-text-content" style={{ color: '#fbbf24' }}>
                {item.remark}
              </div>
            </div>
          )}
          
          {/* Step F-Frontend-5: Trace 展示 */}
          {(item.rule_trace_json || item.computed_trace_json) && (
            <div className="trace-accordion">
              <button 
                className="trace-toggle"
                onClick={() => setShowTrace(!showTrace)}
              >
                🔍 审核追踪
                <span style={{ marginLeft: '8px', fontSize: '12px' }}>
                  {showTrace ? '▼' : '▶'}
                </span>
              </button>
              
              {showTrace && (
                <div className="trace-content">
                  {item.rule_trace_json && (
                    <div className="trace-section">
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <h5>规则追踪</h5>
                        <button 
                          className="link-button"
                          onClick={() => copyToClipboard(item.rule_trace_json)}
                          style={{ fontSize: '12px' }}
                        >
                          📋 复制
                        </button>
                      </div>
                      <pre className="trace-json">
                        {JSON.stringify(item.rule_trace_json, null, 2)}
                      </pre>
                    </div>
                  )}
                  
                  {item.computed_trace_json && (
                    <div className="trace-section">
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <h5>计算过程</h5>
                        <button 
                          className="link-button"
                          onClick={() => copyToClipboard(item.computed_trace_json)}
                          style={{ fontSize: '12px' }}
                        >
                          📋 复制
                        </button>
                      </div>
                      <pre className="trace-json">
                        {JSON.stringify(item.computed_trace_json, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

