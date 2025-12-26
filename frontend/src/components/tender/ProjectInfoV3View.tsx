/**
 * ProjectInfoV3View - 自动适配 V3 九大类的展示组件
 * 
 * 特性：
 * 1. 自动检测 schema_version
 * 2. V3 结构：展示九大类
 * 3. 旧结构：回退到旧版展示
 * 4. 支持证据链查看
 */
import React, { useMemo } from 'react';
import { 
  TenderInfoV3, 
  isTenderInfoV3,
  TENDER_INFO_V3_CATEGORIES,
  TENDER_INFO_V3_CATEGORY_LABELS,
  TenderInfoV3Category
} from '../../types/tenderInfoV3';

type Props = {
  info: Record<string, any>;
  onEvidence?: (chunkIds: string[]) => void;
};

/**
 * 渲染单个字段
 */
const renderField = (
  label: string, 
  value: any, 
  evidenceIds: string[] = [],
  onEvidence?: (chunkIds: string[]) => void
) => {
  // 处理空值
  if (value === null || value === undefined || value === '') {
    return (
      <div key={label} className="tender-kv-item">
        <div className="tender-kv-label">{label}</div>
        <div className="tender-kv-value">—</div>
      </div>
    );
  }

  // 处理数组
  if (Array.isArray(value)) {
    return (
      <div key={label} className="tender-kv-item" style={{ gridColumn: '1 / -1' }}>
        <div className="tender-kv-label">
          {label}
          {evidenceIds.length > 0 && onEvidence && (
            <button 
              onClick={() => onEvidence(evidenceIds)}
              className="link-button"
              style={{ marginLeft: 8, fontSize: '12px' }}
            >
              📎 证据 ({evidenceIds.length})
            </button>
          )}
        </div>
        <div className="tender-kv-value">
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            {value.map((item, idx) => (
              <li key={idx}>{typeof item === 'object' ? JSON.stringify(item) : String(item)}</li>
            ))}
          </ul>
        </div>
      </div>
    );
  }

  // 处理对象
  if (typeof value === 'object') {
    return (
      <div key={label} className="tender-kv-item" style={{ gridColumn: '1 / -1' }}>
        <div className="tender-kv-label">{label}</div>
        <div className="tender-kv-value">
          <pre style={{ margin: 0, fontSize: '12px' }}>
            {JSON.stringify(value, null, 2)}
          </pre>
        </div>
      </div>
    );
  }

  // 处理普通值
  return (
    <div key={label} className="tender-kv-item">
      <div className="tender-kv-label">
        {label}
        {evidenceIds.length > 0 && onEvidence && (
          <button 
            onClick={() => onEvidence(evidenceIds)}
            className="link-button"
            style={{ marginLeft: 8, fontSize: '12px' }}
          >
            📎 证据 ({evidenceIds.length})
          </button>
        )}
      </div>
      <div className="tender-kv-value">{String(value)}</div>
    </div>
  );
};

/**
 * 渲染 V3 单个类别
 */
const renderV3Category = (
  categoryKey: keyof TenderInfoV3,
  categoryData: any,
  onEvidence?: (chunkIds: string[]) => void
) => {
  if (!categoryData || categoryKey === 'schema_version') return null;

  const label = TENDER_INFO_V3_CATEGORY_LABELS[categoryKey] || categoryKey;
  const evidenceIds = categoryData.evidence_chunk_ids || [];

  // 过滤出非 evidence_chunk_ids 的字段
  const fields = Object.entries(categoryData).filter(
    ([key]) => key !== 'evidence_chunk_ids'
  );

  if (fields.length === 0) return null;

  return (
    <div className="source-card" style={{ marginBottom: 16 }} key={categoryKey as string}>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        marginBottom: 12 
      }}>
        <h4 style={{ margin: 0 }}>{label}</h4>
        {evidenceIds.length > 0 && onEvidence && (
          <button 
            onClick={() => onEvidence(evidenceIds)}
            className="link-button"
          >
            📎 查看证据 ({evidenceIds.length})
          </button>
        )}
      </div>

      <div className="tender-kv-grid">
        {fields.map(([key, value]) => {
          // 转换字段名为中文标签
          const fieldLabel = key
            .replace(/_/g, ' ')
            .replace(/\b\w/g, l => l.toUpperCase());
          
          return renderField(fieldLabel, value, [], onEvidence);
        })}
      </div>
    </div>
  );
};

/**
 * 主组件
 */
export default function ProjectInfoV3View({ info, onEvidence }: Props) {
  const [showRaw, setShowRaw] = React.useState(false);

  // 提取 data_json
  const dataJson = info?.data_json || info || {};

  // 检测是否为 V3 结构
  const isV3 = useMemo(() => {
    return isTenderInfoV3(dataJson);
  }, [dataJson]);

  // 如果是 V3 结构，渲染九大类
  if (isV3) {
    const tenderInfoV3 = dataJson as TenderInfoV3;

    return (
      <div>
        {/* 标题栏 */}
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          marginBottom: 16 
        }}>
          <h3 style={{ margin: 0 }}>
            招标信息 
            <span style={{ 
              marginLeft: 8, 
              fontSize: '12px', 
              color: '#52c41a',
              fontWeight: 'normal' 
            }}>
              ✓ V3 九大类
            </span>
          </h3>
          <button 
            onClick={() => setShowRaw(!showRaw)}
            className="link-button"
          >
            {showRaw ? '📋 卡片视图' : '🔍 JSON 视图'}
          </button>
        </div>

        {showRaw ? (
          // JSON 原始视图
          <pre className="md-pre">
            <code>{JSON.stringify(tenderInfoV3, null, 2)}</code>
          </pre>
        ) : (
          // 九大类卡片视图
          <div>
            {TENDER_INFO_V3_CATEGORIES.map((categoryKey) => {
              const categoryData = tenderInfoV3[categoryKey];
              return renderV3Category(categoryKey as keyof TenderInfoV3, categoryData, onEvidence);
            })}
          </div>
        )}
      </div>
    );
  }

  // 旧版结构 - 回退到旧组件
  return (
    <div>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        marginBottom: 16 
      }}>
        <h3 style={{ margin: 0 }}>
          招标信息 
          <span style={{ 
            marginLeft: 8, 
            fontSize: '12px', 
            color: '#faad14',
            fontWeight: 'normal' 
          }}>
            ⚠️ 旧版格式
          </span>
        </h3>
        <button 
          onClick={() => setShowRaw(!showRaw)}
          className="link-button"
        >
          {showRaw ? '📋 卡片视图' : '🔍 JSON 视图'}
        </button>
      </div>

      {showRaw ? (
        <pre className="md-pre">
          <code>{JSON.stringify(dataJson, null, 2)}</code>
        </pre>
      ) : (
        <div style={{ 
          padding: 16, 
          background: '#fffbe6', 
          border: '1px solid #ffe58f',
          borderRadius: 4 
        }}>
          <p style={{ margin: 0 }}>
            当前数据使用旧版格式。
            <br />
            请重新抽取项目信息以使用新版 V3 九大类结构。
          </p>
          <pre className="md-pre" style={{ marginTop: 12 }}>
            <code>{JSON.stringify(dataJson, null, 2)}</code>
          </pre>
        </div>
      )}
    </div>
  );
}

