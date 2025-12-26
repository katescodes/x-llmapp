"""
Test Tender Info V3 Schema and Validators

测试九大类招标信息 schema 与校验器
"""
import pytest
from app.works.tender.schemas.tender_info_v3 import (
    TenderInfoV3,
    TENDER_INFO_V3_KEYS,
    SCHEMA_VERSION_V3,
)
from app.works.tender.schemas.validators import (
    validate_tender_info_v3,
    validate_tender_info_v3_partial,
    is_valid_tender_info_v3,
    TenderInfoV3ValidationError,
)


def test_tender_info_v3_keys():
    """测试九大类 key 常量定义"""
    assert len(TENDER_INFO_V3_KEYS) == 9
    assert "project_overview" in TENDER_INFO_V3_KEYS
    assert "scope_and_lots" in TENDER_INFO_V3_KEYS
    assert "schedule_and_submission" in TENDER_INFO_V3_KEYS
    assert "bidder_qualification" in TENDER_INFO_V3_KEYS
    assert "evaluation_and_scoring" in TENDER_INFO_V3_KEYS
    assert "business_terms" in TENDER_INFO_V3_KEYS
    assert "technical_requirements" in TENDER_INFO_V3_KEYS
    assert "document_preparation" in TENDER_INFO_V3_KEYS
    assert "bid_security" in TENDER_INFO_V3_KEYS


def test_schema_version_constant():
    """测试 schema version 常量"""
    assert SCHEMA_VERSION_V3 == "tender_info_v3"


def test_minimal_valid_json_passes_validation():
    """测试最小有效 JSON（每段空值 + schema_version）通过校验"""
    minimal_json = {
        "schema_version": "tender_info_v3",
        "project_overview": {},
        "scope_and_lots": {},
        "schedule_and_submission": {},
        "bidder_qualification": {},
        "evaluation_and_scoring": {},
        "business_terms": {},
        "technical_requirements": {},
        "document_preparation": {},
        "bid_security": {},
    }
    
    # 应该不抛异常
    validate_tender_info_v3(minimal_json)
    
    # 应该返回 True
    assert is_valid_tender_info_v3(minimal_json)
    
    # 应该能创建 Pydantic 模型
    model = TenderInfoV3(**minimal_json)
    assert model.schema_version == "tender_info_v3"


def test_missing_schema_version_fails():
    """测试缺少 schema_version 应该失败"""
    invalid_json = {
        "project_overview": {},
        "scope_and_lots": {},
        "schedule_and_submission": {},
        "bidder_qualification": {},
        "evaluation_and_scoring": {},
        "business_terms": {},
        "technical_requirements": {},
        "document_preparation": {},
        "bid_security": {},
    }
    
    with pytest.raises(TenderInfoV3ValidationError, match="Missing required field: schema_version"):
        validate_tender_info_v3(invalid_json)
    
    assert not is_valid_tender_info_v3(invalid_json)


def test_wrong_schema_version_fails():
    """测试错误的 schema_version 应该失败"""
    invalid_json = {
        "schema_version": "tender_info_v2",  # 错误的版本
        "project_overview": {},
        "scope_and_lots": {},
        "schedule_and_submission": {},
        "bidder_qualification": {},
        "evaluation_and_scoring": {},
        "business_terms": {},
        "technical_requirements": {},
        "document_preparation": {},
        "bid_security": {},
    }
    
    with pytest.raises(TenderInfoV3ValidationError, match="Invalid schema_version"):
        validate_tender_info_v3(invalid_json)
    
    assert not is_valid_tender_info_v3(invalid_json)


def test_missing_required_key_fails():
    """测试缺少必需 key 应该失败"""
    invalid_json = {
        "schema_version": "tender_info_v3",
        "project_overview": {},
        "scope_and_lots": {},
        # 缺少 schedule_and_submission
        "bidder_qualification": {},
        "evaluation_and_scoring": {},
        "business_terms": {},
        "technical_requirements": {},
        "document_preparation": {},
        "bid_security": {},
    }
    
    with pytest.raises(TenderInfoV3ValidationError, match="Missing required category: schedule_and_submission"):
        validate_tender_info_v3(invalid_json)
    
    assert not is_valid_tender_info_v3(invalid_json)


