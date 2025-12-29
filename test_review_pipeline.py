#!/usr/bin/env python3
"""
测试审核流程 - 验证目标 A/B/C
"""
import asyncio
import sys
import os

# 添加 backend 到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.database import get_db_pool
from app.works.tender.review_pipeline_v3 import ReviewPipelineV3

async def main():
    project_id = "tp_3f49f66ead6d46e1bac3f0bd16a3efe9"
    bidder_name = "测试投标人"
    
    print(f"开始测试审核流程...")
    print(f"项目ID: {project_id}")
    print(f"投标人: {bidder_name}")
    print("-" * 60)
    
    # 获取数据库连接池
    pool = get_db_pool()
    
    # 创建 pipeline
    pipeline = ReviewPipelineV3(pool=pool, llm_orchestrator=None)
    
    # 运行审核
    result = await pipeline.run_pipeline(
        project_id=project_id,
        bidder_name=bidder_name,
        model_id=None,
        use_llm_semantic=False  # 不使用 LLM
    )
    
    # 输出统计
    stats = result.get("stats", {})
    print("\n" + "=" * 60)
    print("审核结果统计:")
    print("=" * 60)
    print(f"总条目数: {stats.get('total_review_items', 0)}")
    print(f"PASS:     {stats.get('pass_count', 0)}")
    print(f"FAIL:     {stats.get('fail_count', 0)}")
    print(f"WARN:     {stats.get('warn_count', 0)}")
    print(f"PENDING:  {stats.get('pending_count', 0)}")
    print("-" * 60)
    
    # 按 evaluator 分组统计
    from collections import defaultdict
    evaluator_stats = defaultdict(lambda: defaultdict(int))
    
    for item in result.get("review_items", []):
        evaluator = item.get("evaluator", "unknown")
        status = item.get("status", "unknown")
        evaluator_stats[evaluator][status] += 1
    
    print("\n按评估器分组:")
    for evaluator, status_counts in sorted(evaluator_stats.items()):
        print(f"\n  {evaluator}:")
        for status, count in sorted(status_counts.items()):
            print(f"    {status}: {count}")
    
    # 显示 out_of_scope 样例
    out_of_scope_items = [
        item for item in result.get("review_items", [])
        if item.get("evaluator") == "out_of_scope"
    ]
    
    if out_of_scope_items:
        print("\n" + "=" * 60)
        print(f"目标A验收: 发现 {len(out_of_scope_items)} 个过程性条款 (out_of_scope)")
        print("=" * 60)
        for i, item in enumerate(out_of_scope_items[:5], 1):
            print(f"\n样例 {i}:")
            print(f"  条款: {item.get('tender_requirement', '')[:80]}")
            print(f"  状态: {item.get('status')}")
            print(f"  备注: {item.get('remark')}")
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())

