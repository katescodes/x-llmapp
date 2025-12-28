export type TenderProject = {
  id: string;
  kb_id: string;
  name: string;
  description?: string;
  status: string;
};

export type TenderProjectDoc = {
  id: string;
  project_id: string;
  kb_doc_id: string;
  doc_role: "tender" | "bid" | "attachment";
  bidder_name?: string | null;
  created_at?: string;
};

export type TenderDirectoryNode = {
  id: string;
  parent_id?: string | null;
  order_no: number;
  level: number;
  numbering?: string | null;
  title: string;
  is_required: boolean;
  source: string;
  evidence_chunk_ids: string[];
};

// ==================== Step F: 新增类型 ====================

export type ReviewStatus = "PASS" | "WARN" | "FAIL" | "PENDING";
export type EvidenceRole = "tender" | "bid";

export interface EvidenceItem {
  role: EvidenceRole;
  segment_id?: string;
  asset_id?: string;
  page_start?: number | null;
  page_end?: number | null;
  heading_path?: string | null;
  quote?: string | null;
  source?: string; // doc_segments/fallback_chunk/derived_consistency
  meta?: any;
}

// ==================== 原有类型（扩展） ====================

export type TenderReviewItem = {
  id: string;
  dimension: string;
  clause_title?: string | null;
  tender_requirement: string;
  bidder_name?: string | null;
  bid_response?: string | null;
  
  // Legacy fields (保留兼容)
  result: "pass" | "risk" | "fail";
  is_hard: boolean;
  remark?: string | null;
  tender_evidence_chunk_ids: string[];
  bid_evidence_chunk_ids: string[];
  
  // Step F: 新增字段
  status?: ReviewStatus;
  evaluator?: string;
  requirement_id?: string;
  matched_response_id?: string;
  
  evidence_json?: EvidenceItem[] | null;
  rule_trace_json?: any;
  computed_trace_json?: any;
};

export type EvidenceChunk = {
  chunk_id: string;
  kb_id: string;
  doc_id: string;
  title?: string | null;
  url?: string | null;
  position: number;
  content: string;
};

export type FormatTemplate = {
  id: string;
  name: string;
  description?: string | null;
  style_config: Record<string, any>;
  is_public: boolean;
  template_sha256?: string | null;
  template_spec_version?: string | null;
  template_spec_analyzed_at?: string | null;
  // 确定性解析（header/footer/section 等）+ 预览
  parse_status?: string | null;
  parse_error?: string | null;
  parse_result_json?: Record<string, any> | null;
  parse_updated_at?: string | null;
  preview_docx_path?: string | null;
  preview_pdf_path?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type DeletePlanItem = {
  type: string;
  count: number;
  samples: string[];
  physical_targets: string[];
};

export type ProjectDeletePlan = {
  project_id: string;
  project_name: string;
  items: DeletePlanItem[];
  confirm_token: string;
  warning: string;
};

export type ProjectDeleteRequest = {
  confirm_text: string;
  confirm_token: string;
};

// ==================== 范本片段（目录页侧边栏） ====================

export type SampleFragment = {
  id: string;
  title: string;
  fragment_type: string;
  confidence?: number;
};

export type SampleFragmentPreview = {
  id: string;
  title: string;
  fragment_type: string;
  preview_html: string;
  warnings?: string[];
};
