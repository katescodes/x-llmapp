"""
测试目录增强功能
"""
import pytest
from unittest.mock import MagicMock, patch
from app.works.tender.directory_augment_v1 import (
    augment_directory_from_tender_info_v3,
    _get_existing_directory_nodes,
)


def test_augment_directory_basic():
    """测试基本目录增强功能"""
    # Mock pool
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    
    # 模拟现有目录节点
    mock_cur.fetchall.return_value = [
        ("node1", "投标函", 1, 1, True, "llm"),  # 精确匹配
        ("node2", "第二章 商务标", 1, 2, True, "llm"),
    ]
    mock_cur.fetchone.return_value = (2,)  # max order_no
    
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_pool.connection.return_value.__enter__.return_value = mock_conn
    
    # 准备 tender_info_v3 数据
    tender_info = {
        "schema_version": "tender_info_v3",
        "document_preparation": {
            "required_forms": [
                {
                    "form_name": "投标函",  # 已存在，应跳过
                    "is_mandatory": True,
                    "evidence_chunk_ids": ["chunk1"]
                },
                {
                    "form_name": "法定代表人身份证明",  # 新节点
                    "is_mandatory": True,
                    "evidence_chunk_ids": ["chunk2"]
                },
                {
                    "form_name": "可选表格",
                    "is_mandatory": False,  # 不强制，应跳过
                    "evidence_chunk_ids": ["chunk3"]
                }
            ]
        },
        "bidder_qualification": {
            "must_provide_documents": [
                "营业执照",  # 新节点
                "资质证书",  # 新节点
            ],
            "evidence_chunk_ids": ["chunk4"]
        }
    }
    
    # 执行增强
    result = augment_directory_from_tender_info_v3(
        project_id="test_project",
        pool=mock_pool,
        tender_info=tender_info
    )
    
    # 验证
    assert result["existing_nodes_count"] == 2
    assert result["identified_required_count"] == 3  # 法定代表人身份证明 + 营业执照 + 资质证书
    assert result["added_count"] == 3
    
    enhanced_titles = result["enhanced_titles"]
    assert "法定代表人身份证明" in enhanced_titles
    assert "营业执照" in enhanced_titles
    assert "资质证书" in enhanced_titles
    assert "投标函" not in enhanced_titles  # 已存在，不应再添加
    assert "可选表格" not in enhanced_titles  # 非强制，不应添加


def test_augment_directory_empty_tender_info():
    """测试空 tender_info"""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    
    mock_cur.fetchall.return_value = [
        ("node1", "第一章", 1, 1, True, "llm"),
    ]
    mock_cur.fetchone.return_value = (1,)
    
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_pool.connection.return_value.__enter__.return_value = mock_conn
    
    tender_info = {
        "schema_version": "tender_info_v3",
        # 没有 document_preparation 和 bidder_qualification
    }
    
    result = augment_directory_from_tender_info_v3(
        project_id="test_project",
        pool=mock_pool,
        tender_info=tender_info
    )
    
    # 验证
    assert result["existing_nodes_count"] == 1
    assert result["identified_required_count"] == 0
    assert result["added_count"] == 0


def test_augment_directory_no_new_nodes():
    """测试所有必填节点都已存在的情况"""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    
    # 模拟现有目录节点（已包含所有必填项）
    mock_cur.fetchall.return_value = [
        ("node1", "投标函", 1, 1, True, "llm"),
        ("node2", "营业执照", 1, 2, True, "llm"),
    ]
    mock_cur.fetchone.return_value = (2,)
    
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_pool.connection.return_value.__enter__.return_value = mock_conn
    
    tender_info = {
        "schema_version": "tender_info_v3",
        "document_preparation": {
            "required_forms": [
                {
                    "form_name": "投标函",  # 已存在
                    "is_mandatory": True,
                    "evidence_chunk_ids": ["chunk1"]
                }
            ]
        },
        "bidder_qualification": {
            "must_provide_documents": [
                "营业执照",  # 已存在
            ],
            "evidence_chunk_ids": ["chunk2"]
        }
    }
    
    result = augment_directory_from_tender_info_v3(
        project_id="test_project",
        pool=mock_pool,
        tender_info=tender_info
    )
    
    # 验证
    assert result["existing_nodes_count"] == 2
    assert result["identified_required_count"] == 0  # 所有都已存在
    assert result["added_count"] == 0


def test_get_existing_directory_nodes():
    """测试获取现有目录节点"""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    
    mock_cur.fetchall.return_value = [
        ("id1", "第一章", 1, 1, True, "llm"),
        ("id2", "第二章", 1, 2, True, "llm"),
        ("id3", "1.1 小节", 2, 3, False, "llm"),
    ]
    
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_pool.connection.return_value.__enter__.return_value = mock_conn
    
    nodes = _get_existing_directory_nodes(mock_pool, "test_project")
    
    # 验证
    assert len(nodes) == 3
    assert nodes[0]["title"] == "第一章"
    assert nodes[0]["level"] == 1
    assert nodes[1]["title"] == "第二章"
    assert nodes[2]["title"] == "1.1 小节"
    assert nodes[2]["level"] == 2
    assert nodes[2]["is_required"] is False


def test_augment_directory_with_evidence_chunk_ids():
    """测试证据ID是否正确传递"""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    
    mock_cur.fetchall.return_value = []
    mock_cur.fetchone.return_value = (0,)
    
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_pool.connection.return_value.__enter__.return_value = mock_conn
    
    tender_info = {
        "schema_version": "tender_info_v3",
        "document_preparation": {
            "required_forms": [
                {
                    "form_name": "投标函",
                    "is_mandatory": True,
                    "evidence_chunk_ids": ["chunk_doc_001", "chunk_doc_002"]
                }
            ]
        }
    }
    
    result = augment_directory_from_tender_info_v3(
        project_id="test_project",
        pool=mock_pool,
        tender_info=tender_info
    )
    
    # 验证
    assert result["added_count"] == 1
    
    # 验证 SQL 调用时传入了正确的 evidence_chunk_ids
    execute_calls = mock_cur.execute.call_args_list
    insert_call = execute_calls[-1]  # 最后一次调用应该是 INSERT
    assert insert_call[0][1][9] == ["chunk_doc_001", "chunk_doc_002"]  # evidence_chunk_ids 参数


def test_augment_directory_deduplication():
    """测试去重逻辑：相同标题只添加一次"""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    
    mock_cur.fetchall.return_value = [
        ("node1", "投标函", 1, 1, True, "llm"),
    ]
    mock_cur.fetchone.return_value = (1,)
    
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_pool.connection.return_value.__enter__.return_value = mock_conn
    
    # 两个来源都要求"营业执照"
    tender_info = {
        "schema_version": "tender_info_v3",
        "document_preparation": {
            "required_forms": [
                {
                    "form_name": "营业执照",
                    "is_mandatory": True,
                    "evidence_chunk_ids": ["chunk1"]
                }
            ]
        },
        "bidder_qualification": {
            "must_provide_documents": [
                "营业执照",  # 重复
            ],
            "evidence_chunk_ids": ["chunk2"]
        }
    }
    
    result = augment_directory_from_tender_info_v3(
        project_id="test_project",
        pool=mock_pool,
        tender_info=tender_info
    )
    
    # 验证：虽然两个来源都有"营业执照"，但只应添加一次
    assert result["identified_required_count"] == 1  # 去重后只识别一次
    assert result["added_count"] == 1
    assert "营业执照" in result["enhanced_titles"]
    assert len(result["enhanced_titles"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

