"""
清理Legacy Prompt模块
删除 project_info (legacy) 和 review (legacy) 两个已废弃的模块
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.db.postgres import get_pool


def cleanup_legacy_prompts():
    """清理Legacy Prompt数据"""
    pool = get_pool()
    
    print("开始清理Legacy Prompt模块...")
    print("-" * 60)
    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            # 1. 查询要删除的数据
            cur.execute("""
                SELECT id, module, name, version, is_active
                FROM prompt_templates
                WHERE module IN ('project_info', 'review')
                ORDER BY module, version
            """)
            rows = cur.fetchall()
            
            if rows:
                print(f"\n找到 {len(rows)} 条Legacy Prompt记录：")
                print("-" * 60)
                for row in rows:
                    print(f"  ID: {row[0]}")
                    print(f"  Module: {row[1]}")
                    print(f"  Name: {row[2]}")
                    print(f"  Version: {row[3]}")
                    print(f"  Active: {row[4]}")
                    print("-" * 60)
                
                # 确认删除
                confirm = input("\n确认删除这些记录？(yes/no): ").strip().lower()
                if confirm != 'yes':
                    print("取消删除操作")
                    return
                
                # 2. 删除prompt_history表中的相关记录
                print("\n正在删除历史记录...")
                cur.execute("""
                    DELETE FROM prompt_history
                    WHERE prompt_id IN (
                        SELECT id FROM prompt_templates
                        WHERE module IN ('project_info', 'review')
                    )
                """)
                deleted_history = cur.rowcount
                print(f"✓ 删除了 {deleted_history} 条历史记录")
                
                # 3. 删除prompt_templates表中的记录
                print("\n正在删除Prompt模板...")
                cur.execute("""
                    DELETE FROM prompt_templates
                    WHERE module IN ('project_info', 'review')
                """)
                deleted_templates = cur.rowcount
                print(f"✓ 删除了 {deleted_templates} 条Prompt模板记录")
                
                # 提交事务
                conn.commit()
                
                print("\n" + "=" * 60)
                print("✓ Legacy Prompt清理完成！")
                print("=" * 60)
                print(f"  删除的Prompt模板: {deleted_templates} 条")
                print(f"  删除的历史记录: {deleted_history} 条")
                print("=" * 60)
            else:
                print("\n未找到需要清理的Legacy Prompt记录")
                print("✓ 数据库已经是干净的状态")


if __name__ == "__main__":
    try:
        cleanup_legacy_prompts()
    except Exception as e:
        print(f"\n❌ 清理失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

