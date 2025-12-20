"""
Step 6: 测试 NEW_ONLY 路径不写入 kb_documents/kb_chunks

这个测试确保：
1. 静态：works/tender 和 platform 的 NEW_ONLY 分支不包含 KB 写入调用
2. 运行时：tender_service._ingest_to_kb 在 NEW_ONLY 模式下会直接抛出异常
"""
import pytest
import re
from pathlib import Path


def test_static_no_kb_writes_in_newonly_paths():
    """
    静态检查：扫描 works/tender + platform/ingest 确保不包含未保护的 KB 写入
    """
    backend_root = Path(__file__).parent.parent / "app"
    
    # 检查的目标
    check_targets = [
        backend_root / "works" / "tender",
        backend_root / "platform" / "extraction",
    ]
    
    # 禁止的模式
    forbidden_patterns = [
        r'\.create_kb_document\(',
        r'\.insert_kb_chunks\(',
        r'\.update_kb_document\(',
    ]
    
    violations = []
    
    for target in check_targets:
        if not target.exists():
            continue
        
        for py_file in target.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            
            content = py_file.read_text(encoding='utf-8')
            rel_path = py_file.relative_to(backend_root.parent)
            
            for pattern in forbidden_patterns:
                matches = list(re.finditer(pattern, content))
                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
                    lines = content.split('\n')
                    
                    # 检查上下文是否有 LEGACY/OLD 标记
                    start_ctx = max(0, line_num - 20)
                    end_ctx = min(len(lines), line_num + 5)
                    context = '\n'.join(lines[start_ctx:end_ctx])
                    
                    # 如果上下文中有 LEGACY 标记，则允许
                    is_legacy = any(marker in context for marker in [
                        'LEGACY',
                        'OLD',
                        '_ingest_to_kb',
                        'need_legacy_ingest',
                    ])
                    
                    if not is_legacy:
                        violations.append(
                            f"{rel_path}:{line_num} - {pattern} without LEGACY guard"
                        )
    
    assert not violations, (
        f"Found {len(violations)} KB write calls in NEW_ONLY paths:\n" +
        "\n".join(violations)
    )


def test_runtime_ingest_to_kb_blocks_newonly():
    """
    运行时检查：tender_service._ingest_to_kb 在 NEW_ONLY 模式下应抛出异常
    """
    from unittest.mock import Mock, patch
    from app.services.tender_service import TenderService
    from app.core.cutover import CutoverMode
    
    # 创建 mock 的 TenderService
    mock_dao = Mock()
    mock_llm_orchestrator = Mock()
    service = TenderService(mock_dao, mock_llm_orchestrator)
    
    # Mock cutover config 返回 NEW_ONLY
    mock_config = Mock()
    mock_mode = Mock()
    mock_mode.value = "NEW_ONLY"
    mock_config.get_mode.return_value = mock_mode
    
    # 需要 patch app.core.cutover，因为 get_cutover_config 是在函数内部导入的
    # 同时需要 mock 文件解析函数，避免解析 fake data 出错
    with patch('app.core.cutover.get_cutover_config', return_value=mock_config):
        with patch('app.services.tender_service._read_text_from_file_bytes', return_value="test content"):
            # 尝试调用 _ingest_to_kb，应该抛出异常
            with pytest.raises(RuntimeError) as exc_info:
                service._ingest_to_kb(
                    kb_id="test_kb",
                    filename="test.pdf",
                    kind="tender",
                    bidder_name=None,
                    data=b"fake data"
                )
            
            # 验证异常消息
            error_msg = str(exc_info.value)
            assert "Step6 Boundary" in error_msg
            assert "NEW_ONLY" in error_msg
            assert "kb_documents" in error_msg
            assert "DocStore" in error_msg


def test_runtime_ingest_to_kb_allows_old():
    """
    运行时检查：tender_service._ingest_to_kb 在 OLD 模式下应允许执行
    """
    from unittest.mock import Mock, patch, MagicMock
    from app.services.tender_service import TenderService
    from app.core.cutover import CutoverMode
    
    # 创建 mock 的 TenderService
    mock_dao = Mock()
    mock_dao.create_kb_document.return_value = "doc_123"
    mock_dao.insert_kb_chunks.return_value = None
    
    mock_llm_orchestrator = Mock()
    service = TenderService(mock_dao, mock_llm_orchestrator)
    
    # Mock cutover config 返回 OLD
    mock_config = Mock()
    mock_mode = Mock()
    mock_mode.value = "OLD"
    mock_config.get_mode.return_value = mock_mode
    
    # Mock 文件解析函数
    with patch('app.core.cutover.get_cutover_config', return_value=mock_config):
        with patch('app.services.tender_service._read_text_from_file_bytes', return_value="test content"):
            with patch('app.services.tender_service._chunk_text', return_value=["chunk1", "chunk2"]):
                # 调用 _ingest_to_kb，应该成功
                doc_id = service._ingest_to_kb(
                    kb_id="test_kb",
                    filename="test.pdf",
                    kind="tender",
                    bidder_name=None,
                    data=b"fake data"
                )
                
                # 验证调用了 DAO
                assert doc_id == "doc_123"
                mock_dao.create_kb_document.assert_called_once()
                mock_dao.insert_kb_chunks.assert_called_once()


def test_ingest_v2_service_no_kb_dao_import():
    """
    静态检查：platform/ingest/v2_service.py 不应导入 kb_dao
    """
    v2_service_path = Path(__file__).parent.parent / "app" / "platform" / "ingest" / "v2_service.py"
    
    if not v2_service_path.exists():
        pytest.skip("v2_service.py not found")
    
    content = v2_service_path.read_text(encoding='utf-8')
    
    # 检查是否有 kb_dao 导入
    kb_dao_imports = re.findall(r'from\s+app\.services\.dao\.kb_dao\s+import', content)
    
    assert not kb_dao_imports, (
        f"platform/ingest/v2_service.py should NOT import kb_dao. "
        f"Found {len(kb_dao_imports)} imports."
    )

