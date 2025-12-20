"""
测试 Milvus DocSegStore 平台化迁移：
1. 新路径导入正常
2. 旧路径 shim 仍可用（向后兼容）
3. 指向同一个对象
4. COLLECTION_NAME / MilvusDocSegStore 类也可以正常导入
"""


def test_new_path_import():
    """测试新路径导入"""
    from app.platform.vectorstore.milvus_docseg_store import (
        COLLECTION_NAME,
        MilvusDocSegStore,
        milvus_docseg_store,
    )
    
    assert COLLECTION_NAME is not None
    assert COLLECTION_NAME == "doc_segments_v1"
    assert MilvusDocSegStore is not None
    assert milvus_docseg_store is not None
    assert isinstance(milvus_docseg_store, MilvusDocSegStore)


def test_old_path_shim_import():
    """测试旧路径 shim 仍可导入（向后兼容）"""
    from app.services.vectorstore.milvus_docseg_store import (
        COLLECTION_NAME,
        MilvusDocSegStore,
        milvus_docseg_store,
    )
    
    assert COLLECTION_NAME is not None
    assert MilvusDocSegStore is not None
    assert milvus_docseg_store is not None


def test_same_object_reference():
    """测试新旧路径指向同一个对象"""
    from app.platform.vectorstore.milvus_docseg_store import (
        milvus_docseg_store as new_store,
        MilvusDocSegStore as NewClass,
        COLLECTION_NAME as new_name,
    )
    from app.services.vectorstore.milvus_docseg_store import (
        milvus_docseg_store as old_store,
        MilvusDocSegStore as OldClass,
        COLLECTION_NAME as old_name,
    )
    
    # 应该是同一个实例
    assert new_store is old_store, "新旧路径应指向同一个 milvus_docseg_store 实例"
    assert NewClass is OldClass, "新旧路径应指向同一个 MilvusDocSegStore 类"
    assert new_name == old_name, "COLLECTION_NAME 应该相同"


def test_milvus_store_class():
    """测试 MilvusDocSegStore 类可以实例化"""
    from app.platform.vectorstore.milvus_docseg_store import MilvusDocSegStore
    
    # 注意：实际实例化会连接 Milvus，这里只测试类存在
    assert hasattr(MilvusDocSegStore, 'upsert_segments')
    assert hasattr(MilvusDocSegStore, 'delete_by_version')
    assert hasattr(MilvusDocSegStore, 'search_dense')


def test_collection_name_constant():
    """测试 COLLECTION_NAME 常量正确导出"""
    from app.platform.vectorstore.milvus_docseg_store import COLLECTION_NAME
    from app.services.vectorstore.milvus_docseg_store import COLLECTION_NAME as OLD_NAME
    
    assert COLLECTION_NAME == "doc_segments_v1"
    assert COLLECTION_NAME == OLD_NAME

