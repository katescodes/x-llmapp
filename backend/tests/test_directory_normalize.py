"""
目录规范化单元测试
测试 _normalize_directory_nodes 的三个核心功能：
1. 折叠 wrapper
2. 确保三分册为一级
3. 语义分桶纠偏（特别是"全挂报价"的纠偏）
"""
import pytest
from app.services.tender_service import TenderService


@pytest.fixture
def tender_service():
    """创建 TenderService 实例（不需要真实的 pool 和 llm）"""
    # 使用 None 作为参数，因为我们只测试 normalize 方法
    service = TenderService(pool=None, llm=None)
    return service


def test_collapse_wrapper_with_three_sections(tender_service):
    """测试折叠 wrapper 节点（包含三分册）"""
    nodes = [
        {"title": "磋商响应文件", "level": 1, "order_no": 1},
        {"title": "资信及商务文件", "level": 2, "order_no": 1, "parent_ref": "磋商响应文件"},
        {"title": "技术文件", "level": 2, "order_no": 2, "parent_ref": "磋商响应文件"},
        {"title": "报价文件", "level": 2, "order_no": 3, "parent_ref": "磋商响应文件"},
        {"title": "营业执照", "level": 3, "order_no": 1, "parent_ref": "资信及商务文件"},
    ]
    
    result = tender_service._normalize_directory_nodes(nodes)
    
    # 验证 wrapper 已被移除
    titles = [n["title"] for n in result]
    assert "磋商响应文件" not in titles
    
    # 验证三分册变为 level=1
    sections = [n for n in result if n["title"] in ["资信及商务文件", "技术文件", "报价文件"]]
    assert len(sections) == 3
    for section in sections:
        assert section["level"] == 1
        assert section.get("parent_ref") == ""
    
    # 验证子节点 level 减1
    biz_child = [n for n in result if n["title"] == "营业执照"][0]
    assert biz_child["level"] == 2  # 原来是 3，减1后变2


def test_all_items_hung_under_price_aggressive_rebucket(tender_service):
    """测试"全挂报价"场景的 aggressive 纠偏"""
    nodes = [
        {"title": "资信及商务文件", "level": 1, "order_no": 1, "parent_ref": ""},
        {"title": "技术文件", "level": 1, "order_no": 2, "parent_ref": ""},
        {"title": "报价文件", "level": 1, "order_no": 3, "parent_ref": ""},
        # 以下全部错误地挂到报价文件
        {"title": "法定代表人授权委托书", "level": 2, "order_no": 1, "parent_ref": "报价文件"},
        {"title": "营业执照副本", "level": 2, "order_no": 2, "parent_ref": "报价文件"},
        {"title": "资质证书", "level": 2, "order_no": 3, "parent_ref": "报价文件"},
        {"title": "社保证明", "level": 2, "order_no": 4, "parent_ref": "报价文件"},
        {"title": "信用中国截图", "level": 2, "order_no": 5, "parent_ref": "报价文件"},
        {"title": "企业自评表", "level": 2, "order_no": 6, "parent_ref": "报价文件"},
        {"title": "技术偏离表", "level": 2, "order_no": 7, "parent_ref": "报价文件"},
        {"title": "技术规格书", "level": 2, "order_no": 8, "parent_ref": "报价文件"},
        {"title": "整体方案", "level": 2, "order_no": 9, "parent_ref": "报价文件"},
        {"title": "实施组织方案", "level": 2, "order_no": 10, "parent_ref": "报价文件"},
    ]
    
    result = tender_service._normalize_directory_nodes(nodes)
    
    # 收集各分册下的子节点
    biz_children = [n for n in result if n.get("parent_ref") == "资信及商务文件"]
    tech_children = [n for n in result if n.get("parent_ref") == "技术文件"]
    price_children = [n for n in result if n.get("parent_ref") == "报价文件"]
    
    # 验证资信商务分册下有正确的节点
    biz_titles = [n["title"] for n in biz_children]
    assert "法定代表人授权委托书" in biz_titles
    assert "营业执照副本" in biz_titles
    assert "资质证书" in biz_titles
    assert "社保证明" in biz_titles
    assert "信用中国截图" in biz_titles
    assert "企业自评表" in biz_titles
    assert len(biz_children) >= 6
    
    # 验证技术分册下有正确的节点
    tech_titles = [n["title"] for n in tech_children]
    assert "技术偏离表" in tech_titles
    assert "技术规格书" in tech_titles
    assert "整体方案" in tech_titles
    assert "实施组织方案" in tech_titles
    assert len(tech_children) >= 4
    
    # 报价文件下应该没有这些错挂的节点
    price_titles = [n["title"] for n in price_children]
    assert "营业执照副本" not in price_titles
    assert "技术偏离表" not in price_titles
    
    # 验证所有纠偏后的节点 level=2
    for n in biz_children + tech_children:
        assert n["level"] == 2


def test_section_titles_identification(tender_service):
    """测试三分册标题识别（模糊匹配）"""
    nodes = [
        {"title": "第一部分 资信及商务文件", "level": 1},
        {"title": "第二部分 技术文件", "level": 1},
        {"title": "第三部分 磋商报价文件", "level": 1},  # 变体："磋商报价文件"
    ]
    
    sections = tender_service._find_section_titles(nodes)
    
    assert sections["biz"] == "第一部分 资信及商务文件"
    assert sections["tech"] == "第二部分 技术文件"
    assert sections["price"] == "第三部分 磋商报价文件"


def test_bucket_by_title(tender_service):
    """测试根据标题内容判断分桶"""
    assert tender_service._bucket_by_title("投标报价汇总表") == "price"
    assert tender_service._bucket_by_title("分项报价明细") == "price"
    assert tender_service._bucket_by_title("技术偏离表") == "tech"
    assert tender_service._bucket_by_title("整体技术方案") == "tech"
    assert tender_service._bucket_by_title("技术规格参数表") == "tech"
    assert tender_service._bucket_by_title("营业执照副本") == "biz"
    assert tender_service._bucket_by_title("资质证书") == "biz"
    assert tender_service._bucket_by_title("社保缴纳证明") == "biz"
    assert tender_service._bucket_by_title("法定代表人授权委托书") == "biz"
    assert tender_service._bucket_by_title("企业自评表") == "biz"


def test_no_wrapper_no_collapse(tender_service):
    """测试没有 wrapper 时不折叠"""
    nodes = [
        {"title": "资信及商务文件", "level": 1, "order_no": 1},
        {"title": "技术文件", "level": 1, "order_no": 2},
        {"title": "报价文件", "level": 1, "order_no": 3},
    ]
    
    result = tender_service._normalize_directory_nodes(nodes)
    
    # 没有 wrapper，结构应保持不变（只是确保三分册为 level=1）
    assert len(result) == 3
    for n in result:
        assert n["level"] == 1


def test_empty_nodes(tender_service):
    """测试空节点列表"""
    result = tender_service._normalize_directory_nodes([])
    assert result == []
    
    result = tender_service._normalize_directory_nodes(None)
    assert result == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

