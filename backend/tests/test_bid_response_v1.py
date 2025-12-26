"""
测试投标响应要素抽取
"""
import pytest
from pathlib import Path


def test_bid_response_spec_exists():
    """测试 bid_response_v1.py 存在"""
    spec_file = Path(__file__).parent.parent / "app" / "works" / "tender" / "extraction_specs" / "bid_response_v1.py"
    assert spec_file.exists(), f"bid_response_v1.py 不存在: {spec_file}"


def test_bid_response_prompt_exists():
    """测试 bid_response_v1.md 存在"""
    prompt_file = Path(__file__).parent.parent / "app" / "works" / "tender" / "prompts" / "bid_response_v1.md"
    assert prompt_file.exists(), f"bid_response_v1.md 不存在: {prompt_file}"


def test_bid_response_spec_queries():
    """测试 ExtractionSpec 有正确的查询维度"""
    import asyncio
    from app.works.tender.extraction_specs.bid_response_v1 import build_bid_response_spec_async
    
    spec = asyncio.run(build_bid_response_spec_async(pool=None))
    
    assert spec.queries is not None
    assert len(spec.queries) == 7  # 7个维度
    
    # 验证关键维度存在
    assert "qualification" in spec.queries
    assert "technical" in spec.queries
    assert "business" in spec.queries
    assert "price" in spec.queries
    assert "doc_structure" in spec.queries
    assert "schedule_quality" in spec.queries
    assert "other" in spec.queries


def test_bid_response_spec_doc_types():
    """测试 ExtractionSpec 只检索投标文件"""
    import asyncio
    from app.works.tender.extraction_specs.bid_response_v1 import build_bid_response_spec_async
    
    spec = asyncio.run(build_bid_response_spec_async(pool=None))
    
    assert spec.doc_types == ["bid"]


def test_bid_response_prompt_content():
    """测试 bid_response_v1.md 包含关键内容"""
    prompt_file = Path(__file__).parent.parent / "app" / "works" / "tender" / "prompts" / "bid_response_v1.md"
    content = prompt_file.read_text(encoding="utf-8")
    
    # 验证关键字段
    assert "schema_version" in content
    assert "bid_response_v1" in content
    assert "bidder_name" in content
    assert "responses" in content
    assert "response_id" in content
    assert "dimension" in content
    assert "response_type" in content
    assert "response_text" in content
    assert "extracted_value_json" in content
    assert "evidence_chunk_ids" in content
    
    # 验证维度
    assert "qualification" in content
    assert "technical" in content
    assert "business" in content
    assert "price" in content
    assert "doc_structure" in content
    assert "schedule_quality" in content
    
    # 验证响应类型
    assert "text" in content
    assert "value" in content
    assert "document_ref" in content
    assert "compliance" in content


def test_bid_response_service_exists():
    """测试 BidResponseService 存在"""
    # 为了避免 psycopg_pool 依赖，我们只检查文件是否存在
    service_file = Path(__file__).parent.parent / "app" / "works" / "tender" / "bid_response_service.py"
    assert service_file.exists(), f"bid_response_service.py 不存在: {service_file}"
    
    # 检查文件内容
    content = service_file.read_text(encoding="utf-8")
    assert "class BidResponseService" in content
    assert "extract_bid_response_v1" in content
    assert "extract_all_bidders_responses" in content


def test_bid_response_service_extract_structure():
    """测试 BidResponseService.extract_bid_response_v1 的方法签名"""
    # 为了避免 psycopg_pool 依赖，我们只检查方法签名
    service_file = Path(__file__).parent.parent / "app" / "works" / "tender" / "bid_response_service.py"
    content = service_file.read_text(encoding="utf-8")
    
    # 验证关键方法存在
    assert "async def extract_bid_response_v1" in content
    assert "project_id" in content
    assert "bidder_name" in content
    assert "model_id" in content
    
    # 验证落库逻辑
    assert "tender_bid_response_items" in content
    assert "INSERT INTO" in content
    
    # 验证返回结构
    assert '"bidder_name"' in content
    assert '"responses"' in content
    assert '"added_count"' in content


def test_bid_response_spec_topk():
    """测试 ExtractionSpec 的 topk 参数合理"""
    import asyncio
    from app.works.tender.extraction_specs.bid_response_v1 import build_bid_response_spec_async
    
    spec = asyncio.run(build_bid_response_spec_async(pool=None))
    
    # topk 应该大于 0
    assert spec.topk_per_query > 0
    assert spec.topk_total > 0
    
    # topk_total 应该 >= topk_per_query * 查询数量
    assert spec.topk_total >= spec.topk_per_query * len(spec.queries)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

