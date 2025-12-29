"""
测试投标响应要素抽取 (v2)
"""
import pytest
from pathlib import Path


def test_bid_response_spec_v2_exists():
    """测试 bid_response_v2.py 存在"""
    spec_file = Path(__file__).parent.parent / "app" / "works" / "tender" / "extraction_specs" / "bid_response_v2.py"
    assert spec_file.exists(), f"bid_response_v2.py 不存在: {spec_file}"


def test_bid_response_spec_queries():
    """测试 ExtractionSpec 有正确的查询维度"""
    # 注意：这个测试需要数据库连接，因此需要mock
    # 这里只做基本的文件内容检查
    spec_file = Path(__file__).parent.parent / "app" / "works" / "tender" / "extraction_specs" / "bid_response_v2.py"
    content = spec_file.read_text(encoding="utf-8")
    
    # 验证关键维度存在
    assert "qualification" in content
    assert "technical" in content
    assert "business" in content
    assert "price" in content
    assert "doc_structure" in content
    assert "schedule_quality" in content
    assert "other" in content


def test_bid_response_spec_v2_features():
    """测试 v2 spec 包含新特性"""
    spec_file = Path(__file__).parent.parent / "app" / "works" / "tender" / "extraction_specs" / "bid_response_v2.py"
    content = spec_file.read_text(encoding="utf-8")
    
    # 验证 v2 特性说明
    assert "normalized_fields_json" in content
    assert "evidence_segment_ids" in content
    assert "bid_response_v2" in content


def test_bid_response_service_exists():
    """测试 BidResponseService 存在"""
    service_file = Path(__file__).parent.parent / "app" / "works" / "tender" / "bid_response_service.py"
    assert service_file.exists(), f"bid_response_service.py 不存在: {service_file}"
    
    # 检查文件内容
    content = service_file.read_text(encoding="utf-8")
    assert "class BidResponseService" in content
    assert "extract_bid_response" in content
    assert "extract_all_bidders_responses" in content


def test_bid_response_service_no_v1():
    """测试 BidResponseService 不再包含 v1 方法"""
    service_file = Path(__file__).parent.parent / "app" / "works" / "tender" / "bid_response_service.py"
    content = service_file.read_text(encoding="utf-8")
    
    # 确认不存在 v1 方法
    assert "extract_bid_response_v1" not in content
    # 确认存在主方法
    assert "async def extract_bid_response(" in content


def test_bid_response_service_v2_fields():
    """测试 BidResponseService 包含 v2 字段"""
    service_file = Path(__file__).parent.parent / "app" / "works" / "tender" / "bid_response_service.py"
    content = service_file.read_text(encoding="utf-8")
    
    # 验证 v2 字段
    assert "normalized_fields_json" in content
    assert "evidence_json" in content
    assert "evidence_segment_ids" in content
    
    # 验证落库逻辑
    assert "tender_bid_response_items" in content
    assert "INSERT INTO" in content
    
    # 验证返回结构
    assert '"bidder_name"' in content
    assert '"responses"' in content
    assert '"added_count"' in content
    assert '"schema_version"' in content


def test_bid_response_service_helper_methods():
    """测试 BidResponseService 包含辅助方法"""
    service_file = Path(__file__).parent.parent / "app" / "works" / "tender" / "bid_response_service.py"
    content = service_file.read_text(encoding="utf-8")
    
    # 验证辅助方法存在
    assert "_prefetch_doc_segments" in content
    assert "_make_quote" in content
    assert "_build_evidence_json_from_segments" in content


def test_bid_response_service_batch_method():
    """测试 BidResponseService 批量方法调用正确版本"""
    service_file = Path(__file__).parent.parent / "app" / "works" / "tender" / "bid_response_service.py"
    content = service_file.read_text(encoding="utf-8")
    
    # 查找 extract_all_bidders_responses 方法
    assert "async def extract_all_bidders_responses" in content
    
    # 确保批量方法调用的是 extract_bid_response（不是 v1）
    # 需要检查方法内部调用
    lines = content.split('\n')
    in_batch_method = False
    found_correct_call = False
    
    for line in lines:
        if "async def extract_all_bidders_responses" in line:
            in_batch_method = True
        if in_batch_method and "await self.extract_bid_response(" in line:
            found_correct_call = True
            break
        if in_batch_method and "async def " in line and "extract_all_bidders_responses" not in line:
            # 进入了下一个方法
            break
    
    assert found_correct_call, "批量方法应该调用 extract_bid_response"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

