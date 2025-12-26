"""
Test Project Info V3 Extraction

测试九大类招标信息抽取逻辑
"""
import pytest


def test_extraction_spec_has_9_queries():
    """测试extraction spec定义了9个查询"""
    from app.works.tender.extraction_specs.project_info_v2 import build_project_info_spec
    
    spec = build_project_info_spec()
    
    # 验证有9个查询
    assert len(spec.queries) == 9
    
    # 验证九大类的key都存在
    expected_keys = [
        "project_overview", "scope_and_lots", "schedule_and_submission",
        "bidder_qualification", "evaluation_and_scoring", "business_terms",
        "technical_requirements", "document_preparation", "bid_security"
    ]
    for key in expected_keys:
        assert key in spec.queries, f"Missing query key: {key}"
    
    # 验证prompt来自v3文件（检查关键词）
    assert len(spec.prompt) > 100  # prompt应该不为空
    assert "tender_info_v3" in spec.prompt or "九大类" in spec.prompt


def test_extraction_spec_topk_increased_for_9_stages():
    """测试九大类的topk参数增加了"""
    from app.works.tender.extraction_specs.project_info_v2 import build_project_info_spec
    
    spec = build_project_info_spec()
    
    # 九大类需要更大的检索范围
    assert spec.topk_per_query >= 30, f"topk_per_query should be >= 30, got {spec.topk_per_query}"
    assert spec.topk_total >= 150, f"topk_total should be >= 150, got {spec.topk_total}"


def test_extraction_spec_query_coverage():
    """测试每个查询都有足够的关键词"""
    from app.works.tender.extraction_specs.project_info_v2 import build_project_info_spec
    
    spec = build_project_info_spec()
    
    # 每个查询应该有多个关键词
    for key, query in spec.queries.items():
        words = query.split()
        assert len(words) >= 3, f"Query {key} should have at least 3 keywords, got {len(words)}"


def test_prompt_file_v3_exists():
    """测试 v3 prompt 文件存在"""
    from pathlib import Path
    
    prompt_file = Path(__file__).parent.parent / "app" / "works" / "tender" / "prompts" / "project_info_v3.md"
    assert prompt_file.exists(), f"Prompt file not found: {prompt_file}"
    
    # 检查文件内容
    content = prompt_file.read_text(encoding="utf-8")
    assert len(content) > 1000, "Prompt file should not be empty"
    
    # 检查包含九大类
    assert "project_overview" in content
    assert "scope_and_lots" in content
    assert "schedule_and_submission" in content
    assert "bidder_qualification" in content
    assert "evaluation_and_scoring" in content
    assert "business_terms" in content
    assert "technical_requirements" in content
    assert "document_preparation" in content
    assert "bid_security" in content


def test_schema_v3_integration_with_extraction():
    """测试 schema v3 与 extraction spec 的集成"""
    from app.works.tender.extraction_specs.project_info_v2 import build_project_info_spec
    from app.works.tender.schemas.tender_info_v3 import TENDER_INFO_V3_KEYS
    
    spec = build_project_info_spec()
    
    # extraction spec 的 queries keys 应该与 schema v3 的 keys 一致
    assert set(spec.queries.keys()) == set(TENDER_INFO_V3_KEYS), \
        f"Queries keys {set(spec.queries.keys())} do not match schema keys {set(TENDER_INFO_V3_KEYS)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

