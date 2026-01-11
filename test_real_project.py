#!/usr/bin/env python3
"""
真实项目测试：使用数据库中的真实招标项目
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def main():
    from app.services.db.postgres import _get_pool
    from app.works.tender.directory_augment_v1 import augment_directory_from_tender_info_v3
    
    # 选择真实项目
    project_id = "tp_f379d279606a4ff89a6aa2cfabc0a6c5"  # 储能技术公司项目
    project_name = "储能技术公司金坛、刘庄储气库控制系统国产化升级改造工程施工项目"
    
    print(f"\n{'='*80}")
    print(f"真实项目测试")
    print(f"{'='*80}")
    print(f"项目ID: {project_id}")
    print(f"项目名称: {project_name}")
    
    pool = _get_pool()
    
    # 1. 查看现有目录
    print(f"\n📋 查询现有目录...")
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT numbering, title, level, source, order_no
                FROM tender_directory_nodes
                WHERE project_id = %s
                ORDER BY order_no
            """, (project_id,))
            
            existing = cur.fetchall()
            
            if existing:
                print(f"现有目录节点数: {len(existing)}")
                for i, row in enumerate(existing[:10], 1):
                    indent = "  " * (row['level'] - 1)
                    print(f"{i:2d}. {indent}[L{row['level']}] {row['numbering']} {row['title']}")
                if len(existing) > 10:
                    print(f"    ... 还有 {len(existing) - 10} 个节点")
            else:
                print("(无现有目录)")
    
    # 2. 执行增强
    print(f"\n🚀 执行目录增强...")
    print("-" * 80)
    
    try:
        result = augment_directory_from_tender_info_v3(
            project_id=project_id,
            pool=pool,
            tender_info=None
        )
        
        print(f"\n✅ 执行完成!")
        print(f"\n统计:")
        print(f"  - 现有节点: {result['existing_nodes_count']}")
        print(f"  - 识别新节点: {result['identified_required_count']}")
        print(f"  - 成功添加: {result['added_count']}")
        
        if result.get('error'):
            print(f"\n⚠️ 错误信息: {result['error']}")
        
        if result['added_count'] > 0:
            print(f"\n📝 新增节点标题:")
            for title in result['enhanced_titles']:
                print(f"  - {title}")
            
            # 3. 显示更新后的目录
            print(f"\n📋 更新后的完整目录:")
            print("-" * 80)
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT numbering, title, level, source
                        FROM tender_directory_nodes
                        WHERE project_id = %s
                        ORDER BY order_no
                    """, (project_id,))
                    
                    updated = cur.fetchall()
                    for i, row in enumerate(updated, 1):
                        indent = "  " * (row['level'] - 1)
                        source_tag = "🆕" if row['source'] == 'format_chapter_extracted' else ""
                        print(f"{i:2d}. {indent}[L{row['level']}] {row['numbering']} {row['title']} {source_tag}")
            
            print(f"\n✨ 目录总数: {len(existing)} → {len(updated)} (新增 {result['added_count']})")
        else:
            print(f"\n💡 提示: {result.get('enhanced_titles', ['没有新增节点'])}")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
