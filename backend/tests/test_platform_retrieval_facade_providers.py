"""
测试平台 Retrieval Facade 的 Provider 架构
验证 legacy 和 new provider 都能正确导入和初始化
"""
import pytest


def test_import_facade():
    """测试 facade 能正确导入"""
    from app.platform.retrieval.facade import RetrievalFacade
    assert RetrievalFacade is not None


def test_import_new_provider():
    """测试 new retriever provider 能正确导入"""
    from app.platform.retrieval.new_retriever import NewRetriever
    assert NewRetriever is not None


def test_import_legacy_provider():
    """测试 legacy retriever provider 能正确导入"""
    from app.platform.retrieval.providers.legacy import retrieve
    assert retrieve is not None


def test_import_legacy_modules():
    """测试 legacy 各模块能正确导入"""
    from app.platform.retrieval.providers.legacy.retriever import retrieve
    from app.platform.retrieval.providers.legacy.pg_lexical import search_lexical
    from app.platform.retrieval.providers.legacy.rrf import rrf_fuse
    
    assert retrieve is not None
    assert search_lexical is not None
    assert rrf_fuse is not None


def test_legacy_shim_compatibility():
    """测试旧路径 shim 向后兼容性"""
    # 旧路径应该仍然可以导入（通过 shim）
    from app.services.retrieval.retriever import retrieve
    from app.services.retrieval.rrf import rrf_fuse
    from app.services.retrieval.pg_lexical import search_lexical
    
    assert retrieve is not None
    assert rrf_fuse is not None
    assert search_lexical is not None


def test_facade_instantiation(mock_pool):
    """测试 facade 能正确实例化"""
    from app.platform.retrieval.facade import RetrievalFacade
    
    facade = RetrievalFacade(mock_pool)
    assert facade is not None
    assert facade.new_retriever is not None
    assert hasattr(facade, '_call_legacy_retriever')


@pytest.fixture
def mock_pool():
    """Mock ConnectionPool for testing"""
    class MockPool:
        pass
    return MockPool()


def test_new_retriever_instantiation(mock_pool):
    """测试 new retriever 能正确实例化（不连接真实数据库）"""
    from app.platform.retrieval.new_retriever import NewRetriever
    
    retriever = NewRetriever(mock_pool)
    assert retriever is not None
    assert retriever.pool is mock_pool

