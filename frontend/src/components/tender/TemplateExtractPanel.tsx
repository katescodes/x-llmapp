/**
 * 投标文件格式/样表抽取面板
 * 展示抽取结果、证据链、状态机处理
 */
import React, { useState } from 'react';
import type { FC } from 'react';

// ==================== 类型定义 ====================

export type TemplateExtractStatus = 
  | 'SUCCESS' 
  | 'NOT_FOUND' 
  | 'NEED_OCR' 
  | 'NEED_CONFIRM' 
  | 'LOW_COVERAGE';

export type TemplateKind =
  | 'BID_LETTER'
  | 'LEGAL_AUTHORIZATION'
  | 'PRICE_SCHEDULE'
  | 'DEVIATION_TABLE'
  | 'COMMITMENT_LETTER'
  | 'PERFORMANCE_TABLE'
  | 'STAFF_TABLE'
  | 'CREDENTIALS_LIST'
  | 'OTHER';

export interface TemplateEvidence {
  type: 'PARAGRAPH' | 'TABLE_CELL' | 'TEXTBOX' | 'IMAGE_ANCHOR';
  block_id: string;
  order_no: number;
  score: number;
  keywords_hit: string[];
  snippet: string;
  reason: string;
}

export interface TemplateSpan {
  kind: TemplateKind;
  display_title: string;
  start_block_id: string;
  end_block_id: string;
  confidence: number;
  evidence_block_ids: string[];
  reason: string;
}

export interface TemplateExtractResult {
  status: TemplateExtractStatus;
  templates: TemplateSpan[];
  evidences: TemplateEvidence[];
  diagnostics: {
    recall_hit_count: number;
    window_count: number;
    llm_call_count: number;
    coverage_ratio: number;
    missing_kinds: TemplateKind[];
    total_blocks: number;
    text_density: number;
    image_anchor_count: number;
    extraction_time_ms: number;
  };
  message?: string;
}

// ==================== 组件Props ====================

export interface TemplateExtractPanelProps {
  projectId: string;
  onTemplateSelect?: (span: TemplateSpan) => void;
  onBlockPreview?: (blockId: string) => void;
}

// ==================== 主组件 ====================

export const TemplateExtractPanel: FC<TemplateExtractPanelProps> = ({
  projectId,
  onTemplateSelect,
  onBlockPreview,
}) => {
  const [result, setResult] = useState<TemplateExtractResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<'NORMAL' | 'ENHANCED'>('NORMAL');

  // 执行抽取
  const handleExtract = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('auth_token') || localStorage.getItem('token') || '';
      const response = await fetch(
        `/api/apps/tender/projects/${projectId}/templates/extract`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({ mode }),
        }
      );

      const data = await response.json();
      if (data.success) {
        setResult(data.result);
      } else {
        alert(`抽取失败: ${data.message}`);
      }
    } catch (error) {
      console.error('抽取失败:', error);
      alert(`抽取失败: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  // 状态卡片渲染
  const renderStatusCard = () => {
    if (!result) return null;

    const { status, diagnostics, message } = result;
    const coveragePercent = (diagnostics.coverage_ratio * 100).toFixed(1);

    // 状态颜色映射
    const statusColors: Record<TemplateExtractStatus, string> = {
      SUCCESS: 'bg-green-50 border-green-200',
      NOT_FOUND: 'bg-gray-50 border-gray-200',
      NEED_OCR: 'bg-yellow-50 border-yellow-200',
      NEED_CONFIRM: 'bg-blue-50 border-blue-200',
      LOW_COVERAGE: 'bg-orange-50 border-orange-200',
    };

    const statusLabels: Record<TemplateExtractStatus, string> = {
      SUCCESS: '✓ 成功',
      NOT_FOUND: '✗ 未找到',
      NEED_OCR: '⚠ 需要OCR',
      NEED_CONFIRM: '? 需要确认',
      LOW_COVERAGE: '⚠ 覆盖率不足',
    };

    return (
      <div className={`p-4 border rounded-lg mb-4 ${statusColors[status]}`}>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold">{statusLabels[status]}</h3>
            <p className="text-sm text-gray-600 mt-1">{message}</p>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold">{result.templates.length}</div>
            <div className="text-sm text-gray-500">个范本</div>
          </div>
        </div>

        {status === 'SUCCESS' && (
          <div className="mt-3 flex gap-4 text-sm">
            <div>覆盖率: <span className="font-semibold">{coveragePercent}%</span></div>
            <div>耗时: <span className="font-semibold">{diagnostics.extraction_time_ms}ms</span></div>
          </div>
        )}

        {status === 'LOW_COVERAGE' && diagnostics.missing_kinds.length > 0 && (
          <div className="mt-3">
            <div className="text-sm text-gray-600">缺失的范本类型：</div>
            <div className="flex flex-wrap gap-2 mt-1">
              {diagnostics.missing_kinds.map((kind) => (
                <span key={kind} className="px-2 py-1 bg-white rounded text-xs">
                  {kind}
                </span>
              ))}
            </div>
            <button
              onClick={() => setMode('ENHANCED')}
              className="mt-2 px-3 py-1 bg-blue-500 text-white rounded text-sm"
            >
              增强重试
            </button>
          </div>
        )}

        {status === 'NEED_CONFIRM' && (
          <div className="mt-3 text-sm text-gray-600">
            请从下方证据列表中选择起点，点击"从这里开始抽取"
          </div>
        )}

        {status === 'NEED_OCR' && (
          <div className="mt-3 text-sm text-gray-600">
            检测到大量图片或扫描内容，建议开启OCR功能
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="p-4">
      <div className="mb-4 flex items-center gap-4">
        <h2 className="text-xl font-bold">投标文件格式抽取</h2>
        <button
          onClick={handleExtract}
          disabled={loading}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
        >
          {loading ? '抽取中...' : '开始抽取'}
        </button>
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as 'NORMAL' | 'ENHANCED')}
          className="px-3 py-2 border rounded"
        >
          <option value="NORMAL">普通模式</option>
          <option value="ENHANCED">增强模式</option>
        </select>
      </div>

      {renderStatusCard()}

      {result && (
        <div className="grid grid-cols-2 gap-4">
          {/* 左侧：范本列表 */}
          <div>
            <h3 className="text-lg font-semibold mb-2">
              抽取结果 ({result.templates.length})
            </h3>
            {/* TODO: 实现TemplateSpansList组件 */}
            <div className="text-sm text-gray-500">
              TemplateSpansList 组件待实现
            </div>
          </div>

          {/* 右侧：证据列表 */}
          <div>
            <h3 className="text-lg font-semibold mb-2">
              证据列表 ({result.evidences.length})
            </h3>
            {/* TODO: 实现EvidenceList组件 */}
            <div className="text-sm text-gray-500">
              EvidenceList 组件待实现
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TemplateExtractPanel;

