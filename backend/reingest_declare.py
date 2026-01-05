#!/usr/bin/env python3
"""
重新入库申报书项目的文档
"""
import asyncio
import os
import sys

# 添加 app 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ''))

from app.platform.ingest.v2_service import IngestV2Service
from app.services.db.postgres import _get_pool

async def main():
    project_id = "declare_proj_5dada4f9440a42dface96aabc53445ad"
    kb_id = "dcee1b39570143e89f102544b0118b6a"
    owner_id = "admin-user-001"
    
    # 文档列表（kind, filename, doc_type）
    docs = [
        ("notice", "浙江省经济和信息化厅关于开展2025年浙江省未来工厂和智能工厂、数字化车间评定工作的通知.pdf", "tender_notice"),
        ("user_doc", "企业简介.docx", "general_doc"),
        ("user_doc", "专利、设备清单.docx", "general_doc"),
        ("user_doc", "图片说明.xlsx", "general_doc"),
    ]
    
    pool = _get_pool()
    ingest_service = IngestV2Service(pool)
    
    base_dir = "./data/declare/files"
    
    for kind, filename, doc_type in docs:
        file_path = os.path.join(base_dir, f"{project_id}_{kind}_{filename}")
        
        if not os.path.exists(file_path):
            print(f"❌ 文件不存在: {file_path}")
            continue
        
        print(f"📝 处理文件: {filename}")
        print(f"   kind: {kind}, doc_type: {doc_type}")
        
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
            
            asset_id = f"temp_{kind}_{filename.replace('.', '_')}"
            
            result = await ingest_service.ingest_asset_v2(
                project_id=project_id,
                asset_id=asset_id,
                file_bytes=file_bytes,
                filename=filename,
                doc_type=doc_type,
                owner_id=owner_id,
                storage_path=file_path,
                kb_id=kb_id,
            )
            
            print(f"   ✅ 入库成功: {result.segment_count} segments, {result.milvus_count} vectors")
        except Exception as e:
            print(f"   ❌ 入库失败: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n🎉 重新入库完成！")

if __name__ == "__main__":
    asyncio.run(main())

