#!/usr/bin/env python3
"""测试审核流程 - 验证目标 A/B/C"""
import sys
import asyncio
sys.path.insert(0, "/app")

from app.database import get_db_pool
from app.works.tender.review_pipeline_v3 import ReviewPipelineV3
from collections import defaultdict

async def test():
    project_id = "tp_3f49f66ead6d46e1bac3f0bd16a3efe9"
    bidder_name = "测试投标人"
    
    print(f"开始审核: {project_id} / {bidder_name}")
    print("=" * 60)
    
    pool = get_db_pool()
    pipeline = ReviewPipelineV3(pool=pool, llm_orchestrator=None)
    
    result = await pipeline.run_pipeline(
        project_id=project_id,
        bidder_name=bidder_name,
        model_id=None,
        use_llm_semantic=False
    )
    
    stats = result.get("stats", {})
    print("\n统计:")
    total = stats.get("total_review_items", 0)
    pass_c = stats.get("pass_count", 0)
    fail_c = stats.get("fail_count", 0)
    warn_c = stats.get("warn_count", 0)
    pending_c = stats.get("pending_count", 0)
    print(f"  总数:    {total}")
    print(f"  PASS:    {pass_c}")
    print(f"  FAIL:    {fail_c}")
    print(f"  WARN:    {warn_c}")
    print(f"  PENDING: {pending_c}")
    
    evaluator_stats = defaultdict(lambda: defaultdict(int))
    
    for item in result.get("review_items", []):
        evaluator = item.get("evaluator", "unknown")
        status = item.get("status", "unknown")
        evaluator_stats[evaluator][status] += 1
    
    print("\n按评估器分组:")
    for evaluator, status_counts in sorted(evaluator_stats.items()):
        print(f"  {evaluator}:")
        for status, count in sorted(status_counts.items()):
            print(f"    {status}: {count}")
    
    # 显示 out_of_scope 样例
    out_of_scope = [i for i in result.get("review_items", []) if i.get("evaluator") == "out_of_scope"]
    if out_of_scope:
        print(f"\n✅ 目标A验收: 发现 {len(out_of_scope)} 个过程性条款")
        for i, item in enumerate(out_of_scope[:5], 1):
            req_text = item.get("tender_requirement", "")
            print(f"  {i}. {req_text[:70]}")

asyncio.run(test())

