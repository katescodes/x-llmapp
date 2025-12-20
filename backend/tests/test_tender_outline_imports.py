"""
测试 outline 导入兼容性
验证 shim 生效，可以从新旧路径导入
"""
import pytest


def test_outline_v2_service_import():
    """测试可以导入 outline_v2_service"""
    from app.works.tender.outline.outline_v2_service import generate_outline_v2
    
    assert callable(generate_outline_v2)


def test_shim_imports_work():
    """测试 shim 生效，可以从旧路径导入"""
    # 从 shim 路径导入
    from app.services.semantic_outline import (
        RequirementExtractionService,
        OutlineSynthesisService,
    )
    
    # 验证类可以实例化
    req_service = RequirementExtractionService(llm_orchestrator=None)
    assert req_service is not None
    
    outline_service = OutlineSynthesisService(llm_orchestrator=None)
    assert outline_service is not None


def test_shim_direct_module_import():
    """测试直接导入shim模块文件"""
    from app.services.semantic_outline.requirement_extraction_service import RequirementExtractionService
    from app.services.semantic_outline.outline_synthesis_service import OutlineSynthesisService
    
    assert RequirementExtractionService is not None
    assert OutlineSynthesisService is not None


def test_new_path_imports():
    """测试从新路径导入"""
    from app.works.tender.outline import (
        RequirementExtractionService,
        OutlineSynthesisService,
    )
    
    assert RequirementExtractionService is not None
    assert OutlineSynthesisService is not None

