#!/usr/bin/env python3
"""
修复项目信息抽取状态

问题：某些项目在tender_runs中显示success，但tender_project_info中无数据或为空
解决：删除无效的tender_runs记录和空的tender_project_info记录
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.db.postgres import _get_pool

def main():
    pool = _get_pool()
    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            # 1. 查找有success run但无project_info数据的项目
            print("=== 检查项目信息抽取状态 ===\n")
            
            cur.execute("""
                SELECT 
                    tr.project_id,
                    tp.name as project_name,
                    tr.id as run_id,
                    tr.status,
                    tr.finished_at,
                    tpi.project_id IS NOT NULL as has_project_info,
                    CASE 
                        WHEN tpi.data_json IS NULL THEN 'NULL'
                        WHEN tpi.data_json = '{}'::jsonb THEN 'EMPTY'
                        WHEN jsonb_typeof(tpi.data_json) = 'object' AND jsonb_object_keys(tpi.data_json) IS NOT NULL THEN 'HAS_DATA'
                        ELSE 'UNKNOWN'
                    END as data_status
                FROM tender_runs tr
                JOIN tender_projects tp ON tr.project_id = tp.id
                LEFT JOIN tender_project_info tpi ON tr.project_id = tpi.project_id
                WHERE tr.kind = 'extract_project_info'
                  AND tr.status IN ('success', 'ok')
                ORDER BY tr.finished_at DESC
                LIMIT 20
            """)
            
            rows = cur.fetchall()
            
            if not rows:
                print("✅ 没有找到项目信息抽取记录\n")
                return
            
            print(f"找到 {len(rows)} 条项目信息抽取记录：\n")
            
            invalid_runs = []
            for row in rows:
                project_id = row['project_id']
                project_name = row['project_name']
                run_id = row['run_id']
                has_info = row['has_project_info']
                data_status = row['data_status']
                
                status_icon = "✅" if data_status == 'HAS_DATA' else "❌"
                print(f"{status_icon} {project_name[:20]:20s} | run: {run_id[:20]:20s} | has_info: {has_info} | data: {data_status}")
                
                # 标记无效的run（显示success但无数据）
                if data_status in ('NULL', 'EMPTY') or not has_info:
                    invalid_runs.append((run_id, project_id, project_name))
            
            print()
            
            if not invalid_runs:
                print("✅ 所有成功的抽取记录都有对应数据\n")
                return
            
            print(f"⚠️  发现 {len(invalid_runs)} 条无效记录（显示成功但无数据）\n")
            
            # 2. 询问是否删除
            print("是否删除这些无效记录? (y/N): ", end='', flush=True)
            confirm = input().strip().lower()
            
            if confirm != 'y':
                print("取消操作")
                return
            
            # 3. 删除无效的runs
            deleted_count = 0
            for run_id, project_id, project_name in invalid_runs:
                cur.execute("DELETE FROM tender_runs WHERE id = %s", (run_id,))
                print(f"  删除 run: {run_id} (项目: {project_name})")
                deleted_count += 1
            
            # 4. 删除空的project_info记录
            cur.execute("""
                DELETE FROM tender_project_info 
                WHERE data_json IS NULL OR data_json = '{}'::jsonb
                RETURNING project_id
            """)
            empty_info = cur.fetchall()
            
            if empty_info:
                print(f"\n删除 {len(empty_info)} 条空的project_info记录")
                for row in empty_info:
                    print(f"  - {row['project_id']}")
            
            conn.commit()
            
            print(f"\n✅ 完成！删除了 {deleted_count} 条无效run记录和 {len(empty_info)} 条空project_info记录\n")

if __name__ == "__main__":
    main()

