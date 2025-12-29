#!/usr/bin/env python3
"""
抽取项目的投标响应数据 (bid_response_items)
使用方式: python scripts/extract_bid_responses.py <project_id> <bidder_name>
"""
import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.db.postgres import _get_pool
from app.services.llm.llm_orchestrator_service import get_llm_orchestrator
from app.platform.extraction.engine import ExtractionEngine
from app.platform.retrieval.facade import RetrievalFacade
from app.works.tender.bid_response_service import BidResponseService


async def main():
    if len(sys.argv) < 3:
        print("使用方式: python scripts/extract_bid_responses.py <project_id> <bidder_name>")
        print("例如: python scripts/extract_bid_responses.py tp_xxx 投标人A")
        sys.exit(1)
    
    project_id = sys.argv[1]
    bidder_name = sys.argv[2]
    
    print(f"开始抽取投标响应数据...")
    print(f"  项目ID: {project_id}")
    print(f"  投标人: {bidder_name}")
    
    # 获取依赖
    pool = _get_pool()
    llm = get_llm_orchestrator()
    engine = ExtractionEngine()
    retriever = RetrievalFacade(pool)
    
    # 创建服务
    service = BidResponseService(
        pool=pool,
        engine=engine,
        retriever=retriever,
        llm=llm
    )
    
    # 执行抽取
    try:
        result = await service.extract_bid_response(
            project_id=project_id,
            bidder_name=bidder_name,
            model_id=None,  # 使用默认模型
            run_id=None
        )
        
        print(f"\n抽取完成!")
        print(f"  投标人: {result.get('bidder_name', bidder_name)}")
        print(f"  响应条目数: {result.get('added_count', 0)}")
        print(f"  Schema版本: {result.get('schema_version', 'v2')}")
        
        # 显示前几条
        responses = result.get('responses', [])
        if responses:
            print(f"\n前3条响应:")
            for i, resp in enumerate(responses[:3], 1):
                print(f"  {i}. {resp.get('dimension', 'N/A')}: {resp.get('response_text', 'N/A')[:50]}...")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ 抽取失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

