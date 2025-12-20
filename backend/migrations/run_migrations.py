#!/usr/bin/env python3
"""
数据库迁移脚本
运行所有 SQL 迁移文件
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.db.postgres import get_conn

def run_migrations():
    """执行所有迁移脚本"""
    migrations_dir = Path(__file__).parent
    sql_files = sorted(migrations_dir.glob("*.sql"))
    
    if not sql_files:
        print("❌ 未找到迁移文件")
        return
    
    print(f"📦 找到 {len(sql_files)} 个迁移文件")
    
    with get_conn() as conn:
        for sql_file in sql_files:
            print(f"\n🔄 执行迁移: {sql_file.name}")
            
            try:
                sql_content = sql_file.read_text(encoding='utf-8')
                
                # 分割多个语句执行
                with conn.cursor() as cur:
                    cur.execute(sql_content)
                
                conn.commit()
                print(f"   ✅ {sql_file.name} 执行成功")
                
            except Exception as e:
                print(f"   ❌ {sql_file.name} 执行失败: {e}")
                conn.rollback()
                raise
    
    print("\n🎉 所有迁移执行完成！")

if __name__ == "__main__":
    try:
        run_migrations()
    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        sys.exit(1)

