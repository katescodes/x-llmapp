#!/usr/bin/env python3
"""
测试项目信息提取 - 调试版本
查看检索到的文档块和LLM返回的结果
"""
import asyncio
import sys
import os
sys.path.insert(0, '/app')

from app.db import get_pool
from app.works.tender.extract_v2_service import ExtractV2Service
from app.services.llm.llm_orchestrator import LLMOrchestrator
from app.services.llm.llm_model_store import get_llm_store
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    # 获取项目ID
    pool = await get_pool()
    row = await pool.fetchrow("""
        SELECT id, name FROM tender_projects
        WHERE name LIKE '%测试%'
        ORDER BY created_at DESC
        LIMIT 1
    """)
    
    if not row:
        print("❌ 未找到测试项目")
        return
    
    project_id = row['id']
    project_name = row['name']
    
    print(f"\n{'='*60}")
    print(f"项目: {project_name}")
    print(f"ID: {project_id}")
    print(f"{'='*60}\n")
    
    # 获取默认LLM模型
    llm_store = get_llm_store()
    default_model = llm_store.get_default()
    
    if not default_model:
        print("❌ 未配置默认LLM模型")
        return
    
    model_id = default_model.model_id
    print(f"使用LLM模型: {model_id}\n")
    
    # 创建服务
    llm_orchestrator = LLMOrchestrator(pool)
    service = ExtractV2Service(pool, llm_orchestrator)
    
    # 执行提取
    print("开始提取项目信息...\n")
    
    try:
        result = await service.extract_project_info_v2(
            project_id=project_id,
            model_id=model_id,
            run_id=None
        )
        
        print("\n" + "="*60)
        print("提取结果")
        print("="*60 + "\n")
        
        data = result.get('data', {})
        base = data.get('base', {})
        
        print("【基本信息】")
        fields = {
            'projectName': '项目名称',
            'ownerName': '招标人',
            'agencyName': '代理机构',
            'budget': '预算金额',
            'maxPrice': '最高限价',
            'bidBond': '投标保证金',
            'bidDeadline': '投标截止时间',
            'bidOpeningTime': '开标时间',
            'schedule': '工期要求',
            'quality': '质量要求',
            'location': '项目地点',
            'contact': '联系人'
        }
        
        missing_fields = []
        for key, label in fields.items():
            value = base.get(key, '')
            if value:
                print(f"  ✅ {label}: {value}")
            else:
                print(f"  ❌ {label}: (缺失)")
                missing_fields.append(label)
        
        print(f"\n检索到的文档块数量: {len(result.get('evidence_chunk_ids', []))}")
        
        if missing_fields:
            print(f"\n⚠️  缺失字段: {', '.join(missing_fields)}")
            print("\n建议检查：")
            print("  1. 原始文档是否包含这些信息")
            print("  2. 文档是否已正确分块并索引（docstore）")
            print("  3. 检索查询关键词是否覆盖这些字段")
        
    except Exception as e:
        logger.exception(f"提取失败: {e}")
        print(f"\n❌ 提取失败: {e}")
    
    finally:
        await pool.close()

if __name__ == '__main__':
    asyncio.run(main())

