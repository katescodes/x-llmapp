"""
Tender Info V3 Schema - 九大类招标信息结构

这是新版本的招标信息分类体系，取代旧的四类结构(base/technical_parameters/business_terms/scoring_criteria)

九大类：
1. project_overview - 项目概览
2. scope_and_lots - 范围与标段
3. schedule_and_submission - 进度与递交
4. bidder_qualification - 投标人资格
5. evaluation_and_scoring - 评审与评分
6. business_terms - 商务条款
7. technical_requirements - 技术要求
8. document_preparation - 文件编制
9. bid_security - 保证金与担保
"""
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


# ============ 1. 项目概览 ============
class ProjectOverview(BaseModel):
    """项目概览信息"""
    project_name: Optional[str] = Field(None, description="项目名称")
    project_number: Optional[str] = Field(None, description="项目编号/招标编号")
    owner_name: Optional[str] = Field(None, description="采购人/业主/招标人")
    agency_name: Optional[str] = Field(None, description="代理机构")
    contact_person: Optional[str] = Field(None, description="联系人")
    contact_phone: Optional[str] = Field(None, description="联系电话")
    project_location: Optional[str] = Field(None, description="项目地点")
    fund_source: Optional[str] = Field(None, description="资金来源")
    procurement_method: Optional[str] = Field(None, description="采购方式")
    budget: Optional[str] = Field(None, description="预算金额")
    max_price: Optional[str] = Field(None, description="招标控制价/最高限价")
    
    # 证据
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="证据chunk IDs")
    
    # 允许额外字段
    class Config:
        extra = "allow"


# ============ 2. 范围与标段 ============
class LotInfo(BaseModel):
    """标段信息"""
    lot_number: Optional[str] = Field(None, description="标段编号")
    lot_name: Optional[str] = Field(None, description="标段名称")
    scope: Optional[str] = Field(None, description="标段范围")
    budget: Optional[str] = Field(None, description="标段预算")
    evidence_chunk_ids: List[str] = Field(default_factory=list)


class ScopeAndLots(BaseModel):
    """范围与标段"""
    project_scope: Optional[str] = Field(None, description="项目范围/采购内容")
    lot_division: Optional[str] = Field(None, description="标段划分说明")
    lots: List[LotInfo] = Field(default_factory=list, description="各标段详情")
    
    evidence_chunk_ids: List[str] = Field(default_factory=list)
    
    class Config:
        extra = "allow"


# ============ 3. 进度与递交 ============
class ScheduleAndSubmission(BaseModel):
    """进度与递交要求"""
    bid_deadline: Optional[str] = Field(None, description="投标截止时间")
    bid_opening_time: Optional[str] = Field(None, description="开标时间")
    bid_opening_location: Optional[str] = Field(None, description="开标地点")
    submission_method: Optional[str] = Field(None, description="递交方式(线上/线下)")
    submission_address: Optional[str] = Field(None, description="递交地点")
    implementation_schedule: Optional[str] = Field(None, description="实施工期/交付期")
    key_milestones: Optional[str] = Field(None, description="关键里程碑")
    
    evidence_chunk_ids: List[str] = Field(default_factory=list)
    
    class Config:
        extra = "allow"


# ============ 4. 投标人资格 ============
class QualificationItem(BaseModel):
    """资格条款"""
    req_type: Optional[str] = Field(None, description="要求类型(资质/业绩/人员/财务/其他)")
    requirement: Optional[str] = Field(None, description="具体要求")
    is_mandatory: bool = Field(True, description="是否强制")
    evidence_chunk_ids: List[str] = Field(default_factory=list)


class BidderQualification(BaseModel):
    """投标人资格要求"""
    general_requirements: Optional[str] = Field(None, description="一般资格要求")
    special_requirements: Optional[str] = Field(None, description="特殊资格要求")
    qualification_items: List[QualificationItem] = Field(default_factory=list, description="资格条款清单")
    must_provide_documents: List[str] = Field(default_factory=list, description="必须提供的资格证明文件")
    
    evidence_chunk_ids: List[str] = Field(default_factory=list)
    
    class Config:
        extra = "allow"


# ============ 5. 评审与评分 ============
class ScoringItem(BaseModel):
    """评分项"""
    category: Optional[str] = Field(None, description="评分类别(技术/商务/价格/其他)")
    item_name: Optional[str] = Field(None, description="评分项名称")
    max_score: Optional[str] = Field(None, description="最高分值")
    scoring_rule: Optional[str] = Field(None, description="计分规则")
    scoring_method: Optional[str] = Field(None, description="计分方法")
    evidence_chunk_ids: List[str] = Field(default_factory=list)


class EvaluationAndScoring(BaseModel):
    """评审与评分"""
    evaluation_method: Optional[str] = Field(None, description="评标办法(综合评分法/最低价法等)")
    reject_conditions: Optional[str] = Field(None, description="废标/否决条件")
    scoring_items: List[ScoringItem] = Field(default_factory=list, description="评分项清单")
    price_scoring_method: Optional[str] = Field(None, description="价格分计算方法")
    
    evidence_chunk_ids: List[str] = Field(default_factory=list)
    
    class Config:
        extra = "allow"


# ============ 6. 商务条款 ============
class BusinessClause(BaseModel):
    """商务条款"""
    clause_type: Optional[str] = Field(None, description="条款类型(付款/交付/质保/验收/违约等)")
    clause_title: Optional[str] = Field(None, description="条款标题")
    content: Optional[str] = Field(None, description="条款内容")
    is_non_negotiable: bool = Field(False, description="是否不可变更")
    evidence_chunk_ids: List[str] = Field(default_factory=list)


