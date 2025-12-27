/**
 * 风险分析相关类型定义
 */

export interface RiskRow {
  id: string;
  requirement_id: string;
  dimension: string;
  req_type: string;
  requirement_text: string;
  allow_deviation: boolean;
  value_schema_json: any;
  evidence_chunk_ids: string[];
  // 派生字段
  consequence: 'reject' | 'hard_requirement' | 'score_loss';
  severity: 'high' | 'medium' | 'low';
  suggestion: string;
}

export interface ChecklistRow {
  id: string;
  requirement_id: string;
  dimension: string;
  req_type: string;
  requirement_text: string;
  allow_deviation: boolean;
  value_schema_json: any;
  evidence_chunk_ids: string[];
  // 派生字段
  category: string;
  severity: 'high' | 'medium' | 'low';
  title: string;
  detail: string;
  suggestion: string;
}

export interface RiskAnalysisStats {
  total_requirements: number;
  must_reject_count: number;
  checklist_count: number;
  high_severity_count: number;
  medium_severity_count: number;
  low_severity_count: number;
}

export interface RiskAnalysisData {
  must_reject_table: RiskRow[];
  checklist_table: ChecklistRow[];
  stats: RiskAnalysisStats;
}

// 维度中文映射
export const DIMENSION_LABELS: Record<string, string> = {
  qualification: '资格要求',
  technical: '技术要求',
  business: '商务要求',
  price: '价格要求',
  doc_structure: '文档结构',
  schedule_quality: '进度与质量',
  bid_security: '保证金',
  other: '其他',
};

// 要求类型中文映射
export const REQ_TYPE_LABELS: Record<string, string> = {
  must_provide: '必须提供',
  must_not_deviate: '不得偏离',
  threshold: '阈值要求',
  format: '格式要求',
  scoring: '评分项',
  other: '其他',
};

// 后果类型中文映射
export const CONSEQUENCE_LABELS: Record<string, string> = {
  reject: '废标/无效',
  hard_requirement: '关键要求',
  score_loss: '扣分/罚则',
};

// 严重性中文映射
export const SEVERITY_LABELS: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低',
};

