#!/usr/bin/env python3
"""
手动触发文档索引脚本
用于修复未索引的招投标项目文档
"""
import asyncio
import sys
import os
sys.path.insert(0, '/app')

from app.db import get_pool
from app.platform.ingest.v2_service import IngestV2Service
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def trigger_index(project_id: str):
    """
    手动触发项目文档索引
    
    适用场景：
    1. 文档上传了但没有自动索引
    2. 索引失败需要重新索引
    3. 旧项目需要补索引
    """
    pool = await get_pool()
    
    # 1. 获取项目信息
    project = await pool.fetchrow("""
        SELECT id, name, kb_id, owner_id
        FROM tender_projects
        WHERE id = $1
    """, project_id)
    
    if not project:
        print(f"❌ 项目不存在: {project_id}")
        return
    
    print(f"\n{'='*60}")
    print(f"项目: {project['name']}")
    print(f"ID: {project_id}")
    print(f"知识库ID: {project['kb_id']}")
    print(f"{'='*60}\n")
    
    # 2. 查找项目的文件（从文件系统）
    project_dir = f"/app/data/tender_assets/{project_id}"
    
    if not os.path.exists(project_dir):
        print(f"❌ 项目文件目录不存在: {project_dir}")
        print("\n可能的原因：")
        print("  1. 文档未上传")
        print("  2. 文件存储在其他位置")
        print("  3. 需要从前端重新上传文档")
        return
    
    # 列出所有文件
    files = []
    for fname in os.listdir(project_dir):
        fpath = os.path.join(project_dir, fname)
        if os.path.isfile(fpath):
            # 判断文档类型
            if fname.startswith("tender_"):
                doc_type = "tender"
            elif fname.startswith("bid_"):
                doc_type = "bid"
            elif fname.startswith("template_"):
                doc_type = "template"
            else:
                doc_type = "custom_rule"
            
            files.append({
                'path': fpath,
                'filename': fname,
                'doc_type': doc_type,
                'size': os.path.getsize(fpath)
            })
    
    if not files:
        print(f"❌ 项目目录下没有文件: {project_dir}")
        return
    
    print(f"发现 {len(files)} 个文件：")
    for f in files:
        print(f"  - [{f['doc_type']}] {f['filename']} ({f['size']} bytes)")
    
    print(f"\n{'='*60}")
    print("开始索引...")
    print(f"{'='*60}\n")
    
    # 3. 逐个索引
    ingest_service = IngestV2Service(pool)
    success_count = 0
    
    for f in files:
        print(f"\n处理: {f['filename']}")
        print(f"  类型: {f['doc_type']}")
        print(f"  大小: {f['size']} bytes")
        
        try:
            # 读取文件内容
            with open(f['path'], 'rb') as file:
                file_bytes = file.read()
            
            # 调用索引
            result = await ingest_service.ingest_asset_v2(
                project_id=project_id,
                asset_id=f"manual_{os.path.basename(f['path'])}",
                file_bytes=file_bytes,
                filename=f['filename'],
                doc_type=f['doc_type'],
                owner_id=project['owner_id'],
                storage_path=f['path']
            )
            
            print(f"  ✅ 索引成功")
            print(f"     - 文档版本ID: {result.doc_version_id}")
            print(f"     - 分片数量: {result.segment_count}")
            print(f"     - Milvus数量: {result.milvus_count}")
            
            success_count += 1
            
        except Exception as e:
            print(f"  ❌ 索引失败: {e}")
            logger.exception(f"索引失败: {f['filename']}")
    
    print(f"\n{'='*60}")
    print(f"索引完成: {success_count}/{len(files)} 成功")
    print(f"{'='*60}\n")
    
    # 4. 验证索引结果
    doc_count = await pool.fetchval("""
        SELECT COUNT(DISTINCT d.id)
        FROM documents d
        WHERE d.namespace = $1
    """, project_id)
    
    chunk_count = await pool.fetchval("""
        SELECT COUNT(*)
        FROM kb_chunks
        WHERE kb_id = $1
    """, project['kb_id'])
    
    print("索引验证：")
    print(f"  - 文档数量: {doc_count}")
    print(f"  - 分片数量: {chunk_count}")
    
    if chunk_count > 0:
        print("\n✅ 索引成功！现在可以提取基本信息了")
    else:
        print("\n⚠️  分片数量为0，索引可能失败")
    
    await pool.close()

if __name__ == '__main__':
    # 使用方式：
    # python manual_index.py tp_9160ce348db444e9b5a3fa4b66e8680a
    
    if len(sys.argv) < 2:
        print("Usage: python manual_index.py <project_id>")
        print("\n示例: python manual_index.py tp_9160ce348db444e9b5a3fa4b66e8680a")
        sys.exit(1)
    
    project_id = sys.argv[1]
    asyncio.run(trigger_index(project_id))

