"""
测试 DocStore 平台化迁移：
1. 新路径导入正常
2. 旧路径 shim 仍可用（向后兼容）
3. 指向同一个类
4. 关键方法存在
"""


def test_new_path_import():
    """测试新路径导入"""
    from app.platform.docstore.service import DocStoreService
    
    assert DocStoreService is not None
    assert hasattr(DocStoreService, '__init__')


def test_old_path_shim_import():
    """测试旧路径 shim 仍可导入（向后兼容）"""
    from app.services.platform.docstore_service import DocStoreService
    
    assert DocStoreService is not None
    assert hasattr(DocStoreService, '__init__')


def test_same_class_reference():
    """测试新旧路径指向同一个类"""
    from app.platform.docstore.service import DocStoreService as NewDocStore
    from app.services.platform.docstore_service import DocStoreService as OldDocStore
    
    assert NewDocStore is OldDocStore, "新旧路径应指向同一个类对象"


def test_docstore_key_methods_exist():
    """测试 DocStoreService 关键方法存在"""
    from app.platform.docstore.service import DocStoreService
    
    # 创建方法
    assert hasattr(DocStoreService, 'create_document')
    assert hasattr(DocStoreService, 'create_document_version')
    assert hasattr(DocStoreService, 'create_segments')
    
    # 查询方法
    assert hasattr(DocStoreService, 'get_document')
    assert hasattr(DocStoreService, 'get_document_version')
    assert hasattr(DocStoreService, 'get_segments_by_version')
    assert hasattr(DocStoreService, 'count_segments_by_version')
    assert hasattr(DocStoreService, 'get_latest_version_by_document')
    
    # 验证方法可调用
    assert callable(getattr(DocStoreService, 'create_document'))
    assert callable(getattr(DocStoreService, 'create_document_version'))
    assert callable(getattr(DocStoreService, 'create_segments'))
    assert callable(getattr(DocStoreService, 'count_segments_by_version'))

