#!/usr/bin/env python3
"""
实际项目测试：从数据库选择项目，测试目录提取功能
"""
import sys
import os
import json

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def list_projects():
    """列出数据库中的项目"""
    from app.services.db.postgres import _get_pool
    
    pool = _get_pool()
    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    p.id, 
                    p.name, 
                    p.kb_id,
                    p.created_at,
                    COUNT(d.id) as doc_count
                FROM tender_projects p
                LEFT JOIN kb_documents d ON d.kb_id = p.kb_id
                WHERE p.kb_id IS NOT NULL
                GROUP BY p.id, p.name, p.kb_id, p.created_at
                ORDER BY p.created_at DESC
                LIMIT 10
            """)
            
            rows = cur.fetchall()
            return [dict(row) for row in rows]


def get_project_documents(project_id):
    """获取项目的文档信息"""
    from app.services.db.postgres import _get_pool
    
    pool = _get_pool()
    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            # 获取kb_id
            cur.execute("SELECT kb_id FROM tender_projects WHERE id = %s", (project_id,))
            row = cur.fetchone()
            if not row:
                return []
            
            kb_id = row['kb_id']
            
            # 获取文档列表
            cur.execute("""
                SELECT 
                    id, 
                    filename, 
                    file_path,
                    created_at
                FROM kb_documents
                WHERE kb_id = %s
                ORDER BY created_at DESC
            """, (kb_id,))
            
            rows = cur.fetchall()
            return [dict(row) for row in rows]


def get_existing_directory(project_id):
    """获取现有目录"""
    from app.services.db.postgres import _get_pool
    
    pool = _get_pool()
    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    id,
                    numbering,
                    title,
                    level,
                    source,
                    order_no
                FROM tender_directory_nodes
                WHERE project_id = %s
                ORDER BY order_no
            """, (project_id,))
            
            rows = cur.fetchall()
            return [dict(row) for row in rows]


def test_directory_extraction(project_id):
    """测试目录提取"""
    print(f"\n{'='*80}")
    print(f"开始测试项目: {project_id}")
    print(f"{'='*80}\n")
    
    from app.services.db.postgres import _get_pool
    from app.works.tender.directory_augment_v1 import augment_directory_from_tender_info_v3
    
    pool = _get_pool()
    
    # 1. 显示现有目录
    print("📋 现有目录节点:")
    print("-" * 80)
    existing_nodes = get_existing_directory(project_id)
    if existing_nodes:
        for i, node in enumerate(existing_nodes[:20], 1):
            indent = "  " * (node['level'] - 1)
            print(f"{i:2d}. {indent}[L{node['level']}] {node['numbering']} {node['title']}")
            if i == 20 and len(existing_nodes) > 20:
                print(f"    ... 还有 {len(existing_nodes) - 20} 个节点")
    else:
        print("  (无现有节点)")
    
    print(f"\n现有节点总数: {len(existing_nodes)}")
    
    # 2. 显示项目文档
    print(f"\n📁 项目文档:")
    print("-" * 80)
    docs = get_project_documents(project_id)
    if docs:
        for i, doc in enumerate(docs, 1):
            path_display = doc['file_path'][:60] + "..." if doc['file_path'] and len(doc['file_path']) > 60 else doc['file_path']
            print(f"{i}. {doc['filename']}")
            print(f"   路径: {path_display}")
    else:
        print("  (无文档)")
    
    print(f"\n文档总数: {len(docs)}")
    
    # 3. 执行目录增强
    print(f"\n🚀 执行目录增强...")
    print("-" * 80)
    
    try:
        result = augment_directory_from_tender_info_v3(
            project_id=project_id,
            pool=pool,
            tender_info=None  # 使用新逻辑，不需要tender_info
        )
        
        print("\n✅ 执行完成!")
        print(f"\n结果统计:")
        print(f"  - 现有节点数: {result['existing_nodes_count']}")
        print(f"  - 识别到的新节点数: {result['identified_required_count']}")
        print(f"  - 成功添加的节点数: {result['added_count']}")
        
        if result.get('enhanced_titles'):
            print(f"\n📝 新增的节点标题:")
            for i, title in enumerate(result['enhanced_titles'], 1):
                print(f"  {i}. {title}")
        
        # 4. 显示更新后的目录
        print(f"\n📋 更新后的完整目录:")
        print("-" * 80)
        updated_nodes = get_existing_directory(project_id)
        
        if updated_nodes:
            for i, node in enumerate(updated_nodes, 1):
                indent = "  " * (node['level'] - 1)
                source_tag = f"[{node['source']}]" if node['source'] == 'format_chapter_extracted' else ""
                print(f"{i:2d}. {indent}[L{node['level']}] {node['numbering']} {node['title']} {source_tag}")
        
        print(f"\n✨ 目录节点总数: {len(existing_nodes)} → {len(updated_nodes)} (新增 {len(updated_nodes) - len(existing_nodes)})")
        
        return result
        
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """主函数"""
    print("\n🔍 查询数据库中的项目...")
    
    try:
        projects = list_projects()
        
        if not projects:
            print("\n❌ 数据库中没有找到项目")
            return 1
        
        print(f"\n找到 {len(projects)} 个项目:\n")
        
        for i, proj in enumerate(projects, 1):
            print(f"{i}. [{proj['id']}] {proj['name']}")
            print(f"   知识库: {proj['kb_id']}, 文档数: {proj['doc_count']}, 创建: {proj['created_at']}")
        
        # 选择第一个有文档的项目
        selected_project = None
        for proj in projects:
            if proj['doc_count'] > 0:
                selected_project = proj
                break
        
        if not selected_project:
            print("\n⚠️ 没有找到包含文档的项目")
            return 1
        
        print(f"\n✅ 选择项目: [{selected_project['id']}] {selected_project['name']}")
        
        # 执行测试
        result = test_directory_extraction(selected_project['id'])
        
        if result:
            print(f"\n{'='*80}")
            print("🎉 测试完成!")
            print(f"{'='*80}\n")
            return 0
        else:
            return 1
            
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
