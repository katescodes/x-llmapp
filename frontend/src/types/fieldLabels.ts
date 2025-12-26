/**
 * V3 字段名中文映射表
 * 
 * 将所有 tender_info_v3 的英文字段名映射为中文
 */

// 1. 项目概况 (project_overview)
const PROJECT_OVERVIEW_LABELS: Record<string, string> = {
  project_name: "项目名称",
  project_number: "项目编号/招标编号",
  owner_name: "采购人/业主/招标人",
  agency_name: "代理机构",
  contact_person: "联系人",
  contact_phone: "联系电话",
  project_location: "项目地点",
  fund_source: "资金来源",
  procurement_method: "采购方式",
  budget: "预算金额",
  max_price: "招标控制价/最高限价",
};

// 2. 范围与标段 (scope_and_lots)
const SCOPE_AND_LOTS_LABELS: Record<string, string> = {
  project_scope: "项目范围/采购内容",
  lot_division: "标段划分说明",
  lots: "标段详情",
  lot_number: "标段编号",
  lot_name: "标段名称",
  scope: "标段范围",
};

// 3. 进度与递交 (schedule_and_submission)
const SCHEDULE_AND_SUBMISSION_LABELS: Record<string, string> = {
  bid_deadline: "投标截止时间",
  bid_opening_time: "开标时间",
  bid_opening_location: "开标地点",
  submission_method: "递交方式",
  submission_address: "递交地点",
  implementation_schedule: "实施工期/交付期",
  key_milestones: "关键里程碑",
};

// 4. 投标人资格 (bidder_qualification)
const BIDDER_QUALIFICATION_LABELS: Record<string, string> = {
  general_requirements: "一般资格要求",
  special_requirements: "特殊资格要求",
  qualification_items: "资格条款清单",
  must_provide_documents: "必须提供的证明文件",
  req_type: "要求类型",
  requirement: "具体要求",
  is_mandatory: "是否强制",
};

// 5. 评审与评分 (evaluation_and_scoring)
const EVALUATION_AND_SCORING_LABELS: Record<string, string> = {
  evaluation_method: "评标办法",
  reject_conditions: "废标/否决条件",
  scoring_items: "评分项清单",
  price_scoring_method: "价格分计算方法",
  category: "评分类别",
  item_name: "评分项名称",
  max_score: "最高分值",
  scoring_rule: "计分规则",
  scoring_method: "计分方法",
};

// 6. 商务条款 (business_terms)
const BUSINESS_TERMS_LABELS: Record<string, string> = {
  payment_terms: "付款方式",
  delivery_terms: "交付条款",
  warranty_terms: "质保条款",
  acceptance_terms: "验收条款",
  liability_terms: "违约责任",
  clauses: "商务条款清单",
  clause_type: "条款类型",
  clause_title: "条款标题",
  content: "条款内容",
  is_non_negotiable: "是否不可变更",
};

// 7. 技术要求 (technical_requirements)
const TECHNICAL_REQUIREMENTS_LABELS: Record<string, string> = {
  technical_specifications: "技术规格总体要求",
  quality_standards: "质量标准",
  technical_parameters: "技术参数清单",
  technical_proposal_requirements: "技术方案编制要求",
  name: "参数/指标名称",
  value: "参数值/要求",
  unit: "单位",
  is_mandatory: "是否强制",
  allow_deviation: "是否允许偏离",
};

// 8. 文件编制 (document_preparation)
const DOCUMENT_PREPARATION_LABELS: Record<string, string> = {
  bid_documents_structure: "投标文件结构要求",
  format_requirements: "格式要求",
  copies_required: "份数要求",
  required_forms: "必填表单清单",
  signature_and_seal: "签字盖章要求",
  form_name: "表单名称",
  form_number: "表单编号",
};

// 9. 投标保证金 (bid_security)
const BID_SECURITY_LABELS: Record<string, string> = {
  bid_bond_amount: "投标保证金金额",
  bid_bond_form: "保证金形式",
  bid_bond_deadline: "保证金递交截止时间",
  bid_bond_return: "保证金退还条件",
  performance_bond: "履约保证金要求",
  other_guarantees: "其他担保要求",
};

// 通用字段
const COMMON_LABELS: Record<string, string> = {
  evidence_chunk_ids: "证据链",
  schema_version: "Schema版本",
  created_at: "创建时间",
  updated_at: "更新时间",
};

/**
 * 合并所有字段映射
 */
export const FIELD_LABELS: Record<string, string> = {
  ...PROJECT_OVERVIEW_LABELS,
  ...SCOPE_AND_LOTS_LABELS,
  ...SCHEDULE_AND_SUBMISSION_LABELS,
  ...BIDDER_QUALIFICATION_LABELS,
  ...EVALUATION_AND_SCORING_LABELS,
  ...BUSINESS_TERMS_LABELS,
  ...TECHNICAL_REQUIREMENTS_LABELS,
  ...DOCUMENT_PREPARATION_LABELS,
  ...BID_SECURITY_LABELS,
  ...COMMON_LABELS,
};

/**
 * 获取字段的中文标签
 * @param key 英文字段名
 * @returns 中文标签，如果没有映射则返回格式化后的英文
 */
export function getFieldLabel(key: string): string {
  // 优先使用映射表
  if (FIELD_LABELS[key]) {
    return FIELD_LABELS[key];
  }
  
  // 如果没有映射，返回格式化的英文（作为fallback）
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, l => l.toUpperCase());
}

