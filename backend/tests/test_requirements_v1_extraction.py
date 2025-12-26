"""
Test Requirements V1 Extraction

测试招标要求抽取逻辑
"""
import pytest
from pathlib import Path


def test_requirements_spec_has_queries():
    """测试 requirements spec 定义了查询"""
    from app.works.tender.extraction_specs.requirements_v1 import build_requirements_spec
    
    spec = build_requirements_spec()
    
    # 验证有查询
    assert len(spec.queries) >= 7, f"Should have at least 7 queries, got {len(spec.queries)}"
    
    # 验证关键维度的query都存在
    expected_keys = ["qualification", "technical", "business", "price", "evaluation"]
    for key in expected_keys:
        assert key in spec.queries, f"Missing query key: {key}"


def test_requirements_spec_prompt_loaded():
    """测试 requirements prompt 文件被正确加载"""
    from app.works.tender.extraction_specs.requirements_v1 import build_requirements_spec
    
    spec = build_requirements_spec()
    
    # 验证prompt不为空
    assert len(spec.prompt) > 1000, "Prompt should not be empty"
    
    # 验证prompt包含关键词
    assert "requirements" in spec.prompt.lower()
    assert "requirement_id" in spec.prompt
    assert "dimension" in spec.prompt
    assert "req_type" in spec.prompt


def test_requirements_prompt_file_exists():
    """测试 requirements_v1.md 文件存在"""
    prompt_file = Path(__file__).parent.parent / "app" / "works" / "tender" / "prompts" / "requirements_v1.md"
    assert prompt_file.exists(), f"Prompt file not found: {prompt_file}"
    
    # 检查文件内容
    content = prompt_file.read_text(encoding="utf-8")
    assert len(content) > 2000, "Prompt file should not be empty"
    
    # 检查包含必要的字段说明
    assert "requirement_id" in content
    assert "dimension" in content
    assert "req_type" in content
    assert "requirement_text" in content
    assert "is_hard" in content
    assert "allow_deviation" in content
    assert "value_schema_json" in content
    assert "evidence_chunk_ids" in content


def test_requirements_spec_query_coverage():
    """测试每个查询都有足够的关键词"""
    from app.works.tender.extraction_specs.requirements_v1 import build_requirements_spec
    
    spec = build_requirements_spec()
    
    # 每个查询应该有多个关键词
    for key, query in spec.queries.items():
        words = query.split()
        assert len(words) >= 3, f"Query {key} should have at least 3 keywords, got {len(words)}"


def test_requirements_dimensions_in_prompt():
    """测试 prompt 中定义了所有维度"""
    prompt_file = Path(__file__).parent.parent / "app" / "works" / "tender" / "prompts" / "requirements_v1.md"
    content = prompt_file.read_text(encoding="utf-8")
    
    # 验证7个维度都在prompt中
    expected_dimensions = [
        "qualification",
        "technical",
        "business",
        "price",
        "doc_structure",
        "schedule_quality",
        "other"
    ]
    
    for dim in expected_dimensions:
        assert dim in content, f"Dimension {dim} not found in prompt"


def test_requirements_types_in_prompt():
    """测试 prompt 中定义了所有要求类型"""
    prompt_file = Path(__file__).parent.parent / "app" / "works" / "tender" / "prompts" / "requirements_v1.md"
    content = prompt_file.read_text(encoding="utf-8")
    
    # 验证6种要求类型都在prompt中
    expected_types = [
        "threshold",
        "must_provide",
        "must_not_deviate",
        "scoring",
        "format",
        "other"
    ]
    
    for req_type in expected_types:
        assert req_type in content, f"Requirement type {req_type} not found in prompt"


def test_requirements_output_structure_in_prompt():
    """测试 prompt 中定义了输出结构"""
    prompt_file = Path(__file__).parent.parent / "app" / "works" / "tender" / "prompts" / "requirements_v1.md"
    content = prompt_file.read_text(encoding="utf-8")
    
    # 验证输出结构说明存在
    assert '"requirements":' in content
    assert '"requirement_id":' in content
    assert '"dimension":' in content
    assert '"req_type":' in content
    assert '"requirement_text":' in content
    assert '"is_hard":' in content
    assert '"allow_deviation":' in content
    assert '"value_schema_json":' in content
    assert '"evidence_chunk_ids":' in content


def test_requirements_spec_topk_reasonable():
    """测试 requirements 的 topk 参数合理"""
    from app.works.tender.extraction_specs.requirements_v1 import build_requirements_spec
    
    spec = build_requirements_spec()
    
    # requirements 需要足够的检索范围
    assert spec.topk_per_query >= 20, f"topk_per_query should be >= 20, got {spec.topk_per_query}"
    assert spec.topk_total >= 100, f"topk_total should be >= 100, got {spec.topk_total}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

