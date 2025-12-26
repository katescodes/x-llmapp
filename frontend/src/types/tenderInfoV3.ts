/**
 * Tender Info V3 类型定义
 * 
 * 对应后端 tender_info_v3.py 的九大类结构
 */

/**
 * Schema 版本标识
 */
export type TenderInfoSchemaVersion = "tender_info_v3";

/**
 * 1. 项目概况
 */
export interface ProjectOverview {
  project_name?: string;
  project_number?: string;
  budget_amount?: number;
  control_price?: number;
  max_price?: number;
  purchaser?: string;
  bidding_agent?: string;
  owner?: string;
  agency?: string;
  contact_person?: string;
  contact_phone?: string;
  project_duration?: string;
  quality_standard?: string;
  funding_source?: string;
  procurement_method?: string;
  evaluation_method?: string;
  evidence_chunk_ids?: string[];
}

/**
 * 2. 范围与标段
 */
export interface ScopeAndLots {
  lot_division?: string[];
  procurement_packages?: string[];
  procurement_content?: string;
  procurement_scope?: string;
  quantity_and_unit?: Array<{ item: string; quantity: number; unit: string }>;
  delivery_location?: string;
  delivery_time?: string;
  service_scope?: string;
  service_requirements?: string[];
  evidence_chunk_ids?: string[];
}

/**
 * 3. 进度与提交
 */
export interface ScheduleAndSubmission {
  bid_deadline?: string;
  submission_deadline?: string;
  opening_time?: string;
  bid_validity_period?: string;
  performance_bond?: number;
  bid_bond?: number;
  bond_payment_method?: string;
  bond_refund_time?: string;
  bid_document_format?: string;
  bid_document_copies?: number;
  sealing_requirements?: string;
  submission_method?: string;
  evidence_chunk_ids?: string[];
}

/**
 * 4. 投标人资格
 */
export interface BidderQualification {
  qualification_requirements?: string[];
  qualification_level?: string;
  performance_requirements?: string[];
  financial_requirements?: string[];
  credit_requirements?: string[];
  personnel_requirements?: string[];
  consortium_allowed?: boolean;
  agent_allowed?: boolean;
  subcontracting_allowed?: boolean;
  registered_capital?: number;
  business_license_required?: boolean;
  credit_record_requirements?: string[];
  litigation_record_requirements?: string[];
  must_provide_documents?: string[];
  evidence_chunk_ids?: string[];
}

/**
 * 5. 评审与评分
 */
export interface EvaluationAndScoring {
  evaluation_method?: string;
  scoring_rules?: string[];
  scoring_table?: Array<{ criterion: string; max_score: number; weight?: number }>;
  price_score_weight?: number;
  technical_score_weight?: number;
  business_score_weight?: number;
  credit_score_weight?: number;
  rejection_conditions?: string[];
  disqualification_conditions?: string[];
  qualification_review?: string;
  evaluation_experts?: string;
  evaluation_committee?: string;
  evidence_chunk_ids?: string[];
}

/**
 * 6. 商务条款
 */
export interface BusinessTerms {
  contract_terms?: string[];
  payment_method?: string;
  payment_terms?: string;
  delivery_period?: string;
  warranty_period?: string;
  acceptance_standard?: string;
  breach_liability?: string[];
  invoice_requirements?: string;
  tax_requirements?: string;
  intellectual_property?: string;
  confidentiality_requirements?: string;
  dispute_resolution?: string;
  applicable_law?: string;
  evidence_chunk_ids?: string[];
}

/**
 * 7. 技术要求
 */
export interface TechnicalRequirements {
  technical_specifications?: string[];
  technical_standards?: string[];
  technical_parameters?: Array<{ parameter: string; requirement: string; unit?: string }>;
  performance_indicators?: Array<{ indicator: string; requirement: string }>;
  functional_requirements?: string[];
  equipment_parameters?: Array<{ equipment: string; parameters: Record<string, any> }>;
  brand_requirements?: string[];
  model_requirements?: string[];
  evidence_chunk_ids?: string[];
}

/**
 * 8. 文件编制
 */
export interface DocumentPreparation {
  bid_document_structure?: string[];
  format_requirements?: string[];
  table_of_contents?: string[];
  attachment_list?: string[];
  required_forms?: Array<{
    form_name: string;
    is_mandatory: boolean;
    description?: string;
    evidence_chunk_ids?: string[];
  }>;
  certification_materials?: string[];
  authorization_letter_required?: boolean;
  commitment_letter_required?: boolean;
  price_table_required?: boolean;
  qualification_documents?: string[];
  technical_proposal_requirements?: string[];
  business_proposal_requirements?: string[];
  response_file_requirements?: string[];
  evidence_chunk_ids?: string[];
}

/**
 * 9. 投标保证金
 */
export interface BidSecurity {
  bid_bond_amount?: number;
  performance_bond_amount?: number;
  payment_method?: string;
  submission_form?: string;
  refund_conditions?: string[];
  guarantee_letter_required?: boolean;
  bank_guarantee_required?: boolean;
  evidence_chunk_ids?: string[];
}

/**
 * Tender Info V3 顶层结构
 */
export interface TenderInfoV3 {
  schema_version: TenderInfoSchemaVersion;
  project_overview: ProjectOverview;
  scope_and_lots: ScopeAndLots;
  schedule_and_submission: ScheduleAndSubmission;
  bidder_qualification: BidderQualification;
  evaluation_and_scoring: EvaluationAndScoring;
  business_terms: BusinessTerms;
  technical_requirements: TechnicalRequirements;
  document_preparation: DocumentPreparation;
  bid_security: BidSecurity;
}

/**
 * API 响应类型
 */
export interface TenderProjectInfoResponse {
  id: string;
  project_id: string;
  data_json: TenderInfoV3;
  created_at: string;
  updated_at: string;
}

/**
 * 类型守卫：检查是否为 V3 结构
 */
export function isTenderInfoV3(data: any): data is TenderInfoV3 {
  return data && data.schema_version === "tender_info_v3";
}

/**
 * 获取所有九大类的 key
 */
export const TENDER_INFO_V3_CATEGORIES = [
  "project_overview",
  "scope_and_lots",
  "schedule_and_submission",
  "bidder_qualification",
  "evaluation_and_scoring",
  "business_terms",
  "technical_requirements",
  "document_preparation",
  "bid_security",
] as const;

/**
 * V3 类别类型（从常量推导）
 */
export type TenderInfoV3Category = typeof TENDER_INFO_V3_CATEGORIES[number];

/**
 * 类别显示名称映射
 */
export const TENDER_INFO_V3_CATEGORY_LABELS: Record<TenderInfoV3Category, string> = {
  project_overview: "项目概况",
  scope_and_lots: "范围与标段",
  schedule_and_submission: "进度与提交",
  bidder_qualification: "投标人资格",
  evaluation_and_scoring: "评审与评分",
  business_terms: "商务条款",
  technical_requirements: "技术要求",
  document_preparation: "文件编制",
  bid_security: "投标保证金",
};

