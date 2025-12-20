"""
文本抽取工具测试
"""
import os
import pytest
from pathlib import Path

# 设置测试fixtures目录
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def create_test_files():
    """创建测试文件"""
    FIXTURES_DIR.mkdir(exist_ok=True)
    
    # 创建txt测试文件
    txt_file = FIXTURES_DIR / "test.txt"
    txt_file.write_text("这是一个测试文本文件。\nHello World!", encoding="utf-8")
    
    # 创建md测试文件
    md_file = FIXTURES_DIR / "test.md"
    md_file.write_text("# 测试Markdown\n\n这是一个**测试**文档。", encoding="utf-8")
    
    # 创建json测试文件
    json_file = FIXTURES_DIR / "test.json"
    json_file.write_text('{"name": "测试", "value": 123}', encoding="utf-8")
    
    # 创建csv测试文件
    csv_file = FIXTURES_DIR / "test.csv"
    csv_file.write_text("姓名,年龄\n张三,25\n李四,30", encoding="utf-8")


def test_extract_text():
    """测试纯文本抽取"""
    from app.utils.text_extractor import extract_text_from_file
    
    create_test_files()
    txt_file = FIXTURES_DIR / "test.txt"
    
    text = extract_text_from_file(str(txt_file))
    assert "这是一个测试文本文件" in text
    assert "Hello World" in text


def test_extract_json():
    """测试JSON抽取"""
    from app.utils.text_extractor import extract_text_from_file
    
    create_test_files()
    json_file = FIXTURES_DIR / "test.json"
    
    text = extract_text_from_file(str(json_file))
    assert "测试" in text
    assert "123" in text


def test_extract_csv():
    """测试CSV抽取"""
    from app.utils.text_extractor import extract_text_from_file
    
    create_test_files()
    csv_file = FIXTURES_DIR / "test.csv"
    
    text = extract_text_from_file(str(csv_file))
    assert "姓名" in text
    assert "张三" in text
    assert "25" in text


def test_safe_filename():
    """测试文件名安全处理"""
    from app.utils.text_extractor import get_safe_filename
    
    # 测试路径穿越
    assert "/" not in get_safe_filename("../../../etc/passwd")
    assert "\\" not in get_safe_filename("..\\..\\windows\\system32")
    
    # 测试正常文件名
    assert get_safe_filename("test.txt") == "test.txt"
    assert get_safe_filename("测试文档.pdf") == "测试文档.pdf"


def test_file_extension():
    """测试文件扩展名检查"""
    from app.utils.text_extractor import is_allowed_extension
    
    allowed = {'.txt', '.pdf', '.docx'}
    
    assert is_allowed_extension("test.txt", allowed) == True
    assert is_allowed_extension("test.pdf", allowed) == True
    assert is_allowed_extension("test.exe", allowed) == False
    assert is_allowed_extension("test.TXT", allowed) == True  # 大小写不敏感


def test_nonexistent_file():
    """测试不存在的文件"""
    from app.utils.text_extractor import extract_text_from_file, TextExtractionError
    
    with pytest.raises(TextExtractionError):
        extract_text_from_file("/nonexistent/file.txt")


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
