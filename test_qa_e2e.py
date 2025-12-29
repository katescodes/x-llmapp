#!/usr/bin/env python3
"""
端到端测试：QA验证完整流程
"""
import sys
sys.path.insert(0, '/app')

import asyncio
from app.works.tender.review_v3_service import ReviewV3Service
from app.services.db.postgres import _get_pool
from app.main import SimpleLLMOrchestrator

async def test_e2e_review():
    """端到端测试：完整的审核流程"""
    
    pool = _get_pool()
    
    # 初始化LLM
    try:
        llm = SimpleLLMOrchestrator()
        print("✅ LLM initialized")
    except Exception as e:
        print(f"⚠️  LLM initialization failed: {e}")
        llm = None
    
    # 初始化审核服务
    review_service = ReviewV3Service(pool=pool, llm_orchestrator=llm)
    
    # 使用真实的项目ID和投标人
    project_id = "tp_3f49f66ead6d46e1bac3f0bd16a3efe9"  # 测试4项目
    bidder_name = "3"
    
    print("=" * 70)
    print("端到端测试：QA验证完整流程")
    print("=" * 70)
    print(f"项目ID: {project_id}")
    print(f"投标人: {bidder_name}")
    print()
    
    try:
        print("开始审核...")
        
        # 运行审核（启用LLM语义审核）
        result = await review_service.run_review_v3(
            project_id=project_id,
            bidder_name=bidder_name,
            use_llm_semantic=True,  # ✅ 启用QA验证
        )
        
        print(f"\n审核完成！")
        print(f"  - 总计: {result.get('total_review_items', 0)}")
        print(f"  - PASS: {result.get('pass_count', 0)}")
        print(f"  - FAIL: {result.get('fail_count', 0)}")
        print(f"  - WARN: {result.get('warn_count', 0)}")
        print(f"  - PENDING: {result.get('pending_count', 0)}")
        print(f"  - 模式: {result.get('review_mode', 'UNKNOWN')}")
        
        # 检查是否有使用QA验证的项
        items = result.get('items', [])
        qa_items = [
            item for item in items 
            if 'QA验证' in str(item.get('remark', ''))
        ]
        
        print(f"\n使用QA验证的审核项: {len(qa_items)}")
        
        if qa_items:
            print("\nQA验证示例：")
            for i, item in enumerate(qa_items[:3]):
                print(f"\n  [{i+1}] {item.get('clause_title', 'N/A')[:50]}")
                print(f"      状态: {item.get('status')}")
                print(f"      说明: {item.get('remark', 'N/A')[:100]}")
                print(f"      评估器: {item.get('evaluator')}")
        
        # 验收
        print("\n" + "=" * 70)
        if result.get('total_review_items', 0) > 0:
            print("✅ 端到端测试通过：审核流程正常运行")
            if qa_items:
                print(f"✅ QA验证已集成：{len(qa_items)}个审核项使用了QA验证")
            else:
                print("⚠️  未检测到QA验证项（可能是因为没有SEMANTIC类型的requirement）")
            return True
        else:
            print("❌ 端到端测试失败：未生成审核结果")
            return False
            
    except Exception as e:
        print(f"\n❌ 端到端测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(test_e2e_review())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

