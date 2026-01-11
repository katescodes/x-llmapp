#!/usr/bin/env python3
"""
实际运行测试：从招标文件提取目录并插入数据库
"""
import sys
sys.path.insert(0, '/aidata/x-llmapp1/backend')

def main():
    from app.services.db.postgres import _get_pool
    from app.works.tender.directory_augment_v1 import augment_directory_from_tender_info_v3
    
    project_id = "tp_3f49f66ead6d46e1bac3f0bd16a3efe9"  # 测试4项目
    
    print("="*80)
    print("实际运行测试：从招标文件提取目录")
    print("="*80)
    print(f"项目ID: {project_id}")
    print(f"项目名称: 测试4（含山县供水改造工程）")
    
    pool = _get_pool()
    
    # 查看执行前的目录
    print("\n📋 执行前的目录节点数:")
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) as cnt FROM tender_directory_nodes 
                WHERE project_id = %s
            """, (project_id,))
            before_count = cur.fetchone()['cnt']
            print(f"  现有节点: {before_count} 个")
    
    # 执行目录增强
    print("\n🚀 开始执行 augment_directory_from_tender_info_v3()...")
    print("-"*80)
    
    result = augment_directory_from_tender_info_v3(
        project_id=project_id,
        pool=pool,
        tender_info=None
    )
    
    print("\n✅ 执行完成!")
    print("="*80)
    print("📊 执行结果:")
    print(f"  - 执行前节点数: {result['existing_nodes_count']}")
    print(f"  - 识别到新节点: {result['identified_required_count']}")
    print(f"  - 成功添加节点: {result['added_count']}")
    
    if result.get('error'):
        print(f"\n⚠️ 错误: {result['error']}")
    
    if result['added_count'] > 0:
        print(f"\n📝 新增的节点标题:")
        for i, title in enumerate(result['enhanced_titles'], 1):
            print(f"  {i}. {title}")
        
        # 显示新增节点的详细信息
        print(f"\n💾 新增节点详情:")
        print("-"*80)
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT numbering, title, level, source, evidence_chunk_ids
                    FROM tender_directory_nodes
                    WHERE project_id = %s AND source = 'format_chapter_extracted'
                    ORDER BY order_no
                    LIMIT 20
                """, (project_id,))
                
                new_nodes = cur.fetchall()
                if new_nodes:
                    for node in new_nodes:
                        indent = "  " * (node['level'] - 1)
                        print(f"[L{node['level']}] {indent}{node['numbering']} {node['title']}")
                        print(f"      证据: {node['evidence_chunk_ids'][:2] if node['evidence_chunk_ids'] else []}")
    else:
        print("\n💡 说明:")
        if result['identified_required_count'] == 0:
            print("  - 未定位到格式章节，或章节为空")
            print("  - 可能原因：招标文件无标准格式章节，或文档路径不存在")
        else:
            print("  - 识别到节点但都已存在，未添加重复节点")
    
    # 显示完整目录
    print(f"\n📋 最终完整目录:")
    print("="*80)
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT numbering, title, level, source
                FROM tender_directory_nodes
                WHERE project_id = %s
                ORDER BY order_no
            """, (project_id,))
            
            all_nodes = cur.fetchall()
            for i, node in enumerate(all_nodes, 1):
                indent = "  " * (node['level'] - 1)
                source_tag = " 🆕[格式章节]" if node['source'] == 'format_chapter_extracted' else ""
                print(f"{i:2d}. {indent}[L{node['level']}] {node['numbering']} {node['title']}{source_tag}")
    
    print(f"\n✨ 总节点数: {before_count} → {len(all_nodes)} (新增 {result['added_count']})")
    print("="*80)
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n❌ 程序异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
