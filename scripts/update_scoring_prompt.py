#!/usr/bin/env python3
"""
更新数据库中的project_info Prompt（评分标准优化版）
"""
import sys
import os
import uuid
from datetime import datetime

# 添加项目路径
sys.path.insert(0, '/app')

import psycopg
from psycopg.rows import dict_row

# 数据库配置
DB_CONFIG = {
    "host": "postgres",
    "port": 5432,
    "dbname": "localgpt",
    "user": "localgpt",
    "password": "localgpt123",
}

def read_prompt_file():
    """读取Prompt文件"""
    prompt_file = "/app/app/works/tender/prompts/project_info_v2.md"
    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read().strip()

def update_prompt():
    """更新数据库中的Prompt"""
    try:
        # 读取Prompt内容
        prompt_content = read_prompt_file()
        print(f"✅ 读取Prompt文件成功，长度: {len(prompt_content)} 字符")
        
        # 连接数据库
        conn_str = f"host={DB_CONFIG['host']} port={DB_CONFIG['port']} dbname={DB_CONFIG['dbname']} user={DB_CONFIG['user']} password={DB_CONFIG['password']}"
        with psycopg.connect(conn_str, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                # 1. 查看当前active的prompt
                cur.execute("""
                    SELECT id, name, version, is_active, char_length(content) as content_len
                    FROM prompt_templates
                    WHERE module = 'project_info'
                    ORDER BY version DESC
                    LIMIT 5
                """)
                existing = cur.fetchall()
                
                print("\n📋 当前project_info模块的Prompt:")
                for row in existing:
                    active_mark = "✅" if row['is_active'] else "  "
                    print(f"{active_mark} ID: {row['id'][:8]}... | Name: {row['name']:<40} | Version: {row['version']} | Length: {row['content_len']}")
                
                # 2. 找到当前最大版本号
                cur.execute("""
                    SELECT MAX(version) as max_version
                    FROM prompt_templates
                    WHERE module = 'project_info'
                """)
                result = cur.fetchone()
                max_version = result['max_version'] if result and result['max_version'] else 0
                new_version = max_version + 1
                
                print(f"\n📌 新版本号: {new_version}")
                
                # 3. 将现有的active prompt设置为inactive
                cur.execute("""
                    UPDATE prompt_templates
                    SET is_active = FALSE
                    WHERE module = 'project_info' AND is_active = TRUE
                """)
                print(f"✅ 已将现有active prompt设置为inactive")
                
                # 4. 插入新的prompt（设置为active）
                new_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO prompt_templates (id, module, name, content, version, is_active, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    new_id,
                    "project_info",
                    f"项目信息抽取v{new_version}（评分表优化-完整性优先）",
                    prompt_content,
                    new_version,
                    True,
                    "system"
                ))
                
                conn.commit()
                
                print(f"\n✅ 成功插入新Prompt:")
                print(f"   ID: {new_id}")
                print(f"   Module: project_info")
                print(f"   Name: 项目信息抽取v{new_version}（评分表优化-完整性优先）")
                print(f"   Version: {new_version}")
                print(f"   Length: {len(prompt_content)} 字符")
                print(f"   Status: ACTIVE ✅")
                
                # 5. 记录到history表
                cur.execute("""
                    INSERT INTO prompt_history (id, template_id, content, changed_by, change_note)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    str(uuid.uuid4()),
                    new_id,
                    prompt_content,
                    "system",
                    "评分标准抽取优化：1) 扩展评分查询词 2) 增强Prompt完整性要求 3) 增加自检步骤 4) 提供详细示例"
                ))
                
                conn.commit()
                print(f"✅ 已记录到prompt_history")
                
                print("\n" + "="*80)
                print("🎉 数据库Prompt更新完成！")
                print("="*80)
                
                # 6. 验证
                cur.execute("""
                    SELECT id, name, version, is_active, char_length(content) as content_len
                    FROM prompt_templates
                    WHERE module = 'project_info'
                    ORDER BY version DESC
                    LIMIT 3
                """)
                updated = cur.fetchall()
                
                print("\n📋 更新后的Prompt列表:")
                for row in updated:
                    active_mark = "✅" if row['is_active'] else "  "
                    print(f"{active_mark} ID: {row['id'][:8]}... | Name: {row['name']:<40} | Version: {row['version']} | Length: {row['content_len']}")
                
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    update_prompt()
