#!/usr/bin/env python3
"""
使用真实LLM重新分析格式模板
"""
import asyncio
import sys
sys.path.insert(0, '/app')

from app.works.tender.format_templates import FormatTemplatesWork
from app.services.db.postgres import _get_pool

async def main():
    template_id = "tpl_3c38daa2b8af4999a615580b21f4ad4e"
    model_id = "fcd1f843-d3dd-4305-ab78-ab2fce884a26"  # 真实LLM模型ID
    
    print(f"开始重新分析模板: {template_id}")
    print(f"使用模型: {model_id}")
    print("=" * 60)
    
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
            
            anchors = apply_assets.get('anchors', [])
            if anchors:
                print(f"\n  锚点详情:")
                for i, anchor in enumerate(anchors, 1):
                    print(f"    {i}. blockId: {anchor.get('blockId')}")
                    print(f"       type: {anchor.get('type')}")
                    print(f"       reason: {anchor.get('reason')}")
                    print(f"       confidence: {anchor.get('confidence')}")
            
            keep_plan = apply_assets.get('keepPlan', {})
            print(f"\n  保留/删除计划:")
            print(f"    - keepBlockIds: {len(keep_plan.get('keepBlockIds', []))}")
            print(f"    - deleteBlockIds: {len(keep_plan.get('deleteBlockIds', []))}")
            print(f"    - notes: {keep_plan.get('notes', '')}")
            
            policy = apply_assets.get('policy', {})
            print(f"\n  策略信息:")
            print(f"    - confidence: {policy.get('confidence', 0)}")
            print(f"    - warnings: {policy.get('warnings', [])}")
            
            role_mapping = result.analysis_json.get("roleMapping", {})
            print(f"\n样式映射 (roleMapping):")
            for key, value in role_mapping.items():
                print(f"  - {key}: {value}")
        
    except Exception as e:
        print(f"\n❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

