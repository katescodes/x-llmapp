#!/usr/bin/env python3
"""清空所有抽取状态"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.db.postgres import get_conn

with get_conn() as conn:
    with conn.cursor() as cur:
        print("=" * 80)
        print("检查当前抽取状态")
        print("=" * 80)
        
        # 1. 检查 tender_runs
        cur.execute("""
            SELECT id, project_id, run_type, status, progress, message
            FROM tender_runs
            WHERE status IN ('running', 'pending')
            ORDER BY started_at DESC
        """)
        runs = cur.fetchall()
        print(f"\n1. tender_runs 表中正在运行的任务: {len(runs)} 条")
        for r in runs[:10]:
            print(f"   - id: {r['id']}, project: {r['project_id']}, type: {r['run_type']}, status: {r['status']}, progress: {r['progress']}")
        
        # 2. 检查 platform_jobs
        cur.execute("""
            SELECT id, biz_type, biz_id, status, progress
            FROM platform_jobs
            WHERE status IN ('running', 'pending')
            ORDER BY created_at DESC
        """)
        jobs = cur.fetchall()
        print(f"\n2. platform_jobs 表中正在运行的任务: {len(jobs)} 条")
        for j in jobs[:10]:
            print(f"   - id: {j['id']}, biz_type: {j['biz_type']}, biz_id: {j['biz_id']}, status: {j['status']}, progress: {j['progress']}")
        
        print("\n" + "=" * 80)
        print("开始清空抽取状态")
        print("=" * 80)
        
        # 3. 更新 tender_runs
        cur.execute("""
            UPDATE tender_runs
            SET status = 'failed',
                message = '任务已被手动取消',
                finished_at = CURRENT_TIMESTAMP
            WHERE status IN ('running', 'pending')
            RETURNING id, project_id, run_type
        """)
        updated_runs = cur.fetchall()
        print(f"\n✅ 已取消 {len(updated_runs)} 个 tender_runs 任务")
        for r in updated_runs[:10]:
            print(f"   - {r['id']} ({r['run_type']})")
        
        # 4. 更新 platform_jobs
        cur.execute("""
            UPDATE platform_jobs
            SET status = 'failed',
                message = '任务已被手动取消',
                updated_at = CURRENT_TIMESTAMP
            WHERE status IN ('running', 'pending')
            RETURNING id, biz_type, biz_id
        """)
        updated_jobs = cur.fetchall()
        print(f"\n✅ 已取消 {len(updated_jobs)} 个 platform_jobs 任务")
        for j in updated_jobs[:10]:
            print(f"   - {j['id']} (biz_type: {j['biz_type']}, biz_id: {j['biz_id']})")
        
        conn.commit()
        
        print("\n" + "=" * 80)
        print("✅ 所有抽取状态已清空")
        print("=" * 80)

