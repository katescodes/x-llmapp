#!/usr/bin/env python3
"""
重新分析格式模板，使用 LLM 生成 applyAssets
"""
import asyncio
import sys
sys.path.insert(0, '/app')

from app.works.tender.format_templates import FormatTemplatesWork
from app.services.db.postgres import _get_pool

async def main():
    template_id = "tpl_3c38daa2b8af4999a615580b21f4ad4e"
    model_id = "mock-llm-1"
    
    print(f"开始重新分析模板: {template_id}")
    print(f"使用模型: {model_id}")
    
    pool = _get_pool()
    work = FormatTemplatesWork(
        pool=pool,
        llm_orchestrator=None,
        storage_dir="storage/templates"
    )
    
    try:
        result = await work.analyze_template(
            template_id=template_id,
            force=True,
            docx_bytes=None,
            model_id=model_id
        )
        
        print(f"\n✅ 分析完成！")
        print(f"模板ID: {result.id}")
        print(f"模板名称: {result.name}")
        
        # 检查 applyAssets
        if result.analysis_json:
            apply_assets = result.analysis_json.get("applyAssets", {})
            print(f"\napplyAssets 信息:")
            print(f"  - anchors: {len(apply_assets.get('anchors', []))}")
            print(f"  - keepBlockIds: {len(apply_assets.get('keepPlan', {}).get('keepBlockIds', []))}")
            print(f"  - deleteBlockIds: {len(apply_assets.get('keepPlan', {}).get('deleteBlockIds', []))}")
            print(f"  - confidence: {apply_assets.get('policy', {}).get('confidence', 0)}")
            print(f"  - warnings: {apply_assets.get('policy', {}).get('warnings', [])}")
        
    except Exception as e:
        print(f"\n❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

