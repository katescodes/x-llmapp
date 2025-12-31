"""
测试：过滤合同条款和格式范例
"""
import sys
sys.path.insert(0, '/aidata/x-llmapp1/backend')

from app.works.tender.extract_v2_service import ExtractV2Service


def test_filter_logic():
    """测试过滤逻辑"""
    
    # 创建service实例（只用于测试过滤方法）
    service = ExtractV2Service(pool=None, llm_orchestrator=None)
    
    # 测试数据
    test_requirements = [
        # 应该保留的（实质性要求）
        {
            "requirement_id": "req_001",
            "requirement_text": "投标人须具备建筑工程施工总承包二级及以上资质",
            "dimension": "qualification"
        },
        {
            "requirement_id": "req_002",
            "requirement_text": "工期不得超过180天",
            "dimension": "duration"
        },
        {
            "requirement_id": "req_003",
            "requirement_text": "质保期不少于2年",
            "dimension": "warranty"
        },
        {
            "requirement_id": "req_004",
            "requirement_text": "技术方案应包含施工组织设计和安全保障措施",
            "dimension": "technical"
        },
        
        # 应该过滤掉的（合同条款）
        {
            "requirement_id": "contract_001",
            "requirement_text": "合同范本：甲方应在工程验收合格后30日内支付尾款",
            "dimension": "other"
        },
        {
            "requirement_id": "contract_002",
            "requirement_text": "乙方负责施工现场的安全管理，违约责任由乙方承担",
            "dimension": "other"
        },
        {
            "requirement_id": "contract_003",
            "requirement_text": "拟签订的合同协议书中明确了争议解决方式",
            "dimension": "other"
        },
        
        # 应该过滤掉的（格式范例）
        {
            "requirement_id": "format_001",
            "requirement_text": "投标文件格式：封面应注明项目名称、投标人名称",
            "dimension": "document"
        },
        {
            "requirement_id": "format_002",
            "requirement_text": "法定代表人授权书格式见附件，投标人按此格式填写",
            "dimension": "document"
        },
        {
            "requirement_id": "format_003",
            "requirement_text": "报价表格式范本如下，投标人可参考此样表编制",
            "dimension": "price"
        },
    ]
    
    print("=" * 60)
    print("测试：过滤合同条款和格式范例")
    print("=" * 60)
    print("")
    
    print(f"原始要求数量: {len(test_requirements)}")
    print("")
    
    # 执行过滤
    filtered = service._filter_out_format_and_contract(test_requirements)
    
    print(f"过滤后数量: {len(filtered)}")
    print(f"过滤掉: {len(test_requirements) - len(filtered)} 条")
    print("")
    
    # 验证结果
    print("保留的要求:")
    for req in filtered:
        print(f"  ✓ [{req['requirement_id']}] {req['requirement_text'][:40]}...")
    
    print("")
    print("过滤掉的要求:")
    filtered_ids = {req['requirement_id'] for req in filtered}
    for req in test_requirements:
        if req['requirement_id'] not in filtered_ids:
            reason = "合同条款" if any(k in req['requirement_text'] for k in ["合同", "甲方", "乙方"]) else "格式范例"
            print(f"  ✗ [{req['requirement_id']}] ({reason}) {req['requirement_text'][:40]}...")
    
    print("")
    print("=" * 60)
    
    # 断言验证
    assert len(filtered) == 4, f"应该保留4条，实际保留{len(filtered)}条"
    assert all(req['requirement_id'].startswith('req_') for req in filtered), "保留的应该都是req_开头"
    
    print("✅ 测试通过！")
    print("")
    print("说明：")
    print("- 实质性要求（资质、工期、质保、技术）：✓ 保留")
    print("- 合同条款（甲方、乙方、违约、争议）：✗ 过滤")
    print("- 格式范例（格式、范本、样表）：✗ 过滤")
    
    return True


if __name__ == "__main__":
    try:
        success = test_filter_logic()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

