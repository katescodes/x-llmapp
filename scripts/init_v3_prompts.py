"""
初始化 V3 Prompt 模板到数据库

将新增的三个 prompt 模板插入到 prompt_templates 表
"""
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.db.postgres import _get_pool


def init_v3_prompts():
    """初始化 V3 prompt 模板"""
    pool = _get_pool()
    
    # 定义三个新 prompt
    prompts = [
        {
            "id": "prompt_project_info_v3_001",
            "module": "project_info_v3",
            "name": "招标信息提取 V3",
            "description": "从招标文件中提取九大类结构化信息（项目概况、范围与标段、进度与提交、投标人资格、评审与评分、商务条款、技术要求、文件编制、投标保证金）",
            "file_path": "backend/app/works/tender/prompts/project_info_v3.md"
        },
        {
            "id": "prompt_requirements_v1_001",
            "module": "requirements_v1",
            "name": "招标要求抽取 V1",
            "description": "从招标文件中抽取结构化的招标要求（基准条款库），包括7个维度：资格要求、技术要求、商务要求、价格要求、文档结构、进度质量、其他要求",
            "file_path": "backend/app/works/tender/prompts/requirements_v1.md"
        },
        {
            "id": "prompt_bid_response_v1_001",
            "module": "bid_response_v1",
            "name": "投标响应要素抽取 V1",
            "description": "从投标文件中抽取结构化的响应要素，包括7个维度：资格响应、技术响应、商务响应、价格响应、文档结构、进度质量、其他响应",
            "file_path": "backend/app/works/tender/prompts/bid_response_v1.md"
        }
    ]
    
    # 读取并插入每个 prompt
    with pool.connection() as conn:
        with conn.cursor() as cur:
            for prompt_info in prompts:
                # 检查是否已存在
                cur.execute("""
                    SELECT id FROM prompt_templates 
                    WHERE module = %s AND is_active = TRUE
                """, (prompt_info["module"],))
                
                existing = cur.fetchone()
                
                if existing:
                    print(f"✓ 模块 '{prompt_info['module']}' 已存在，跳过")
                    continue
                
                # 读取 prompt 文件内容
                prompt_file = Path(__file__).parent.parent / prompt_info["file_path"]
                
                if not prompt_file.exists():
                    print(f"✗ 文件不存在: {prompt_file}")
                    continue
                
                content = prompt_file.read_text(encoding="utf-8")
                
                # 插入到数据库
                cur.execute("""
                    INSERT INTO prompt_templates (
                        id, module, name, description, content, 
                        version, is_active, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    prompt_info["id"],
                    prompt_info["module"],
                    prompt_info["name"],
                    prompt_info["description"],
                    content,
                    1,  # version
                    True,  # is_active
                    datetime.now(),
                    datetime.now()
                ))
                
                print(f"✓ 成功插入模块 '{prompt_info['module']}' (长度: {len(content)} 字符)")
        
        # 提交事务
        conn.commit()
    
    # 可选：标记旧版为 deprecated
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE prompt_templates 
                SET description = '[旧版 - 已弃用] ' || description 
                WHERE module IN ('project_info', 'review') 
                  AND description NOT LIKE '[旧版%'
                  AND description NOT LIKE '%已弃用%'
            """)
            
            updated = cur.rowcount
            if updated > 0:
                print(f"✓ 已标记 {updated} 个旧版 prompt 为 deprecated")
            
            conn.commit()
    
    # 验证结果
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT module, name, version, is_active, 
                       length(content) as content_length, created_at
                FROM prompt_templates
                WHERE module IN ('project_info_v3', 'requirements_v1', 'bid_response_v1')
                ORDER BY module
            """)
            
            rows = cur.fetchall()
            
            print("\n验证结果：")
            print("-" * 80)
            for row in rows:
                print(f"模块: {row[0]:<25} | 名称: {row[1]:<20} | "
                      f"版本: {row[2]} | 激活: {row[3]} | "
                      f"内容长度: {row[4]:>6} | 创建时间: {row[5]}")
            print("-" * 80)
    
    print("\n✅ V3 Prompt 模板初始化完成！")


if __name__ == "__main__":
    try:
        init_v3_prompts()
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

