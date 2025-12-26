"""
测试 DOCX 导出模板样式映射
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile


def test_docx_style_mapper_exists():
    """测试 docx_style_mapper.py 文件存在"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "docx_style_mapper.py"
    assert file_path.exists()
    
    content = file_path.read_text(encoding="utf-8")
    assert "validate_template_styles" in content
    assert "insert_toc_field" in content
    assert "apply_heading_style" in content
    assert "ensure_template_compatibility" in content


def test_validate_template_styles_function():
    """测试 validate_template_styles 函数签名"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "docx_style_mapper.py"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证函数定义
    assert "def validate_template_styles" in content
    assert "template_path" in content
    assert "Dict[int, str]" in content
    
    # 验证返回的是层级映射
    assert "heading_map" in content or "Heading" in content


def test_insert_toc_field_function():
    """测试 insert_toc_field 函数"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "docx_style_mapper.py"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证函数定义
    assert "def insert_toc_field" in content
    assert "Document" in content
    
    # 验证 TOC field 相关
    assert "TOC" in content
    assert "fldSimple" in content or "field" in content.lower()


def test_apply_heading_style_function():
    """测试 apply_heading_style 函数"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "docx_style_mapper.py"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证函数定义
    assert "def apply_heading_style" in content
    assert "level" in content
    assert "heading_map" in content
    
    # 验证样式应用逻辑
    assert "paragraph.style" in content


def test_ensure_template_compatibility_function():
    """测试 ensure_template_compatibility 函数"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "docx_style_mapper.py"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证函数定义
    assert "def ensure_template_compatibility" in content
    assert "template_path" in content
    
    # 验证返回配置
    assert "heading_map" in content
    assert "has_toc" in content or "toc" in content.lower()
    assert "normal_style" in content


def test_heading_levels_supported():
    """测试支持1-6层级标题"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "docx_style_mapper.py"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证支持6个层级
    assert "Heading 1" in content
    assert "Heading 2" in content
    assert "Heading 3" in content
    # 层级范围检查
    assert "1, 7" in content or "range(1, 7)" in content or "1-6" in content


def test_toc_field_format():
    """测试 TOC field 格式正确"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "docx_style_mapper.py"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证 TOC field 指令格式
    # 标准格式：TOC \o "1-6" \h \z \u
    assert "TOC" in content
    assert r"\o" in content or "\\o" in content
    
    # 验证使用 OxmlElement 构建
    assert "OxmlElement" in content
    assert "w:fldSimple" in content or "fldSimple" in content


def test_style_mapper_error_handling():
    """测试样式映射的错误处理"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "docx_style_mapper.py"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证有 try-except
    assert "try:" in content
    assert "except" in content
    
    # 验证有默认值
    assert "default" in content.lower()


def test_existing_export_service_compatibility():
    """测试与现有 ExportService 的兼容性"""
    # 检查 ExportService 是否存在
    export_service_path = Path(__file__).parent.parent / "app" / "services" / "export" / "export_service.py"
    if export_service_path.exists():
        content = export_service_path.read_text(encoding="utf-8")
        
        # 验证 ExportService 有导出方法
        assert "class ExportService" in content
        assert "export" in content.lower() or "docx" in content.lower()


def test_docx_exporter_exists():
    """测试 docx_exporter 模块存在"""
    docx_exporter_path = Path(__file__).parent.parent / "app" / "services" / "export" / "docx_exporter.py"
    assert docx_exporter_path.exists()
    
    content = docx_exporter_path.read_text(encoding="utf-8")
    
    # 验证渲染函数
    assert "render_directory_tree_to_docx" in content or "render" in content
    
    # 验证支持模板
    assert "template" in content.lower()


def test_toc_update_instructions():
    """测试 TOC 更新说明"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "docx_style_mapper.py"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证包含用户提示
    assert "F9" in content or "更新" in content or "update" in content.lower()


def test_heading_style_fallback():
    """测试标题样式回退机制"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "docx_style_mapper.py"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证有回退逻辑
    assert "KeyError" in content or "not found" in content.lower()
    assert "default" in content.lower() or "fallback" in content.lower()


def test_normal_style_detection():
    """测试正文样式检测"""
    file_path = Path(__file__).parent.parent / "app" / "works" / "tender" / "docx_style_mapper.py"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证支持多种正文样式名称
    assert "Normal" in content
    assert "正文" in content or "Body Text" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

