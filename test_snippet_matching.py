"""
测试范文匹配功能
Phase 2 测试
"""

def test_matching_algorithm():
    """测试匹配算法"""
    from app.works.tender.snippet.snippet_matcher import (
        normalize_title,
        calculate_similarity,
        match_snippets_to_nodes
    )
    
    print("=" * 60)
    print("🧪 Phase 2 测试: 匹配算法")
    print("=" * 60)
    
    # Test 1: 标题归一化
    print("\n📝 Test 1: 标题归一化")
    test_titles = [
        ("1. 投标函（格式）", "投标函"),
        ("附件1：法人授权书", "法人授权书"),
        ("（一）报价一览表", "报价一览表"),
        ("6.1 投标函及投标函附录", "投标函及投标函附录"),
    ]
    
    for original, expected in test_titles:
        normalized = normalize_title(original)
        status = "✅" if expected in normalized else "❌"
        print(f"  {status} '{original}' -> '{normalized}'")
    
    # Test 2: 相似度计算
    print("\n📊 Test 2: 相似度计算")
    test_pairs = [
        ("投标函", "投标函", 1.0, "exact"),  # 精确匹配
        ("投标函", "投标函及投标函附录", 0.9, "synonym"),  # 同义词
        ("法人授权书", "授权委托书", 0.9, "synonym"),  # 同义词
        ("报价表", "投标报价表", 0.9, "synonym"),  # 同义词
        ("投标函", "技术方案", 0.0, "none"),  # 无匹配
    ]
    
    for title1, title2, expected_min, expected_type in test_pairs:
        score, match_type = calculate_similarity(title1, title2)
        status = "✅" if score >= expected_min * 0.8 else "⚠️"
        print(f"  {status} '{title1}' vs '{title2}': {score:.2f} ({match_type})")
    
    # Test 3: 完整匹配流程
    print("\n🔄 Test 3: 完整匹配流程")
    
    # 模拟范文
    snippets = [
        {"id": "snip_1", "title": "投标函"},
        {"id": "snip_2", "title": "法人授权书"},
        {"id": "snip_3", "title": "报价一览表"},
    ]
    
    # 模拟目录节点
    nodes = [
        {"id": "node_1", "title": "1. 投标函及投标函附录"},
        {"id": "node_2", "title": "2. 授权委托书"},
        {"id": "node_3", "title": "3. 投标报价表"},
        {"id": "node_4", "title": "4. 技术方案"},  # 无匹配
    ]
    
    result = match_snippets_to_nodes(snippets, nodes, confidence_threshold=0.7)
    
    print(f"\n  匹配结果:")
    print(f"  - 总节点数: {result['stats']['total_nodes']}")
    print(f"  - 总范文数: {result['stats']['total_snippets']}")
    print(f"  - 匹配成功: {result['stats']['matched_count']}")
    print(f"  - 匹配率: {result['stats']['match_rate']*100:.1f}%")
    
    print(f"\n  匹配详情:")
    for match in result['matches']:
        print(f"    ✅ {match['node_title']} -> {match['snippet_title']} "
              f"({match['match_type']}, {match['confidence']})")
    
    print(f"\n  未匹配节点:")
    for node in result['unmatched_nodes']:
        print(f"    ⚠️  {node['title']}")
    
    # 验证结果
    assert result['stats']['matched_count'] == 3, "应该匹配3个节点"
    assert len(result['unmatched_nodes']) == 1, "应该有1个未匹配节点"
    
    print("\n" + "=" * 60)
    print("✅ Phase 2 匹配算法测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, '/aidata/x-llmapp1/backend')
    
    try:
        test_matching_algorithm()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
