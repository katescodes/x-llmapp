#!/usr/bin/env python3
"""最终测试所有chunks的范本识别"""
import sys
sys.path.insert(0, 'backend')

from backend.app.services.db.postgres import _get_pool
from psycopg.rows import tuple_row
from backend.app.works.tender.template_matcher import identify_potential_template
import psycopg

pool = _get_pool()

with pool.connection() as conn:
    with conn.cursor(row_factory=tuple_row) as cur:
        doc_version_id = 'dv_c4325dbab0104daa92ba2566d5622cdf'
        
        print('=' * 70)
        print('✅ 最终测试：所有chunks')
        print('=' * 70)
        
        cur.execute('''
            SELECT segment_no, id, content_text, meta_json
            FROM doc_segments
            WHERE doc_version_id = %s
            ORDER BY segment_no
        ''', [doc_version_id])
        
        chunks = cur.fetchall()
        identified = []
        
        for seg_no, chunk_id, content, meta_json in chunks:
            result = identify_potential_template(content, meta_json or {})
            
            if result:
                identified.append((seg_no, result))
                print(f'\n✅ Chunk {seg_no}: 分数={result["template_score"]}')
                print(f'   特征: {result["template_hints"]}')
                print(f'   预览: {content[:60]}...')
        
        print(f'\n{"=" * 70}')
        print(f'📊 最终识别结果')
        print(f'{"=" * 70}')
        print(f'总chunks: {len(chunks)}')
        print(f'识别为范本: {len(identified)}')
        print(f'识别chunks编号: {[seg_no for seg_no, _ in identified]}')
        
        # 更新数据库
        print(f'\n🔨 更新数据库...')
        for seg_no, chunk_id, content, meta_json in chunks:
            result = identify_potential_template(content, meta_json or {})
            
            if result:
                meta_json = meta_json or {}
                meta_json.update(result)
                
                cur.execute('''
                    UPDATE doc_segments
                    SET meta_json = %s
                    WHERE id = %s
                ''', [psycopg.types.json.Json(meta_json), chunk_id])
        
        conn.commit()
        print(f'✅ 数据库更新完成！')
        print(f'\n💡 现在可以在前端生成目录，查看范本自动填充效果')

