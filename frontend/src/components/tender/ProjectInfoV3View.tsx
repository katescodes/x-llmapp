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
import { getFieldLabel } from '../../types/fieldLabels';

/**
 * 定义每个类别的字段显示顺序
 * 用于控制前端展示顺序，不受后端JSON字段顺序影响
 */
const FIELD_DISPLAY_ORDER: Record<string, string[]> = {
  project_overview: [
    // 基本信息
    'project_name',
    'project_number',
    'owner_name',
    'agency_name',
    'contact_person',
    'contact_phone',
    'project_location',
    'fund_source',
    'procurement_method',
    'budget',
    'max_price',
    // 范围与标段
    'project_scope',
    'lot_division',
    'lots',
    // 进度与递交
    'bid_deadline',
    'bid_opening_time',
    'bid_opening_location',
    'submission_method',
    'submission_address',
    'implementation_schedule',
    'key_milestones',
    // 保证金与担保
    'bid_bond_amount',
    'bid_bond_form',
    'bid_bond_deadline',
    'bid_bond_return',
    'performance_bond',
    'other_guarantees',
  ],
  bidder_qualification: [
    'general_requirements',
    'special_requirements',
    'qualification_items',
    'must_provide_documents',
  ],
  evaluation_and_scoring: [
    'evaluation_method',
    'reject_conditions',
    'scoring_items',
    'price_scoring_method',
  ],
  business_terms: [
    'payment_terms',
    'delivery_terms',
    'warranty_terms',
    'acceptance_terms',
    'liability_terms',
    'clauses',
  ],
  technical_requirements: [
    'technical_specifications',
    'quality_standards',
    'technical_parameters',
    'technical_proposal_requirements',
  ],
  document_preparation: [
    'bid_documents_structure',
    'format_requirements',
    'copies_required',
    'required_forms',
    'signature_and_seal',
  ],
};

type Props = {
  info: Record<string, any>;
  onEvidence?: (chunkIds: string[]) => void;
};

/**
 * 渲染对象数组为表格
 */
const renderObjectArrayTable = (
  items: any[], 
  onEvidence?: (chunkIds: string[]) => void
) => {
  if (items.length === 0) return null;
  
  // 获取所有可能的列（从第一个对象中提取，排除 evidence_chunk_ids）
  const firstItem = items[0];
  const columns = Object.keys(firstItem).filter(key => key !== 'evidence_chunk_ids');
  
  return (
    <div className="tender-table-wrap" style={{ marginTop: 10 }}>
      <table className="tender-table">
        <thead>
          <tr>
            {columns.map(col => (
              <th key={col}>{getFieldLabel(col)}</th>
            ))}
            <th style={{ width: 100 }}>证据</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, idx) => {
            const evidenceIds = item.evidence_chunk_ids || [];
            return (
              <tr key={idx}>
                {columns.map(col => {
                  const val = item[col];
                  let displayValue = '—';
                  
                  if (val !== null && val !== undefined && val !== '') {
                    if (typeof val === 'boolean') {
                      displayValue = val ? '是' : '否';
                    } else if (Array.isArray(val)) {
                      displayValue = val.join('、');
                    } else {
                      displayValue = String(val);
                    }
                  }
                  
                  return (
                    <td key={col} className="tender-cell">
                      {displayValue}
                    </td>
                  );
                })}
                <td>
                  {evidenceIds.length > 0 && onEvidence && (
                    <button 
                      onClick={() => onEvidence(evidenceIds)}
                      className="link-button"
                      style={{ fontSize: '12px' }}
                    >
                      📎 ({evidenceIds.length})
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
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
    return null; // 空值不渲染
  }

  // 处理数组
  if (Array.isArray(value)) {
    // 空数组不渲染
    if (value.length === 0) return null;
    
    // 检查是否是对象数组（如 clauses, scoring_items 等）
    const hasObjects = value.some(item => typeof item === 'object' && item !== null);
    
    if (hasObjects) {
      // 渲染为表格
      return (
        <div key={label} style={{ gridColumn: '1 / -1', marginTop: 16 }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            marginBottom: 8 
          }}>
            <div style={{ fontWeight: 600, fontSize: '14px' }}>
              {label} ({value.length} 项)
            </div>
            {evidenceIds.length > 0 && onEvidence && (
              <button 
                onClick={() => onEvidence(evidenceIds)}
                className="link-button"
                style={{ fontSize: '12px' }}
              >
                📎 证据 ({evidenceIds.length})
              </button>
            )}
          </div>
          {renderObjectArrayTable(value, onEvidence)}
        </div>
      );
    } else {
      // 渲染简单数组（字符串数组）
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
            {value.map((item, idx) => (
              <span key={idx}>
                {String(item)}
                {idx < value.length - 1 && '、'}
              </span>
            ))}
          </div>
        </div>
      );
    }
  }

  // 处理对象（但不是数组）
  if (typeof value === 'object') {
    return null; // 嵌套对象暂不渲染（避免混乱）
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

  // ✅ 使用预定义的字段顺序，如果没有定义则使用原始顺序
  const fieldOrder = FIELD_DISPLAY_ORDER[categoryKey as string];
  
  let fields: [string, any][];
  if (fieldOrder) {
    // 按预定义顺序排列字段
    fields = fieldOrder
      .filter(key => key !== 'evidence_chunk_ids' && key in categoryData)
      .map(key => [key, categoryData[key]]);
    
    // 添加未在预定义顺序中的字段（兜底）
    const definedKeys = new Set(fieldOrder);
    Object.entries(categoryData).forEach(([key, value]) => {
      if (key !== 'evidence_chunk_ids' && !definedKeys.has(key)) {
        fields.push([key, value]);
      }
    });
  } else {
    // 没有预定义顺序，使用原始顺序
    fields = Object.entries(categoryData).filter(
      ([key]) => key !== 'evidence_chunk_ids'
    );
  }

  // 渲染所有字段，过滤掉 null 结果
  const renderedFields = fields
    .map(([key, value]) => {
      const fieldLabel = getFieldLabel(key);
      return renderField(fieldLabel, value, [], onEvidence);
    })
    .filter(Boolean); // 过滤掉 null 和 undefined

  // 如果没有任何可渲染的字段，则不显示该类别
  if (renderedFields.length === 0) return null;

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
        {renderedFields}
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

