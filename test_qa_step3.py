#!/usr/bin/env python3
"""
Step 3 测试：QA验证 - LLM判断逻辑
注意：此测试假设LLM可能未配置，主要验证代码逻辑不崩溃
"""
import sys
sys.path.insert(0, '/app')

import asyncio
from app.works.tender.review_pipeline_v3 import ReviewPipelineV3
from app.services.db.postgres import _get_pool
from app.main import SimpleLLMOrchestrator

async def test_qa_with_llm():
    """测试QA验证的LLM判断功能"""
    
    pool = _get_pool()
    
    # 尝试初始化LLM
    try:
        llm = SimpleLLMOrchestrator()
        print("✅ LLM initialized")
    except Exception as e:
        print(f"⚠️  LLM initialization failed: {e}")
        llm = None
    
    pipeline = ReviewPipelineV3(pool=pool, llm_orchestrator=llm)
    
    # 使用真实的项目ID和投标人
    project_id = "tp_3f49f66ead6d46e1bac3f0bd16a3efe9"  # 测试4项目
    bidder_name = "3"
    
    # 测试用例 - 使用更容易检索到内容的查询
    test_cases = [
        {
            "name": "技术要求",
            "req": {
                "requirement_id": "test_qa_llm_1",
                "requirement_text": "投标设备应满足技术要求",
                "dimension": "technical",
                "eval_method": "SEMANTIC",
                "is_hard": False
            }
        }
    ]
    
    print("=" * 70)
    print("Step 3 测试：QA验证 - LLM判断逻辑")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    for case in test_cases:
        print(f"\n【{case['name']}】")
        print(f"要求: {case['req']['requirement_text']}")
        
        try:
            # 调用QA验证（完整流程：检索 + LLM判断）
            status, remark, confidence, evidence = await pipeline._qa_based_verification(
                req=case['req'],
                project_id=project_id,
                bidder_name=bidder_name
            )
            
            print(f"状态: {status}")
            print(f"说明: {remark}")
            print(f"置信度: {confidence}")
            print(f"证据数量: {len(evidence)}")
            
            # 验收：不应该抛出异常
            if status in ["PASS", "WARN", "FAIL", "PENDING"]:
                print("✅ 通过（返回了有效状态）")
                passed += 1
            else:
                print(f"❌ 失败（状态无效: {status}）")
                failed += 1
                
        except Exception as e:
            print(f"❌ 异常: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 70)
    
    if llm is None:
        print("\n⚠️  注意：LLM未配置，测试仅验证代码不崩溃")
        print("在生产环境中，需要配置LLM才能进行实际判断")
    
    return failed == 0

if __name__ == "__main__":
    try:
        success = asyncio.run(test_qa_with_llm())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

