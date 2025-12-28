#!/usr/bin/env python3
"""
诊断投标响应抽取问题
"""
import sys
sys.path.insert(0, '/app')

import asyncio
from app.services.db.postgres import _get_pool

async def main():
    pool = _get_pool()
    project_id = "tp_3f49f66ead6d46e1bac3f0bd16a3efe9"
    bidder_name = "123"
    
    print("=" * 80)
    print("诊断投标响应抽取问题")
    print("=" * 80)
    
    # 1. 检查投标文件
    print("\n【1】检查投标文件:")
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    tpd.bidder_name,
                    d.id as doc_id,
                    d.title,
                    (SELECT COUNT(*) FROM doc_segments ds 
                     JOIN document_versions dv ON ds.doc_version_id = dv.id
                     WHERE dv.document_id = d.id) as segment_count
                FROM tender_project_docs tpd
                JOIN documents d ON tpd.kb_doc_id = d.id
                WHERE tpd.project_id = %s
                  AND tpd.doc_role = 'bid'
                  AND tpd.bidder_name = %s
            """, (project_id, bidder_name))
            rows = cur.fetchall()
            print(f"找到 {len(rows)} 个投标文件")
            for row in rows:
                print(f"  - {row[2]}: {row[3]} segments")
    
    # 2. 检查v2 prompt
    print("\n【2】检查v2 prompt:")
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, module, name, version, is_active, LENGTH(content) as len
                FROM prompt_templates
                WHERE module = 'bid_response'
                ORDER BY version DESC
            """)
            rows = cur.fetchall()
            for row in rows:
                print(f"  {row[0]}: v{row[3]}, active={row[4]}, len={row[5]}")
    
    # 3. 检查已抽取的响应
    print("\n【3】检查已抽取的响应:")
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT dimension, COUNT(*) as cnt
                FROM tender_bid_response_items
                WHERE project_id = %s AND bidder_name = %s
                GROUP BY dimension
                ORDER BY dimension
            """, (project_id, bidder_name))
            rows = cur.fetchall()
            total = sum(r[1] for r in rows)
            print(f"总计: {total} 条")
            for row in rows:
                print(f"  {row[0]}: {row[1]} 条")
    
    # 4. 检查检索配置
    print("\n【4】检查检索配置:")
    from app.works.tender.extraction_specs.bid_response_v2 import build_bid_response_spec_v2_async
    spec = await build_bid_response_spec_v2_async(pool)
    print(f"  Queries: {len(spec.queries)} 个")
    print(f"  TopK per query: {spec.topk_per_query}")
    print(f"  TopK total: {spec.topk_total}")
    print(f"  Doc types: {spec.doc_types}")
    for key, query in spec.queries.items():
        print(f"  - {key}: {query[:50]}...")
    
    # 5. 模拟检索
    print("\n【5】模拟检索 (qualification 维度):")
    from app.platform.retrieval.facade import RetrievalFacade
    from app.services.embedding_provider_store import get_embedding_store
    
    retriever = RetrievalFacade(pool)
    embedding_provider = get_embedding_store().get_default()
    
    result = await retriever.retrieve(
        kb_id=None,  # 会从 project_id 推导
        query_text=spec.queries["qualification"],
        top_k=20,
        embedding_provider=embedding_provider,
        project_id=project_id,
        doc_types=["bid"],
    )
    
    print(f"  检索到 {len(result.chunks)} 个 chunks")
    if result.chunks:
        print(f"  第一个chunk: doc_id={result.chunks[0].chunk_id[:30]}... score={result.chunks[0].score}")
    
    print("\n" + "=" * 80)
    print("诊断完成")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())

