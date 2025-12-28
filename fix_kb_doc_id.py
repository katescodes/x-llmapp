#!/usr/bin/env python3
"""
修复已上传文件的 kb_doc_id
- 对于已经成功 ingest_v2 但 kb_doc_id 为空的文件
- 从 meta_json 的 doc_version_id 查询 document_id
- 更新 kb_doc_id
"""
import sys
sys.path.insert(0, '/app')

import asyncio
from app.services.db.postgres import _get_pool

async def main():
    pool = _get_pool()
    project_id = "tp_3f49f66ead6d46e1bac3f0bd16a3efe9"
    
    print("=" * 80)
    print("修复已上传文件的 kb_doc_id")
    print("=" * 80)
    
    # 查找需要修复的文件
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    id,
                    kind,
                    filename,
                    meta_json->>'doc_version_id' as doc_version_id,
                    meta_json->>'ingest_v2_segments' as segments
                FROM tender_project_assets
                WHERE project_id = %s
                  AND kb_doc_id IS NULL
                  AND meta_json->>'doc_version_id' IS NOT NULL
            """, (project_id,))
            assets_to_fix = cur.fetchall()
    
    print(f"\n找到 {len(assets_to_fix)} 个需要修复的文件:")
    
    fixed_count = 0
    for asset_id, kind, filename, doc_version_id, segments in assets_to_fix:
        print(f"\n处理: {kind} - {filename[:50]}...")
        print(f"  doc_version_id: {doc_version_id}")
        print(f"  segments: {segments}")
        
        # 从 doc_version_id 获取 document_id
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT document_id 
                    FROM document_versions 
                    WHERE id = %s
                """, (doc_version_id,))
                row = cur.fetchone()
                
                if row:
                    document_id = row[0]
                    print(f"  → 找到 document_id: {document_id}")
                    
                    # 更新 kb_doc_id
                    cur.execute("""
                        UPDATE tender_project_assets
                        SET kb_doc_id = %s
                        WHERE id = %s
                    """, (document_id, asset_id))
                    conn.commit()
                    
                    print(f"  ✅ 已更新 kb_doc_id")
                    fixed_count += 1
                else:
                    print(f"  ❌ 未找到对应的 document_id")
    
    print("\n" + "=" * 80)
    print(f"修复完成: {fixed_count}/{len(assets_to_fix)} 个文件")
    print("=" * 80)
    
    # 验证修复结果
    print("\n验证修复结果:")
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    kind,
                    COUNT(*) as total,
                    SUM(CASE WHEN kb_doc_id IS NOT NULL THEN 1 ELSE 0 END) as has_kb_doc
                FROM tender_project_assets
                WHERE project_id = %s
                GROUP BY kind
                ORDER BY kind
            """, (project_id,))
            results = cur.fetchall()
            
            for kind, total, has_kb_doc in results:
                status = "✅" if has_kb_doc == total else "⚠️"
                print(f"  {status} {kind}: {has_kb_doc}/{total} 有 kb_doc_id")

if __name__ == "__main__":
    asyncio.run(main())

