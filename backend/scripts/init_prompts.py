"""
初始化Prompt数据库
从文件系统读取现有的Prompt文件，导入到数据库中
"""
import asyncio
import os
from app.services.db.postgres import get_pool
import uuid


async def init_prompts():
    """初始化Prompt模板数据"""
    pool = get_pool()
    
    # 定义所有Prompt模板
    prompts = [
        {
            "id": "prompt_project_info_v2",
            "module": "project_info",
            "name": "项目信息提取 v2",
            "description": "提取项目基本信息、技术参数、商务条款、评分标准（契约字段 + v0.3.0宽泛提取）",
            "file_path": "backend/app/works/tender/prompts/project_info_v2.md"
        },
        {
            "id": "prompt_risks_v2",
            "module": "risks",
            "name": "风险识别 v2",
            "description": "识别招标文件中的法律、技术、商务、合规风险",
            "file_path": "backend/app/works/tender/prompts/risks_v2.md"
        },
        {
            "id": "prompt_directory_v2",
            "module": "directory",
            "name": "目录生成 v2",
            "description": "自动生成投标文件语义大纲和章节结构",
            "file_path": "backend/app/works/tender/prompts/directory_v2.md"
        },
        {
            "id": "prompt_review_v2",
            "module": "review",
            "name": "审核评估 v2",
            "description": "对投标文件进行合规性和完整性审核",
            "file_path": "backend/app/works/tender/prompts/review_v2.md"
        }
    ]
    
    async with pool.acquire() as conn:
        for prompt_def in prompts:
            # 检查是否已存在
            existing = await conn.fetchrow(
                "SELECT id FROM prompt_templates WHERE id = $1",
                prompt_def["id"]
            )
            
            if existing:
                print(f"Prompt {prompt_def['id']} already exists, skipping...")
                continue
            
            # 读取文件内容
            file_path = os.path.join("/aidata/x-llmapp1", prompt_def["file_path"])
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except FileNotFoundError:
                print(f"Warning: File not found: {file_path}")
                content = f"# {prompt_def['name']}\n\n(待添加内容)"
            
            # 插入数据库
            await conn.execute(
                """
                INSERT INTO prompt_templates 
                (id, module, name, description, content, version, is_active)
                VALUES ($1, $2, $3, $4, $5, 1, TRUE)
                """,
                prompt_def["id"],
                prompt_def["module"],
                prompt_def["name"],
                prompt_def["description"],
                content
            )
            
            print(f"✓ Initialized prompt: {prompt_def['name']}")
    
    print("\n✓ All prompts initialized successfully!")


if __name__ == "__main__":
    asyncio.run(init_prompts())

