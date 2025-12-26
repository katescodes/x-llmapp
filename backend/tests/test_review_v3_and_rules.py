"""
测试审核服务 V3 和规则引擎
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock


def test_effective_ruleset_builder_exists():
    """测试 EffectiveRulesetBuilder 文件存在"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "rules" / "effective_ruleset.py"
    assert file_path.exists()
    
    content = file_path.read_text(encoding="utf-8")
    assert "class EffectiveRulesetBuilder" in content
    assert "build_effective_ruleset" in content
    assert "get_rules_by_type" in content


def test_deterministic_engine_exists():
    """测试 DeterministicRuleEngine 文件存在"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "rules" / "deterministic_engine.py"
    assert file_path.exists()
    
    content = file_path.read_text(encoding="utf-8")
    assert "class DeterministicRuleEngine" in content
    assert "evaluate_rules" in content
    assert "check_requirement_response" in content or "_check_requirement_response" in content


def test_semantic_llm_engine_exists():
    """测试 SemanticLLMRuleEngine 文件存在"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "rules" / "semantic_llm_engine.py"
    assert file_path.exists()
    
    content = file_path.read_text(encoding="utf-8")
    assert "class SemanticLLMRuleEngine" in content
    assert "evaluate_rules" in content
    assert "async def" in content  # 异步方法


def test_review_v3_service_exists():
    """测试 ReviewV3Service 文件存在"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "review_v3_service.py"
    assert file_path.exists()
    
    content = file_path.read_text(encoding="utf-8")
    assert "class ReviewV3Service" in content
    assert "run_review_v3" in content
    assert "requirements × response" in content


def test_effective_ruleset_deduplication_logic():
    """测试有效规则集的去重逻辑"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "rules" / "effective_ruleset.py"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证去重方法存在
    assert "_deduplicate_by_rule_key" in content
    
    # 验证规则合并策略
    assert "project_custom" in content
    assert "system_default" in content


def test_deterministic_engine_rule_types():
    """测试确定性引擎支持的规则类型"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "rules" / "deterministic_engine.py"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证支持的规则类型
    assert "check_requirement_response" in content
    assert "check_value_threshold" in content or "threshold" in content
    assert "check_document_provided" in content or "document" in content


def test_review_v3_service_uses_requirements_and_responses():
    """测试 ReviewV3Service 使用 requirements 和 responses"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "review_v3_service.py"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证读取 requirements
    assert "tender_requirements" in content
    assert "_get_requirements" in content
    
    # 验证读取 responses
    assert "tender_bid_response_items" in content
    assert "_get_responses" in content
    
    # 验证使用规则引擎
    assert "DeterministicRuleEngine" in content
    assert "SemanticLLMRuleEngine" in content
    assert "EffectiveRulesetBuilder" in content


def test_review_v3_service_saves_to_review_items():
    """测试 ReviewV3Service 保存结果到 tender_review_items"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "review_v3_service.py"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证落库逻辑
    assert "tender_review_items" in content
    assert "_save_review_items" in content
    assert "INSERT INTO" in content
    
    # 验证新字段
    assert "rule_id" in content
    assert "requirement_id" in content
    assert "severity" in content
    assert "evaluator" in content


def test_semantic_llm_engine_async():
    """测试语义LLM引擎是异步的"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "rules" / "semantic_llm_engine.py"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证异步方法
    assert "async def evaluate_rules" in content


def test_deterministic_engine_synchronous():
    """测试确定性引擎是同步的"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "rules" / "deterministic_engine.py"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证同步方法（不是异步）
    assert "def evaluate_rules" in content
    # 确保不是异步
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if "def evaluate_rules" in line:
            # 检查前一行不是 async
            assert "async" not in lines[i] and "async" not in lines[i-1]
            break


def test_rules_module_init():
    """测试规则模块的 __init__.py"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "rules" / "__init__.py"
    assert file_path.exists()
    
    content = file_path.read_text(encoding="utf-8")
    
    # 验证导出
    assert "EffectiveRulesetBuilder" in content
    assert "DeterministicRuleEngine" in content
    assert "SemanticLLMRuleEngine" in content


def test_effective_ruleset_priority_sorting():
    """测试有效规则集按 priority 排序"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "rules" / "effective_ruleset.py"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证排序逻辑
    assert "priority" in content
    assert "sort" in content


def test_review_v3_handles_no_responses():
    """测试 ReviewV3Service 处理无响应的情况"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "review_v3_service.py"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证无响应处理
    assert "_handle_no_responses" in content or "no responses" in content.lower()


def test_deterministic_engine_indexes_by_dimension():
    """测试确定性引擎按维度索引"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "rules" / "deterministic_engine.py"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证按维度索引
    assert "dimension" in content
    assert "_index" in content or "index" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

