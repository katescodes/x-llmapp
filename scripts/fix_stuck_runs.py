#!/usr/bin/env python3
"""
修复卡死的任务运行状态

问题场景：
1. 后台任务异常退出（OOM、容器重启等），但数据库状态未更新
2. 前端轮询一直显示"提取中"，但后台已无进程运行
3. 用户无法进行后续操作

解决方案：
- 检测所有 running 状态但超过阈值时间的任务
- 自动更新为 failed 状态，并标注原因
- 可选择手动运行或定时任务运行
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import psycopg
from psycopg.rows import dict_row


def get_db_connection():
    """获取数据库连接"""
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "localgpt"),
        user=os.getenv("POSTGRES_USER", "localgpt"),
        password=os.getenv("POSTGRES_PASSWORD", "localgpt"),
        row_factory=dict_row
    )


def find_stuck_runs(conn, timeout_minutes: int = 10):
    """
    查找卡死的任务
    
    Args:
        conn: 数据库连接
        timeout_minutes: 超时阈值（分钟），超过此时间仍为running的任务视为卡死
    
    Returns:
        List[Dict]: 卡死的任务列表
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                id, project_id, kind, status, progress, message,
                started_at,
                EXTRACT(EPOCH FROM (NOW() - started_at)) / 60 as running_minutes
            FROM tender_runs
            WHERE status = 'running'
              AND started_at < NOW() - INTERVAL '%s minutes'
            ORDER BY started_at ASC
        """, (timeout_minutes,))
        
        return cur.fetchall()


def fix_stuck_run(conn, run_id: str, dry_run: bool = False):
    """
    修复单个卡死的任务
    
    Args:
        conn: 数据库连接
        run_id: 任务ID
        dry_run: 是否仅模拟运行
    """
    if dry_run:
        print(f"  [DRY-RUN] 将更新任务 {run_id} 为 failed 状态")
        return
    
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE tender_runs
            SET status = 'failed',
                finished_at = NOW(),
                error = '任务超时未完成（后台进程可能已退出）',
                message = '任务异常终止：超时未完成'
            WHERE id = %s
        """, (run_id,))
        conn.commit()
        print(f"  ✅ 已修复任务 {run_id}")


def main():
    parser = argparse.ArgumentParser(description="修复卡死的任务运行状态")
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="超时阈值（分钟），默认10分钟"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅检测，不实际修复"
    )
    parser.add_argument(
        "--auto-fix",
        action="store_true",
        help="自动修复所有卡死任务"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🔧 卡死任务修复工具")
    print("=" * 60)
    print(f"超时阈值: {args.timeout} 分钟")
    print(f"模式: {'仅检测' if args.dry_run else '修复模式'}")
    print()
    
    try:
        conn = get_db_connection()
        print("✅ 数据库连接成功")
        
        # 查找卡死的任务
        print(f"\n🔍 查找超过 {args.timeout} 分钟的 running 任务...")
        stuck_runs = find_stuck_runs(conn, args.timeout)
        
        if not stuck_runs:
            print("✅ 未发现卡死的任务")
            return
        
        print(f"\n⚠️  发现 {len(stuck_runs)} 个卡死的任务：\n")
        
        for run in stuck_runs:
            print(f"任务ID: {run['id']}")
            print(f"  项目: {run['project_id']}")
            print(f"  类型: {run['kind']}")
            print(f"  消息: {run['message']}")
            print(f"  开始时间: {run['started_at']}")
            print(f"  运行时长: {run['running_minutes']:.1f} 分钟")
            print()
        
        # 修复逻辑
        if args.dry_run:
            print("💡 提示：使用 --auto-fix 参数可自动修复这些任务")
        elif args.auto_fix:
            print("🔧 开始修复...\n")
            for run in stuck_runs:
                fix_stuck_run(conn, run['id'], dry_run=False)
            print(f"\n✅ 已修复 {len(stuck_runs)} 个任务")
        else:
            # 交互式确认
            answer = input("\n是否修复这些任务？(y/n): ")
            if answer.lower() == 'y':
                print("\n🔧 开始修复...\n")
                for run in stuck_runs:
                    fix_stuck_run(conn, run['id'], dry_run=False)
                print(f"\n✅ 已修复 {len(stuck_runs)} 个任务")
            else:
                print("❌ 取消修复")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()





