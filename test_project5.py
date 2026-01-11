#!/usr/bin/env python3
"""
测试"测试5"项目的目录生成
"""
import sys
import os
sys.path.insert(0, '/aidata/x-llmapp1/backend')

from app.db.connection import get_pool
from app.works.tender.directory_augment_v1 import augment_directory_from_tender_info_v3

def main():
    project_id = "tp_c7539ae635164ec8ab9c9b7e19d066db"
    
    print("=" * 80)
    print(f"测试项目: 测试5")
    print(f"Project ID: {project_id}")
    print("=" * 80)
    
    # 获取数据库连接池
    pool = get_pool()
    
    # 调用目录增强函数
    result = augment_directory_from_tender_info_v3(pool, project_id, {})
    
    print("\n" + "=" * 80)
    print("执行结果:")
    print("=" * 80)
    print(f"状态: {result['status']}")
    print(f"已增强节点数: {result['augmented_count']}")
    print(f"现有节点数: {result['existing_count']}")
    print(f"总节点数: {result['total_count']}")
    
    # 查询并显示目录结构
    print("\n" + "=" * 80)
    print("目录结构:")
    print("=" * 80)
    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
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
            
            if not rows:
                print("（暂无目录）")
            else:
                for row in rows:
                    numbering = row['numbering'] or ''
                    title = row['title']
                    level = row['level']
                    source = row['source'] or ''
                    order_no = row['order_no']
                    
                    # 根据层级缩进
                    indent = "  " * (level - 1)
                    
                    # 来源标记
                    source_mark = ""
                    if 'format_chapter_extracted' in source:
                        source_mark = " [规则提取]"
                    elif 'format_chapter_llm_extracted' in source:
                        source_mark = " [LLM提取]"
                    elif source == 'tender':
                        source_mark = " [原有LLM]"
                    
                    print(f"{order_no:3d}. {indent}{numbering} {title}{source_mark}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
