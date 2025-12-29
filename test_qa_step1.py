#!/usr/bin/env python3
"""
Step 1 测试：QA验证基础架构 - requirement转换为question
"""
import sys
sys.path.insert(0, '/aidata/x-llmapp1/backend')

from app.works.tender.review_pipeline_v3 import ReviewPipelineV3
from app.services.db.postgres import _get_pool

def test_requirement_to_question():
    """测试requirement到question的转换"""
    
    pool = _get_pool()
    pipeline = ReviewPipelineV3(pool=pool)
    
    # 测试用例
    test_cases = [
        {
            "name": "资格-营业执照",
            "req": {
                "requirement_id": "test_1",
                "requirement_text": "投标人须提供有效的营业执照副本",
                "dimension": "qualification",
                "eval_method": "PRESENCE"
            },
            "expected_contains": ["营业执照", "是否提供"]
        },
        {
            "name": "数值-价格",
            "req": {
                "requirement_id": "test_2",
                "requirement_text": "投标报价不得超过控制价 1000000 元",
                "dimension": "price",
                "eval_method": "NUMERIC"
            },
            "expected_contains": ["投标报价", "多少"]
        },
        {
            "name": "数值-工期",
            "req": {
                "requirement_id": "test_3",
                "requirement_text": "工期不得超过180天",
                "dimension": "schedule_quality",
                "eval_method": "NUMERIC"
            },
            "expected_contains": ["工期", "多少天"]
        },
        {
            "name": "技术-参数",
            "req": {
                "requirement_id": "test_4",
                "requirement_text": "设备性能参数应满足国家标准GB/T xxx",
                "dimension": "technical",
                "eval_method": "SEMANTIC"
            },
            "expected_contains": ["技术方案", "是否满足"]
        },
        {
            "name": "商务-质保",
            "req": {
                "requirement_id": "test_5",
                "requirement_text": "质保期不少于24个月",
                "dimension": "business",
                "eval_method": "NUMERIC"
            },
            "expected_contains": ["质保期", "多少个月"]
        }
    ]
    
    print("=" * 70)
    print("Step 1 测试：requirement → question 转换")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    for case in test_cases:
        print(f"\n【{case['name']}】")
        print(f"原文: {case['req']['requirement_text']}")
        
        question = pipeline._requirement_to_question(case['req'])
        print(f"问题: {question}")
        
        # 检查是否包含期望的关键词
        success = all(keyword in question for keyword in case['expected_contains'])
        
        if success:
            print("✅ 通过")
            passed += 1
        else:
            print(f"❌ 失败 - 期望包含关键词: {case['expected_contains']}")
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 70)
    
    return failed == 0

if __name__ == "__main__":
    try:
        success = test_requirement_to_question()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

