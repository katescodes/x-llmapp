#!/usr/bin/env python3
"""
运行单个迁移：用户-企业多对多关系
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.db.postgres import get_conn

def run_migration():
    """执行046迁移"""
    migrations_dir = Path(__file__).parent
    sql_file = migrations_dir / "046_create_user_organization_mapping.sql"
    
    if not sql_file.exists():
        print(f"❌ 迁移文件不存在: {sql_file}")
        return
    
    print(f"📦 执行迁移: {sql_file.name}")
    
    try:
        with get_conn() as conn:
            sql_content = sql_file.read_text(encoding='utf-8')
            
            with conn.cursor() as cur:
                cur.execute(sql_content)
            
            conn.commit()
            print(f"✅ {sql_file.name} 执行成功")
            
    except Exception as e:
        print(f"❌ {sql_file.name} 执行失败: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    try:
        run_migration()
        print("\n🎉 迁移完成！")
    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        sys.exit(1)
