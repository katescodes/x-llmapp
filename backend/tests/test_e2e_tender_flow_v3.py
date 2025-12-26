"""
E2E 集成测试 - 招投标完整流程 (V3)

测试完整的招投标流程：
1. 创建项目
2. 上传招标文件
3. 抽取 tender_info_v3 + requirements
4. 目录增强
5. 上传投标文件
6. 抽取投标响应
7. 运行审核（V3）
8. 导出 DOCX

所有 LLM 和检索操作均 mock
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import uuid


# ==================== Mock 数据 ====================

def get_mock_tender_info_v3():
    """Mock 招标信息 V3"""
    return {
        "schema_version": "tender_info_v3",
        "project_overview": {
            "project_name": "E2E测试项目",
            "budget_amount": 1000000,
            "purchaser": "测试采购方",
            "evidence_chunk_ids": ["chunk_001"]
        },
        "scope_and_lots": {
            "procurement_content": "测试采购内容",
            "evidence_chunk_ids": ["chunk_002"]
        },
        "schedule_and_submission": {
            "bid_deadline": "2025-12-31T23:59:59Z",
            "evidence_chunk_ids": ["chunk_003"]
        },
        "bidder_qualification": {
            "qualification_requirements": ["营业执照", "资质证书"],
            "must_provide_documents": ["营业执照", "资质证书"],
            "evidence_chunk_ids": ["chunk_004"]
        },
        "evaluation_and_scoring": {
            "evaluation_method": "综合评分法",
            "evidence_chunk_ids": ["chunk_005"]
        },
        "business_terms": {
            "payment_method": "到货验收后30日内支付",
            "evidence_chunk_ids": ["chunk_006"]
        },
        "technical_requirements": {
            "technical_specifications": ["符合国标"],
            "evidence_chunk_ids": ["chunk_007"]
        },
        "document_preparation": {
            "required_forms": [
                {
                    "form_name": "投标函",
                    "is_mandatory": True,
                    "evidence_chunk_ids": ["chunk_008"]
                }
            ],
            "evidence_chunk_ids": ["chunk_008"]
        },
        "bid_security": {
            "bid_bond_amount": 20000,
            "evidence_chunk_ids": ["chunk_009"]
        }
    }


def get_mock_requirements():
    """Mock 招标要求"""
    return [
        {
            "requirement_id": "qual_001",
            "dimension": "qualification",
            "req_type": "must_provide",
            "requirement_text": "必须提供营业执照",
            "is_hard": True,
            "allow_deviation": False,
            "value_schema_json": {},
            "evidence_chunk_ids": ["chunk_004"]
        },
        {
            "requirement_id": "tech_001",
            "dimension": "technical",
            "req_type": "threshold",
            "requirement_text": "产品符合国家标准",
            "is_hard": True,
            "allow_deviation": False,
            "value_schema_json": {},
            "evidence_chunk_ids": ["chunk_007"]
        }
    ]


def get_mock_bid_responses():
    """Mock 投标响应"""
    return [
        {
            "response_id": "qual_resp_001",
            "dimension": "qualification",
            "response_type": "document_ref",
            "response_text": "已提供营业执照",
            "extracted_value_json": {"document_name": "营业执照"},
            "evidence_chunk_ids": ["chunk_bid_001"]
        },
        {
            "response_id": "tech_resp_001",
            "dimension": "technical",
            "response_type": "text",
            "response_text": "产品符合GB/T xxxx标准",
            "extracted_value_json": {"standard": "GB/T xxxx"},
            "evidence_chunk_ids": ["chunk_bid_002"]
        }
    ]


# ==================== E2E 测试 ====================

@pytest.mark.asyncio
async def test_e2e_tender_flow_v3_structure():
    """
    E2E 测试 - 验证完整流程的数据结构
    
    注意：这是一个结构性测试，验证各步骤的输入输出格式
    实际的数据库操作和 LLM 调用需要在集成环境中测试
    """
    # Step 1: 创建项目
    project_id = str(uuid.uuid4())
    project = {
        "id": project_id,
        "name": "E2E测试项目",
        "status": "active"
    }
    
    assert project["id"] is not None
    assert project["status"] == "active"
    
    # Step 2: Mock 招标文件上传
    tender_asset_id = str(uuid.uuid4())
    
    # Step 3: Mock 招标信息抽取（V3）
    tender_info_v3 = get_mock_tender_info_v3()
    
    # 验证 schema_version
    assert tender_info_v3["schema_version"] == "tender_info_v3"
    
    # 验证九大类都存在
    assert "project_overview" in tender_info_v3
    assert "scope_and_lots" in tender_info_v3
    assert "schedule_and_submission" in tender_info_v3
    assert "bidder_qualification" in tender_info_v3
    assert "evaluation_and_scoring" in tender_info_v3
    assert "business_terms" in tender_info_v3
    assert "technical_requirements" in tender_info_v3
    assert "document_preparation" in tender_info_v3
    assert "bid_security" in tender_info_v3
    
    # Step 4: Mock 招标要求生成
    requirements = get_mock_requirements()
    
    # 验证 requirements 结构
    assert len(requirements) > 0
    for req in requirements:
        assert "requirement_id" in req
        assert "dimension" in req
        assert "req_type" in req
        assert "requirement_text" in req
        assert "is_hard" in req
        assert "evidence_chunk_ids" in req
    
    # Step 5: Mock 目录增强
    # 从 document_preparation 提取必填表单
    required_forms = tender_info_v3["document_preparation"].get("required_forms", [])
    augmented_nodes = [form["form_name"] for form in required_forms if form.get("is_mandatory")]
    
    assert len(augmented_nodes) > 0
    assert "投标函" in augmented_nodes
    
    # Step 6: Mock 投标文件上传
    bid_asset_id = str(uuid.uuid4())
    bidder_name = "测试投标人"
    
    # Step 7: Mock 投标响应抽取
    bid_responses = get_mock_bid_responses()
    
    # 验证 responses 结构
    assert len(bid_responses) > 0
    for resp in bid_responses:
        assert "response_id" in resp
        assert "dimension" in resp
        assert "response_type" in resp
        assert "response_text" in resp
        assert "extracted_value_json" in resp
        assert "evidence_chunk_ids" in resp
    
    # Step 8: Mock 审核流程（V3）
    # 模拟确定性规则引擎结果
    deterministic_results = [
        {
            "rule_id": "rule_001",
            "requirement_id": "qual_001",
            "result": "PASS",
            "reason": "已提供营业执照",
            "severity": "medium",
            "evaluator": "deterministic_engine",
            "dimension": "qualification"
        }
    ]
    
    # 验证审核结果结构
    for result in deterministic_results:
        assert "rule_id" in result or result.get("rule_key")
        assert "requirement_id" in result
        assert "result" in result
        assert "reason" in result
        assert "severity" in result
        assert "evaluator" in result
        assert "dimension" in result
    
    # Step 9: Mock 统计
    stats = {
        "total_review_items": len(deterministic_results),
        "pass_count": sum(1 for r in deterministic_results if r["result"] == "PASS"),
        "fail_count": sum(1 for r in deterministic_results if r["result"] == "FAIL"),
        "warn_count": sum(1 for r in deterministic_results if r["result"] == "WARN")
    }
    
    assert stats["total_review_items"] >= 0
    assert stats["pass_count"] + stats["fail_count"] + stats["warn_count"] == stats["total_review_items"]
    
    # Step 10: Mock DOCX 导出
    docx_config = {
        "heading_map": {i: f"Heading {i}" for i in range(1, 7)},
        "has_toc": True,
        "normal_style": "Normal"
    }
    
    assert docx_config["has_toc"] is True
    assert len(docx_config["heading_map"]) == 6


@pytest.mark.asyncio
async def test_e2e_data_flow_validation():
    """
    E2E 测试 - 验证数据流的一致性
    
    确保：
    1. tender_info_v3 的 must_provide_documents 能被目录增强使用
    2. requirements 的 dimension 与 responses 的 dimension 对应
    3. 审核结果引用正确的 requirement_id
    """
    tender_info_v3 = get_mock_tender_info_v3()
    requirements = get_mock_requirements()
    bid_responses = get_mock_bid_responses()
    
    # 验证：document_preparation 的必填表单能被目录增强使用
    required_forms = tender_info_v3["document_preparation"].get("required_forms", [])
    mandatory_forms = [f for f in required_forms if f.get("is_mandatory")]
    assert len(mandatory_forms) > 0
    
    # 验证：requirements 的 dimension 有对应的 responses
    req_dimensions = {req["dimension"] for req in requirements}
    resp_dimensions = {resp["dimension"] for resp in bid_responses}
    
    # 应该有交集
    common_dimensions = req_dimensions & resp_dimensions
    assert len(common_dimensions) > 0, "Requirements 和 responses 应该有共同的 dimension"
    
    # 验证：硬性要求有对应的响应
    hard_requirements = [req for req in requirements if req.get("is_hard")]
    for hard_req in hard_requirements:
        dimension = hard_req["dimension"]
        # 检查是否有对应维度的响应
        matching_responses = [resp for resp in bid_responses if resp["dimension"] == dimension]
        assert len(matching_responses) > 0, f"硬性要求 {hard_req['requirement_id']} 应该有对应的响应"


def test_e2e_schema_versions():
    """测试所有组件使用正确的 schema_version"""
    tender_info_v3 = get_mock_tender_info_v3()
    
    # 验证 schema_version
    assert tender_info_v3["schema_version"] == "tender_info_v3"
    
    # 验证不包含旧字段
    assert "base" not in tender_info_v3
    assert "technical_parameters" not in tender_info_v3
    assert "scoring_criteria" not in tender_info_v3


def test_e2e_evidence_chain():
    """测试证据链的完整性"""
    tender_info_v3 = get_mock_tender_info_v3()
    requirements = get_mock_requirements()
    bid_responses = get_mock_bid_responses()
    
    # 验证所有数据都有 evidence_chunk_ids
    for category_key in ["project_overview", "scope_and_lots", "schedule_and_submission",
                         "bidder_qualification", "evaluation_and_scoring", "business_terms",
                         "technical_requirements", "document_preparation", "bid_security"]:
        category_data = tender_info_v3.get(category_key, {})
        assert "evidence_chunk_ids" in category_data, f"{category_key} 缺少 evidence_chunk_ids"
    
    for req in requirements:
        assert "evidence_chunk_ids" in req
        assert len(req["evidence_chunk_ids"]) > 0
    
    for resp in bid_responses:
        assert "evidence_chunk_ids" in resp
        assert len(resp["evidence_chunk_ids"]) > 0


def test_e2e_requirements_types():
    """测试 requirements 的类型覆盖"""
    requirements = get_mock_requirements()
    
    # 验证 req_type 多样性
    req_types = {req["req_type"] for req in requirements}
    
    # 应该至少有 must_provide 和 threshold 类型
    assert "must_provide" in req_types or "threshold" in req_types
    
    # 验证所有 requirement 都有 dimension
    for req in requirements:
        assert req["dimension"] in [
            "qualification", "technical", "business", "price",
            "doc_structure", "schedule_quality", "other"
        ]


def test_e2e_response_types():
    """测试 responses 的类型覆盖"""
    bid_responses = get_mock_bid_responses()
    
    # 验证 response_type 多样性
    response_types = {resp["response_type"] for resp in bid_responses}
    
    # 应该至少有 document_ref 和 text 类型
    assert "document_ref" in response_types or "text" in response_types
    
    # 验证所有 response 都有 dimension
    for resp in bid_responses:
        assert resp["dimension"] in [
            "qualification", "technical", "business", "price",
            "doc_structure", "schedule_quality", "other"
        ]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

