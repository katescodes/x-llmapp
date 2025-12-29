"""
初始化Prompt数据库
从文件系统读取现有的Prompt文件，导入到数据库中
"""
import asyncio
import os
from app.services.db.postgres import _get_pool
import uuid


async def init_prompts():
    """初始化Prompt模板数据"""
    pool = _get_pool()
    
    # 定义所有Prompt模板
    prompts = [
        {
            "id": "prompt_project_info_v3",
            "module": "project_info_v3",
            "name": "招标信息提取 V3",
            "description": "提取招标文件的六大类信息（V3合并版）：项目概览、投标人资格、评审与评分、商务条款、技术要求、文件编制",
            "file_path": "backend/app/works/tender/prompts/project_info_v3.md"
        },
        {
            "id": "prompt_requirements_v1",
            "module": "requirements_v1",
            "name": "招标要求抽取 V1",
            "description": "从招标文件中抽取结构化的招标要求（基准条款库），包括资格要求、技术要求、商务要求等7个维度",
            "file_path": "backend/app/works/tender/prompts/requirements_v1.md"
        },
        {
            "id": "prompt_bid_response_v2_001",
            "module": "bid_response",
            "name": "投标响应要素抽取 V2",
            "description": "从投标文件中抽取结构化的响应要素（V2增强版），包括normalized_fields_json和evidence_json",
            "file_path": "backend/app/prompts/bid_response_extraction_v2.md"
        },
        {
            "id": "prompt_risks_v2",
            "module": "risks_v2",
            "name": "风险识别 V2",
            "description": "识别招标文件中的法律、技术、商务、合规风险",
            "file_path": "backend/app/works/tender/prompts/risks_v2.md"
        },
        {
            "id": "prompt_directory_v2",
            "module": "directory_v2",
            "name": "目录生成 V2",
            "description": "自动生成投标文件语义大纲和章节结构",
            "file_path": "backend/app/works/tender/prompts/directory_v2.md"
        },
        {
            "id": "prompt_review_v2",
            "module": "review_v2",
            "name": "审核评估 V2",
            "description": "基于检索驱动+分维度生成的审核服务",
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

