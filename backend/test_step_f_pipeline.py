#!/usr/bin/env python3
"""
Step F: 验收测试 - 统一 evidence_json 结构（直接测试 pipeline）
"""
import sys
import os
import asyncio

# 添加后端路径
sys.path.insert(0, "/aidata/x-llmapp1/backend")

from app.works.tender.review_pipeline_v3 import ReviewPipelineV3
from psycopg_pool import ConnectionPool

# 使用已有项目
PROJECT_ID = "tp_3f49f66ead6d46e1bac3f0bd16a3efe9"
BIDDER_NAME = "123"


async def test_pipeline():
    """测试 pipeline"""
    print("=" * 60)
    print("Step F: 统一 evidence_json 结构（role=tender/bid）")
    print("=" * 60)
    
    # 创建数据库连接池
    pool = ConnectionPool(
        "postgresql://localgpt:localgpt@postgres:5432/localgpt",
        min_size=1,
        max_size=5
    )
    
    # 创建 pipeline（不需要 llm 参数）
    pipeline = ReviewPipelineV3(pool=pool)
    
    print(f"\n=== 运行 Pipeline ===")
    print(f"  - Project: {PROJECT_ID}")
    print(f"  - Bidder: {BIDDER_NAME}")
    
    # 运行 pipeline
    result = await pipeline.run_pipeline(
        project_id=PROJECT_ID,
        bidder_name=BIDDER_NAME,
        use_llm_semantic=False
    )
    
    # 分析结果
    review_items = result.get("review_items", [])
    stats = result.get("stats", {})
    
    print(f"\n📊 Pipeline 结果:")
    print(f"  - 总审核项: {len(review_items)}")
    print(f"  - 统计: {stats}")
    
    # 检查 evidence_json 结构
    print(f"\n📝 Evidence 结构检查:")
    
    has_tender_role = 0
    has_bid_role = 0
    has_both_roles = 0
    has_tender_ids = 0
    has_bid_ids = 0
    
    for item in review_items:
        evidence_json = item.get("evidence_json", [])
        tender_ids = item.get("tender_evidence_chunk_ids", [])
        bid_ids = item.get("bid_evidence_chunk_ids", [])
        
        # 检查 role
        has_tender = any(ev.get("role") == "tender" for ev in evidence_json if isinstance(ev, dict))
        has_bid = any(ev.get("role") == "bid" for ev in evidence_json if isinstance(ev, dict))
        
        if has_tender:
            has_tender_role += 1
        if has_bid:
            has_bid_role += 1
        if has_tender and has_bid:
            has_both_roles += 1
        
        if tender_ids:
            has_tender_ids += 1
        if bid_ids:
            has_bid_ids += 1
    
    print(f"  - 包含 role=tender 的 evidence: {has_tender_role}/{len(review_items)}")
    print(f"  - 包含 role=bid 的 evidence: {has_bid_role}/{len(review_items)}")
    print(f"  - 同时包含 tender 和 bid: {has_both_roles}/{len(review_items)}")
    print(f"  - tender_evidence_chunk_ids 非空: {has_tender_ids}/{len(review_items)}")
    print(f"  - bid_evidence_chunk_ids 非空: {has_bid_ids}/{len(review_items)}")
    
    # 抽样展示
    print(f"\n📄 抽样展示 (前3条):")
    for i, item in enumerate(review_items[:3], 1):
        evidence_json = item.get("evidence_json", [])
        tender_ids = item.get("tender_evidence_chunk_ids", [])
        bid_ids = item.get("bid_evidence_chunk_ids", [])
        
        print(f"\n  [{i}] {item.get('clause_title', '')[:40]}...")
        print(f"      evaluator: {item.get('evaluator')}")
        print(f"      evidence count: {len(evidence_json)}")
        print(f"      tender_ids: {len(tender_ids)}")
        print(f"      bid_ids: {len(bid_ids)}")
        
        # 展示前2条 evidence
        for j, ev in enumerate(evidence_json[:2], 1):
            if isinstance(ev, dict):
                print(f"        [{j}] role={ev.get('role')}, source={ev.get('source')}, page={ev.get('page_start')}")
                quote = ev.get('quote', '')
                if quote:
                    print(f"            quote: {quote[:60]}...")
    
    # 验收判定
    print(f"\n✅ 验收结果:")
    
    passed = True
    
    # 指标1: evidence_json 包含 role 字段
    if has_tender_role > 0 or has_bid_role > 0:
        print(f"  ✅ 指标1: evidence_json 包含 role 字段 (tender: {has_tender_role}, bid: {has_bid_role})")
    else:
        print(f"  ❌ 指标1: evidence_json 缺少 role 字段")
        passed = False
    
    # 指标2: 至少有部分同时包含 tender 和 bid
    if has_both_roles > 0:
        print(f"  ✅ 指标2: {has_both_roles} 条审核项同时包含 tender 和 bid evidence")
    else:
        print(f"  ⚠️  指标2: 没有同时包含 tender 和 bid 的 evidence（可能是数据特性）")
    
    # 指标3: chunk_ids 不全是空数组
    if has_tender_ids > 0 or has_bid_ids > 0:
        print(f"  ✅ 指标3: tender/bid_evidence_chunk_ids 不再全是空数组 (tender: {has_tender_ids}, bid: {has_bid_ids})")
    else:
        print(f"  ❌ 指标3: tender/bid_evidence_chunk_ids 全是空数组")
        passed = False
    
    pool.close()
    
    if passed:
        print("\n" + "="*60)
        print("🎉 Step F 验收通过！")
        print("="*60)
        return 0
    else:
        print("\n" + "="*60)
        print("❌ Step F 验收未通过")
        print("="*60)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(test_pipeline())
    sys.exit(exit_code)