class BusinessTerms(BaseModel):
    """商务条款"""
    payment_terms: Optional[str] = Field(None, description="付款方式")
    delivery_terms: Optional[str] = Field(None, description="交付条款")
    warranty_terms: Optional[str] = Field(None, description="质保条款")
    acceptance_terms: Optional[str] = Field(None, description="验收条款")
    liability_terms: Optional[str] = Field(None, description="违约责任")
    clauses: List[BusinessClause] = Field(default_factory=list, description="商务条款清单")
    
    evidence_chunk_ids: List[str] = Field(default_factory=list)
    
    class Config:
        extra = "allow"


# ============ 7. 技术要求 ============
class TechnicalParameter(BaseModel):
    """技术参数"""
    name: Optional[str] = Field(None, description="参数/指标名称")
    value: Optional[str] = Field(None, description="参数值/要求")
    category: Optional[str] = Field(None, description="参数类别")
    unit: Optional[str] = Field(None, description="单位")
    is_mandatory: bool = Field(True, description="是否强制")
    allow_deviation: bool = Field(False, description="是否允许偏离")
    evidence_chunk_ids: List[str] = Field(default_factory=list)


class TechnicalRequirements(BaseModel):
    """技术要求"""
    technical_specifications: Optional[str] = Field(None, description="技术规格总体要求")
    quality_standards: Optional[str] = Field(None, description="质量标准")
    technical_parameters: List[TechnicalParameter] = Field(default_factory=list, description="技术参数清单")
    technical_proposal_requirements: Optional[str] = Field(None, description="技术方案编制要求")
    
    evidence_chunk_ids: List[str] = Field(default_factory=list)
    
    class Config:
        extra = "allow"


# ============ 8. 文件编制 ============
class RequiredForm(BaseModel):
    """必填表单"""
    form_name: Optional[str] = Field(None, description="表单名称")
    form_number: Optional[str] = Field(None, description="表单编号")
    is_mandatory: bool = Field(True, description="是否必填")
    evidence_chunk_ids: List[str] = Field(default_factory=list)


class DocumentPreparation(BaseModel):
    """文件编制要求"""
    bid_documents_structure: Optional[str] = Field(None, description="投标文件结构要求")
    format_requirements: Optional[str] = Field(None, description="格式要求(装订/封面/页码等)")
    copies_required: Optional[str] = Field(None, description="份数要求(正本/副本)")
    required_forms: List[RequiredForm] = Field(default_factory=list, description="必填表单清单")
    signature_and_seal: Optional[str] = Field(None, description="签字盖章要求")
    
    evidence_chunk_ids: List[str] = Field(default_factory=list)
    
    class Config:
        extra = "allow"


# ============ 9. 保证金与担保 ============
class BidSecurity(BaseModel):
    """保证金与担保"""
    bid_bond_amount: Optional[str] = Field(None, description="投标保证金金额")
    bid_bond_form: Optional[str] = Field(None, description="保证金形式(转账/保函/支票等)")
    bid_bond_deadline: Optional[str] = Field(None, description="保证金递交截止时间")
    bid_bond_return: Optional[str] = Field(None, description="保证金退还条件")
    performance_bond: Optional[str] = Field(None, description="履约保证金要求")
    other_guarantees: Optional[str] = Field(None, description="其他担保要求")
    
    evidence_chunk_ids: List[str] = Field(default_factory=list)
    
    class Config:
        extra = "allow"


# ============ 顶层结构 ============
class TenderInfoV3(BaseModel):
    """
    Tender Info V3 - 九大类招标信息
    
    这是新版本的招标信息结构，替代旧的四类结构
    """
    schema_version: Literal["tender_info_v3"] = Field("tender_info_v3", description="Schema版本标识")
    
    project_overview: ProjectOverview = Field(default_factory=ProjectOverview, description="项目概览")
    scope_and_lots: ScopeAndLots = Field(default_factory=ScopeAndLots, description="范围与标段")
    schedule_and_submission: ScheduleAndSubmission = Field(default_factory=ScheduleAndSubmission, description="进度与递交")
    bidder_qualification: BidderQualification = Field(default_factory=BidderQualification, description="投标人资格")
    evaluation_and_scoring: EvaluationAndScoring = Field(default_factory=EvaluationAndScoring, description="评审与评分")
    business_terms: BusinessTerms = Field(default_factory=BusinessTerms, description="商务条款")
    technical_requirements: TechnicalRequirements = Field(default_factory=TechnicalRequirements, description="技术要求")
    document_preparation: DocumentPreparation = Field(default_factory=DocumentPreparation, description="文件编制")
    bid_security: BidSecurity = Field(default_factory=BidSecurity, description="保证金与担保")
    
    def to_dict_exclude_none(self) -> dict:
        """导出为 dict，排除 None 值"""
        return self.model_dump(exclude_none=True, by_alias=True)
    
    class Config:
        extra = "forbid"  # 不允许额外字段，确保结构标准


# ============ 常量定义 ============
TENDER_INFO_V3_KEYS = [
    "project_overview",
    "scope_and_lots",
    "schedule_and_submission",
    "bidder_qualification",
    "evaluation_and_scoring",
    "business_terms",
    "technical_requirements",
    "document_preparation",
    "bid_security",
]

SCHEMA_VERSION_V3 = "tender_info_v3"

