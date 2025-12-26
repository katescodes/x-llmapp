#!/usr/bin/env python3
"""
测试从目录到PDF的语义搜索功能
"""
import sys
sys.path.insert(0, '/aidata/x-llmapp1/backend')

from app.services.dao.tender_dao import TenderDAO
from app.services.fragment.outline_attacher import OutlineSampleAttacher
from app.db.base import init_pool

print("=" * 80)
print("🧪 测试从目录标题到PDF内容的语义搜索")
print("=" * 80)

# 初始化数据库连接
pool = init_pool()
dao = TenderDAO(pool)

project_id = "pj_f3b8e15489f44deead8f68cac58fa97a"  # 测试1项目

# 1. 获取目录
print("\n📋 获取目录...")
nodes = dao.list_directory(project_id)
print(f"目录节点数: {len(nodes)}")

# 显示前10个节点
print("\n前10个节点:")
for i, node in enumerate(nodes[:10]):
    print(f"  {i+1}. [{node.get('id')}] {node.get('title')}")

# 2. 执行语义搜索
print("\n" + "=" * 80)
print("🔍 执行语义搜索匹配...")
print("=" * 80)

attacher = OutlineSampleAttacher(dao)

try:
    attached_count = attacher.attach_from_pdf_semantic(project_id, nodes, min_confidence=0.5)
    
    print(f"\n✅ 成功匹配并填充 {attached_count} 个节点")
    
    # 3. 查看填充结果
    print("\n📊 填充结果检查...")
    filled_nodes = []
    for node in nodes:
        node_id = node.get("id")
        body = dao.get_section_body(project_id, node_id)
        if body and body.get("content_html"):
            filled_nodes.append({
                "id": node_id,
                "title": node.get("title"),
                "source": body.get("source"),
                "content_type": body.get("content_type"),
                "content_length": len(body.get("content_html", "")),
            })
    
    print(f"\n已填充节点数: {len(filled_nodes)}")
    for i, n in enumerate(filled_nodes[:10]):
        print(f"  {i+1}. {n['title']}")
        print(f"     → 来源: {n['source']}, 类型: {n['content_type']}, 长度: {n['content_length']}字符")
    
except Exception as e:
    print(f"\n❌ 执行失败: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("测试完成")
print("=" * 80)