def test_valid_json_with_data():
    """测试带有实际数据的有效 JSON"""
    valid_json = {
        "schema_version": "tender_info_v3",
        "project_overview": {
            "project_name": "测试项目",
            "project_number": "TEST-2025-001",
            "owner_name": "测试采购单位",
            "budget": "100万元",
            "evidence_chunk_ids": ["chunk_1", "chunk_2"],
        },
        "scope_and_lots": {
            "project_scope": "采购办公设备",
            "lots": [
                {
                    "lot_number": "1",
                    "lot_name": "第一标段",
                    "scope": "计算机设备",
                    "budget": "50万元",
                    "evidence_chunk_ids": ["chunk_3"],
                }
            ],
            "evidence_chunk_ids": ["chunk_4"],
        },
        "schedule_and_submission": {
            "bid_deadline": "2025-01-15 09:00:00",
            "bid_opening_time": "2025-01-15 09:30:00",
            "implementation_schedule": "60天",
            "evidence_chunk_ids": [],
        },
        "bidder_qualification": {
            "general_requirements": "具有独立法人资格",
            "qualification_items": [
                {
                    "req_type": "资质",
                    "requirement": "具有有效营业执照",
                    "is_mandatory": True,
                    "evidence_chunk_ids": ["chunk_5"],
                }
            ],
            "must_provide_documents": ["营业执照", "资质证书"],
            "evidence_chunk_ids": [],
        },
        "evaluation_and_scoring": {
            "evaluation_method": "综合评分法",
            "scoring_items": [
                {
                    "category": "技术",
                    "item_name": "技术方案",
                    "max_score": "30",
                    "scoring_rule": "按方案质量打分",
                    "evidence_chunk_ids": ["chunk_6"],
                }
            ],
            "evidence_chunk_ids": [],
        },
        "business_terms": {
            "payment_terms": "分期付款",
            "clauses": [],
            "evidence_chunk_ids": [],
        },
        "technical_requirements": {
            "technical_specifications": "按国家标准执行",
            "technical_parameters": [
                {
                    "name": "CPU",
                    "value": "Intel i5 或以上",
                    "category": "硬件",
                    "is_mandatory": True,
                    "allow_deviation": False,
                    "evidence_chunk_ids": ["chunk_7"],
                }
            ],
            "evidence_chunk_ids": [],
        },
        "document_preparation": {
            "bid_documents_structure": "按招标文件要求",
            "required_forms": [
                {
                    "form_name": "投标报价表",
                    "form_number": "F-01",
                    "is_mandatory": True,
                    "evidence_chunk_ids": [],
                }
            ],
            "evidence_chunk_ids": [],
        },
        "bid_security": {
            "bid_bond_amount": "2万元",
            "bid_bond_form": "银行保函或转账",
            "evidence_chunk_ids": [],
        },
    }
    
    # 应该通过校验
    validate_tender_info_v3(valid_json)
    assert is_valid_tender_info_v3(valid_json)
    
    # 应该能创建 Pydantic 模型
    model = TenderInfoV3(**valid_json)
    assert model.project_overview.project_name == "测试项目"
    assert len(model.scope_and_lots.lots) == 1
    assert len(model.bidder_qualification.qualification_items) == 1
    assert len(model.evaluation_and_scoring.scoring_items) == 1
    assert len(model.technical_requirements.technical_parameters) == 1
    assert len(model.document_preparation.required_forms) == 1


def test_partial_validation_allows_missing_keys():
    """测试部分校验允许缺少某些 key"""
    partial_json = {
        "schema_version": "tender_info_v3",
        "project_overview": {
            "project_name": "部分项目",
        },
        "technical_requirements": {
            "technical_specifications": "部分技术要求",
        },
    }
    
    # 完整校验应该失败（缺少必需的 key）
    with pytest.raises(TenderInfoV3ValidationError):
        validate_tender_info_v3(partial_json)
    
    # 部分校验应该通过
    validate_tender_info_v3_partial(partial_json)


def test_unknown_key_rejected():
    """测试未知的 key 应该被拒绝"""
    invalid_json = {
        "schema_version": "tender_info_v3",
        "project_overview": {},
        "unknown_category": {},  # 未知的 key
    }
    
    with pytest.raises(TenderInfoV3ValidationError, match="Unknown category key: unknown_category"):
        validate_tender_info_v3_partial(invalid_json)


def test_pydantic_model_creation():
    """测试 Pydantic 模型创建"""
    # 测试默认值
    model = TenderInfoV3()
    assert model.schema_version == "tender_info_v3"
    assert model.project_overview is not None
    assert model.project_overview.project_name is None
    
    # 测试 to_dict_exclude_none
    data_dict = model.to_dict_exclude_none()
    assert "schema_version" in data_dict
    assert data_dict["schema_version"] == "tender_info_v3"


def test_evidence_chunk_ids_default_to_empty_list():
    """测试 evidence_chunk_ids 默认为空列表"""
    model = TenderInfoV3()
    assert isinstance(model.project_overview.evidence_chunk_ids, list)
    assert len(model.project_overview.evidence_chunk_ids) == 0
    assert isinstance(model.technical_requirements.evidence_chunk_ids, list)
    assert len(model.technical_requirements.evidence_chunk_ids) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

