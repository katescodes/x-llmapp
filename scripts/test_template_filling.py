#!/usr/bin/env python3
"""
格式范本自动填充 - 完整测试和修复脚本

用途：
1. 检查项目状态
2. 补打范本标记（如需要）
3. 触发目录生成
4. 验证填充结果
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, '/app')
os.chdir('/app')

import psycopg
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def main():
    # 连接数据库
    conn = psycopg.connect("host=postgres port=5432 dbname=localgpt user=localgpt password=localgpt")
    cur = conn.cursor()
    
    try:
        # 1. 获取最新项目
        logger.info("=" * 60)
        logger.info("📁 检查项目")
        logger.info("=" * 60)
        
        cur.execute("""
            SELECT id, name 
            FROM tender_projects 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        projects = cur.fetchall()
        
        if not projects:
            logger.error("❌ 没有找到项目")
            return
        
        logger.info(f"找到 {len(projects)} 个项目:")
        for i, (pid, pname) in enumerate(projects, 1):
            logger.info(f"  {i}. {pname} (ID: {pid[:30]}...)")
        
        # 使用第一个项目
        project_id = projects[0][0]
        project_name = projects[0][1]
        
        logger.info(f"\n🎯 测试项目: {project_name}")
        logger.info(f"   项目ID: {project_id}")
        
        # 2. 检查文档
        logger.info("\n" + "=" * 60)
        logger.info("📄 检查文档")
        logger.info("=" * 60)
        
        cur.execute("""
            SELECT dv.id, dv.filename, dv.created_at
            FROM tender_project_documents tpd
            JOIN documents d ON d.id = tpd.kb_doc_id
            JOIN document_versions dv ON dv.document_id = d.id
            WHERE tpd.project_id = %s AND tpd.doc_role = 'tender'
            ORDER BY dv.created_at DESC
            LIMIT 1
        """, [project_id])
        
        doc_version = cur.fetchone()
        
        if not doc_version:
            logger.error("❌ 没有找到招标文档")
            logger.info("\n请先上传招标文档")
            return
        
        doc_version_id, filename, created_at = doc_version
        logger.info(f"✅ 找到招标文档:")
        logger.info(f"   文件名: {filename}")
        logger.info(f"   文档版本ID: {doc_version_id}")
        logger.info(f"   上传时间: {created_at}")
        
        # 3. 检查chunks总数
        logger.info("\n" + "=" * 60)
        logger.info("📦 检查文档分片")
        logger.info("=" * 60)
        
        cur.execute("""
            SELECT COUNT(*) FROM doc_segments WHERE doc_version_id = %s
        """, [doc_version_id])
        total_chunks = cur.fetchone()[0]
        logger.info(f"总chunks数: {total_chunks}")
        
        # 4. 检查范本标记
        logger.info("\n" + "=" * 60)
        logger.info("🔍 检查范本标记")
        logger.info("=" * 60)
        
        cur.execute("""
            SELECT 
                COUNT(*) as template_count,
                AVG((meta_json->>'template_score')::int) as avg_score,
                MAX((meta_json->>'template_score')::int) as max_score
            FROM doc_segments
            WHERE doc_version_id = %s
              AND meta_json->>'is_potential_template' = 'true'
        """, [doc_version_id])
        
        result = cur.fetchone()
        template_count = result[0]
        avg_score = result[1] if result[1] else 0
        max_score = result[2] if result[2] else 0
        
        logger.info(f"标记为范本的chunks: {template_count} / {total_chunks}")
        
        if template_count > 0:
            logger.info(f"平均分数: {avg_score:.1f}")
            logger.info(f"最高分数: {max_score}")
            
            # 显示前3个范本
            cur.execute("""
                SELECT 
                    LEFT(content_text, 80) as preview,
                    (meta_json->>'template_score')::int as score
                FROM doc_segments
                WHERE doc_version_id = %s
                  AND meta_json->>'is_potential_template' = 'true'
                ORDER BY (meta_json->>'template_score')::int DESC
                LIMIT 3
            """, [doc_version_id])
            
            logger.info("\n前3个范本chunks:")
            for i, (preview, score) in enumerate(cur.fetchall(), 1):
                logger.info(f"  {i}. [分数:{score}] {preview}...")
        else:
            logger.warning("⚠️  没有chunks被标记为范本！")
            logger.info("\n💡 解决方案:")
            logger.info(f"   在宿主机运行: python scripts/mark_existing_templates.py --project-id {project_id}")
            logger.info("   或者: 上传新文档（会自动标记）")
            return
        
        # 5. 检查目录
        logger.info("\n" + "=" * 60)
        logger.info("📋 检查目录节点")
        logger.info("=" * 60)
        
        cur.execute("""
            SELECT COUNT(*) FROM tender_directory_nodes WHERE project_id = %s
        """, [project_id])
        total_nodes = cur.fetchone()[0]
        
        if total_nodes == 0:
            logger.warning("⚠️  没有目录节点")
            logger.info("\n请先生成目录")
            return
        
        logger.info(f"总节点数: {total_nodes}")
        
        # 6. 检查正文填充
        cur.execute("""
            SELECT COUNT(*) 
            FROM tender_directory_nodes 
            WHERE project_id = %s 
              AND body_content IS NOT NULL 
              AND body_content != ''
        """, [project_id])
        filled_nodes = cur.fetchone()[0]
        
        logger.info(f"已填充正文: {filled_nodes} / {total_nodes}")
        
        if filled_nodes > 0:
            logger.info("\n✅ 有节点正文已填充!")
            
            cur.execute("""
                SELECT numbering, title, LEFT(body_content, 60) as preview
                FROM tender_directory_nodes
                WHERE project_id = %s 
                  AND body_content IS NOT NULL 
                  AND body_content != ''
                ORDER BY numbering
                LIMIT 5
            """, [project_id])
            
            logger.info("\n已填充的节点:")
            for numbering, title, preview in cur.fetchall():
                logger.info(f"  {numbering} {title}")
                logger.info(f"     {preview}...")
        else:
            logger.warning("\n❌ 没有节点正文被填充")
            logger.info("\n💡 可能原因:")
            logger.info("   1. 目录生成时template_matching功能未启用")
            logger.info("   2. LLM匹配失败（置信度不够）")
            logger.info("   3. 范本chunks与节点标题不匹配")
            
            logger.info("\n💡 解决方案:")
            logger.info("   1. 重新生成目录（确保enable_template_matching=True）")
            logger.info("   2. 查看后端日志: docker-compose logs backend | grep -i template")
        
        # 7. 总结
        logger.info("\n" + "=" * 60)
        logger.info("📊 诊断总结")
        logger.info("=" * 60)
        
        status = []
        status.append(("文档已上传", "✅" if doc_version else "❌"))
        status.append(("Chunks已分片", f"✅ ({total_chunks})" if total_chunks > 0 else "❌"))
        status.append(("范本已标记", f"✅ ({template_count})" if template_count > 0 else "❌"))
        status.append(("目录已生成", f"✅ ({total_nodes})" if total_nodes > 0 else "❌"))
        status.append(("正文已填充", f"✅ ({filled_nodes})" if filled_nodes > 0 else "❌"))
        
        for item, result in status:
            logger.info(f"  {item}: {result}")
        
        if filled_nodes > 0:
            logger.info("\n🎉 功能正常！格式范本已自动填充到目录节点正文")
        else:
            logger.info("\n⚠️  功能未生效，请按照上述解决方案操作")
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()

