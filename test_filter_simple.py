"""
简化测试：过滤合同条款和格式范例（不依赖环境）
"""


def filter_out_format_and_contract(requirements):
    """过滤函数（从extract_v2_service复制）"""
    # 合同关键词
    contract_keywords = [
        "合同范本", "合同草案", "拟签订的合同", "合同协议书", "合同文本", "合同条款",
        "甲方应", "乙方应", "甲方负责", "乙方负责", "甲方权利", "乙方义务",
        "违约责任", "争议解决", "合同签订", "合同生效", "合同终止"
    ]
    
    # 格式范例关键词
    format_keywords = [
        "投标文件格式", "编制格式", "参考格式", "格式范本", "格式要求",
        "样本", "样表", "模板", "范本", "格式如下", "格式见附件",
        "授权书格式", "承诺函格式", "报价表格式", "封面格式"
    ]
    
    filtered = []
    
    for req in requirements:
        requirement_text = req.get("requirement_text", "")
        if not requirement_text:
            filtered.append(req)
            continue
        
        # 检查是否包含合同关键词
        is_contract = any(keyword in requirement_text for keyword in contract_keywords)
        
        # 检查是否包含格式关键词
        is_format = any(keyword in requirement_text for keyword in format_keywords)
        
        # 不是合同也不是格式，保留
        if not is_contract and not is_format:
            filtered.append(req)
    
    return filtered


def test_filter():
    """测试过滤逻辑"""
    
    test_requirements = [
        # ✓ 应该保留（实质性要求）
        {"id": "req_001", "requirement_text": "投标人须具备建筑工程施工总承包二级及以上资质"},
        {"id": "req_002", "requirement_text": "工期不得超过180天"},
        {"id": "req_003", "requirement_text": "质保期不少于2年"},
        {"id": "req_004", "requirement_text": "技术方案应包含施工组织设计"},
        
        # ✗ 应该过滤（合同条款）
        {"id": "contract_001", "requirement_text": "合同范本：甲方应在工程验收合格后30日内支付尾款"},
        {"id": "contract_002", "requirement_text": "乙方负责施工现场的安全管理，违约责任由乙方承担"},
        {"id": "contract_003", "requirement_text": "拟签订的合同协议书中明确了争议解决方式"},
        
        # ✗ 应该过滤（格式范例）
        {"id": "format_001", "requirement_text": "投标文件格式：封面应注明项目名称"},
        {"id": "format_002", "requirement_text": "法定代表人授权书格式见附件"},
        {"id": "format_003", "requirement_text": "报价表格式范本如下"},
    ]
    
    print("=" * 70)
    print("测试：过滤合同条款和格式范例")
    print("=" * 70)
    print(f"\n原始要求: {len(test_requirements)} 条\n")
    
    # 执行过滤
    filtered = filter_out_format_and_contract(test_requirements)
    
    print(f"过滤后: {len(filtered)} 条")
    print(f"过滤掉: {len(test_requirements) - len(filtered)} 条\n")
    
    # 显示结果
    print("✓ 保留的要求（实质性）:")
    for req in filtered:
        print(f"  [{req['id']}] {req['requirement_text']}")
    
    print("\n✗ 过滤掉的要求:")
    filtered_ids = {req['id'] for req in filtered}
    for req in test_requirements:
        if req['id'] not in filtered_ids:
            text = req['requirement_text']
            reason = "合同条款" if any(k in text for k in ["合同", "甲方", "乙方", "违约", "争议"]) else "格式范例"
            print(f"  [{req['id']}] ({reason}) {text}")
    
    print("\n" + "=" * 70)
    
    # 验证
    assert len(filtered) == 4, f"期望保留4条，实际{len(filtered)}条"
    assert all(req['id'].startswith('req_') for req in filtered)
    
    print("✅ 测试通过！")
    print("\n过滤规则:")
    print("  • 合同类关键词：合同范本、甲方应、乙方应、违约责任、争议解决")
    print("  • 格式类关键词：投标文件格式、授权书格式、范本、样表、模板")
    
    return True


if __name__ == "__main__":
    try:
        test_filter()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

