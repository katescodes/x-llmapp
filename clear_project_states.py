"""
清除所有项目的状态数据

清除内容：
- tender_runs（运行状态）
- tender_requirements（招标要求）
- tender_bid_response_items（投标响应）
- tender_review_items（审核结果）
- tender_projects.meta_json 中的提取结果

保留内容：
- tender_projects（项目）
- tender_project_assets（上传的文件）

用法：
  python clear_project_states.py           # 交互式确认
  python clear_project_states.py --force   # 自动确认
"""
import psycopg
from psycopg.rows import dict_row
import sys

# 数据库连接（从Docker内部连接）
DB_CONFIG = {
    "host": "postgres",
    "port": 5432,
    "dbname": "localgpt",
    "user": "localgpt",
    "password": "localgpt"
}

def main():
    print("="*60)
    print("清除所有项目的状态数据")
    print("="*60)
    
    conn = psycopg.connect(**DB_CONFIG)
    cur = conn.cursor(row_factory=dict_row)
    
    try:
        # 1. 统计当前数据
        print("\n📊 当前数据统计：")
        
        cur.execute("SELECT COUNT(*) as count FROM tender_projects")
        project_count = cur.fetchone()['count']
        print(f"   项目数: {project_count}")
        
        cur.execute("SELECT COUNT(*) as count FROM tender_project_assets")
        asset_count = cur.fetchone()['count']
        print(f"   文件数: {asset_count}")
        
        cur.execute("SELECT COUNT(*) as count FROM tender_runs")
        run_count = cur.fetchone()['count']
        print(f"   运行记录数: {run_count}")
        
        cur.execute("SELECT COUNT(*) as count FROM tender_requirements")
        req_count = cur.fetchone()['count']
        print(f"   招标要求数: {req_count}")
        
        cur.execute("SELECT COUNT(*) as count FROM tender_bid_response_items")
        response_count = cur.fetchone()['count']
        print(f"   投标响应数: {response_count}")
        
        cur.execute("SELECT COUNT(*) as count FROM tender_review_items")
        review_count = cur.fetchone()['count']
        print(f"   审核结果数: {review_count}")
        
        # 2. 确认清除
        print(f"\n⚠️  即将清除以下数据：")
        print(f"   - {run_count} 条运行记录")
        print(f"   - {req_count} 条招标要求")
        print(f"   - {response_count} 条投标响应")
        print(f"   - {review_count} 条审核结果")
        print(f"   - 项目元数据中的提取结果")
        print(f"\n✅ 保留：")
        print(f"   - {project_count} 个项目")
        print(f"   - {asset_count} 个文件")
        
        # 检查是否有 --force 参数
        force = '--force' in sys.argv
        if not force:
            confirm = input("\n❓ 确认清除？(输入 yes 继续): ")
            if confirm.lower() != 'yes':
                print("❌ 已取消")
                return
        else:
            print("\n✅ 使用 --force 参数，自动确认")
        
        # 3. 开始清除
        print("\n🗑️  开始清除...")
        
        # 清除运行记录
        cur.execute("DELETE FROM tender_runs")
        deleted_runs = cur.rowcount
        print(f"   ✅ 清除 {deleted_runs} 条运行记录")
        
        # 清除审核结果
        cur.execute("DELETE FROM tender_review_items")
        deleted_reviews = cur.rowcount
        print(f"   ✅ 清除 {deleted_reviews} 条审核结果")
        
        # 清除投标响应
        cur.execute("DELETE FROM tender_bid_response_items")
        deleted_responses = cur.rowcount
        print(f"   ✅ 清除 {deleted_responses} 条投标响应")
        
        # 清除招标要求
        cur.execute("DELETE FROM tender_requirements")
        deleted_reqs = cur.rowcount
        print(f"   ✅ 清除 {deleted_reqs} 条招标要求")
        
        # 清除项目元数据中的提取结果
        cur.execute("""
            UPDATE tender_projects 
            SET meta_json = '{}'::jsonb
            WHERE meta_json IS NOT NULL
        """)
        cleared_meta = cur.rowcount
        print(f"   ✅ 清除 {cleared_meta} 个项目的元数据")
        
        # 提交事务
        conn.commit()
        
        print("\n" + "="*60)
        print("✅ 清除完成！")
        print("="*60)
        print(f"\n保留了 {project_count} 个项目和 {asset_count} 个文件")
        print("您可以重新提取招标要求和进行审核。")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ 清除失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()

