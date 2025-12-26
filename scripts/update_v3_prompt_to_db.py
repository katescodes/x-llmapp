#!/usr/bin/env python3
"""
更新数据库中的 V3 Prompt（六大类版本）

用途：
将更新后的 project_info_v3.md prompt 写入数据库的 prompt_templates 表

使用方法：
cd /aidata/x-llmapp1
python3 scripts/update_v3_prompt_to_db.py
"""

import sys
from pathlib import Path

# 添加 backend 到路径
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from psycopg_pool import ConnectionPool
from datetime import datetime


def update_v3_prompt():
    """更新 V3 prompt 到数据库"""
    
    # 读取 prompt 文件
    prompt_file = backend_dir / "app" / "works" / "tender" / "prompts" / "project_info_v3.md"
    
    if not prompt_file.exists():
        print(f"❌ Prompt 文件不存在: {prompt_file}")
        return False
    
    with open(prompt_file, 'r', encoding='utf-8') as f:
        prompt_content = f.read()
    
    print(f"✅ 已读取 prompt 文件: {len(prompt_content)} 字符")
    print(f"📄 文件路径: {prompt_file}")
    
    # 连接数据库
    try:
        pool = ConnectionPool("postgresql://localhost/x-llmapp1")
        print("✅ 数据库连接成功")
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False
    
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # 删除旧记录
                cur.execute("DELETE FROM prompt_templates WHERE module = 'project_info_v3'")
                deleted_count = cur.rowcount
                print(f"🗑️  删除旧记录: {deleted_count} 条")
                
                # 插入新记录
                cur.execute("""
                    INSERT INTO prompt_templates (
                        id, module, name, description, content, 
                        version, is_active, deprecated, created_at, updated_at
                    ) VALUES (
                        'prompt_project_info_v3_001',
                        'project_info_v3',
                        '招标信息提取 V3（六大类）',
                        '从招标文件中提取六大类结构化信息（项目概况【含范围、进度、保证金】、投标人资格、评审与评分、商务条款、技术要求、文件编制）',
                        %s,
                        1,
                        TRUE,
                        FALSE,
                        %s,
                        %s
                    )
                """, (prompt_content, datetime.now(), datetime.now()))
                
                conn.commit()
                print("✅ 新 prompt 已写入数据库")
                
                # 验证
                cur.execute("""
                    SELECT id, module, name, LENGTH(content), is_active, created_at
                    FROM prompt_templates 
                    WHERE module = 'project_info_v3'
                """)
                row = cur.fetchone()
                
                if row:
                    print("\n📊 验证结果：")
                    print(f"  ID: {row[0]}")
                    print(f"  模块: {row[1]}")
                    print(f"  名称: {row[2]}")
                    print(f"  内容长度: {row[3]} 字符")
                    print(f"  是否激活: {row[4]}")
                    print(f"  创建时间: {row[5]}")
                    return True
                else:
                    print("❌ 验证失败：未找到插入的记录")
                    return False
                    
    except Exception as e:
        print(f"❌ 数据库操作失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        pool.close()


if __name__ == "__main__":
    print("=" * 60)
    print("📝 更新数据库中的 V3 Prompt（六大类版本）")
    print("=" * 60)
    print()
    
    success = update_v3_prompt()
    
    print()
    print("=" * 60)
    if success:
        print("✅ 更新完成！")
        print()
        print("📌 下一步：")
        print("  1. 重启后端服务")
        print("  2. 打开前端 → 系统设置 → Prompt 管理")
        print("  3. 查看 'project_info_v3' 模块")
        print("  4. 验证内容为 '六大类' 版本")
        sys.exit(0)
    else:
        print("❌ 更新失败！")
        sys.exit(1)

