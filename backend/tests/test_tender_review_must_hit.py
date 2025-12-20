"""
测试 review MUST_HIT 规则兜底
确保 ReviewV2Service 总是产出 MUST_HIT_001
"""
import pytest
from unittest.mock import Mock


def test_must_hit_rules_defined():
    """测试 MUST_HIT 规则已定义"""
    from app.works.tender.extraction_specs.review_v2 import get_must_hit_rules
    
    rules = get_must_hit_rules()
    
    # 至少有 MUST_HIT_001
    assert len(rules) >= 1
    
    rule_ids = [r["rule_id"] for r in rules]
    assert "MUST_HIT_001" in rule_ids
    
    # 验证结构
    for rule in rules:
        assert "rule_id" in rule
        assert "title" in rule
        assert "description" in rule
        assert "severity" in rule


def test_ensure_must_hit_rules_function():
    """测试 _ensure_must_hit_rules() 函数逻辑"""
    from app.works.tender.review_v2_service import ReviewV2Service
    
    # 创建一个mock service（不需要真实的pool和llm）
    mock_pool = Mock()
    mock_llm = Mock()
    service = ReviewV2Service(mock_pool, mock_llm)
    
    # 测试场景1：空列表，应该添加所有 MUST_HIT 规则
    empty_items = []
    result = service._ensure_must_hit_rules(empty_items, [], [])
    
    # 至少有 MUST_HIT_001
    rule_ids = [item.get("rule_id") for item in result]
    assert "MUST_HIT_001" in rule_ids
    
    # 测试场景2：已有 MUST_HIT_001，不应该重复添加
    existing_items = [
        {
            "rule_id": "MUST_HIT_001",
            "title": "Already exists",
            "severity": "info",
            "description": "test",
        }
    ]
    result2 = service._ensure_must_hit_rules(existing_items, [], [])
    
    # 应该只有一个 MUST_HIT_001
    must_hit_001_count = sum(1 for item in result2 if item.get("rule_id") == "MUST_HIT_001")
    assert must_hit_001_count == 1
    
    # 测试场景3：有其他规则，但没有 MUST_HIT_001，应该添加
    other_items = [
        {
            "rule_id": "CUSTOM_001",
            "title": "Custom rule",
            "severity": "warning",
            "description": "test",
        }
    ]
    result3 = service._ensure_must_hit_rules(other_items, [], [])
    
    # 应该有2个规则（CUSTOM_001 + MUST_HIT_001）
    assert len(result3) >= 2
    rule_ids = [item.get("rule_id") for item in result3]
    assert "MUST_HIT_001" in rule_ids
    assert "CUSTOM_001" in rule_ids


def test_review_spec_has_must_hit():
    """测试 review spec 包含 MUST_HIT 规则定义"""
    from app.works.tender.extraction_specs.review_v2 import build_review_spec, get_must_hit_rules
    
    spec = build_review_spec()
    
    # Spec 应该有 queries 和 prompt
    assert spec.queries
    assert spec.prompt
    
    # MUST_HIT 规则应该可获取
    rules = get_must_hit_rules()
    assert len(rules) > 0

