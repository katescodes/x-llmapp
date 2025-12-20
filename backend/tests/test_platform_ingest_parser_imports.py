"""
测试 Document Parser 平台化迁移：
1. 新路径导入正常
2. 旧路径 shim 仍可用（向后兼容）
3. 指向同一个函数对象
4. ParsedDocument 类也可以正常导入
"""


def test_new_path_import():
    """测试新路径导入"""
    from app.platform.ingest.parser import parse_document, ParsedDocument
    
    assert parse_document is not None
    assert callable(parse_document)
    assert ParsedDocument is not None


def test_old_path_shim_import():
    """测试旧路径 shim 仍可导入（向后兼容）"""
    from app.services.documents.parser import parse_document, ParsedDocument
    
    assert parse_document is not None
    assert callable(parse_document)
    assert ParsedDocument is not None


def test_same_function_reference():
    """测试新旧路径指向同一个函数对象"""
    from app.platform.ingest.parser import parse_document as new_parse
    from app.services.documents.parser import parse_document as old_parse
    
    # 应该是同一个函数对象
    assert new_parse is old_parse, "新旧路径应指向同一个函数对象"


def test_same_class_reference():
    """测试新旧路径 ParsedDocument 指向同一个类"""
    from app.platform.ingest.parser import ParsedDocument as NewParsed
    from app.services.documents.parser import ParsedDocument as OldParsed
    
    assert NewParsed is OldParsed, "新旧路径 ParsedDocument 应指向同一个类"


def test_constants_exported():
    """测试常量也被正确导出"""
    from app.platform.ingest.parser import TEXT_EXTS, PDF_EXTS, DOCX_EXTS
    from app.services.documents.parser import TEXT_EXTS as OLD_TEXT, PDF_EXTS as OLD_PDF
    
    assert TEXT_EXTS is not None
    assert PDF_EXTS is not None
    assert DOCX_EXTS is not None
    
    # 应该是同一个对象
    assert TEXT_EXTS is OLD_TEXT
    assert PDF_EXTS is OLD_PDF


def test_parsed_document_dataclass():
    """测试 ParsedDocument 数据类可以正常实例化"""
    from app.platform.ingest.parser import ParsedDocument
    
    doc = ParsedDocument(
        title="Test",
        text="Hello World",
        metadata={"filename": "test.txt"}
    )
    
    assert doc.title == "Test"
    assert doc.text == "Hello World"
    assert doc.metadata["filename"] == "test.txt"

