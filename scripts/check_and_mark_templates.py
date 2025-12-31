#!/usr/bin/env python3
"""检查并标记项目的格式范本"""
import sys
sys.path.insert(0, '/app')

from app.services.db.postgres import _get_pool
from app.works.tender.template_matcher import identify_potential_template
import psycopg
from psycopg.rows import tuple_row
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def main():
    pool = _get_pool()
    
    with pool.connection() as conn:
        with conn.cursor(row_factory=tuple_row) as cur:
            # 1. 查找有目录的项目（说明已经提取过）
            logger.info("=" * 60)
            logger.info("🔍 查找已有目录的项目")
            logger.info("=" * 60)
            
            cur.execute("""
                SELECT DISTINCT project_id
                FROM tender_directory_nodes
                ORDER BY project_id
                LIMIT 10
            """)
            
            projects_with_dir = [row[0] for row in cur.fetchall()]
            logger.info(f"找到 {len(projects_with_dir)} 个有目录的项目")
            
            for project_id in projects_with_dir:
                logger.info(f"\n{'=' * 60}")
                logger.info(f"📁 项目ID: {project_id}")
                logger.info(f"{'=' * 60}")
                
                # 2. 查找项目名称
                cur.execute("SELECT name FROM tender_projects WHERE id = %s", [project_id])
                result = cur.fetchone()
                if result:
                    logger.info(f"项目名: {result[0]}")
                
                # 3. 查找文档
                cur.execute("""
                    SELECT dv.id, dv.filename
                    FROM tender_project_documents tpd
                    JOIN documents d ON d.id = tpd.kb_doc_id
                    JOIN document_versions dv ON dv.document_id = d.id
                    WHERE tpd.project_id = %s AND tpd.doc_role = 'tender'
                    LIMIT 1
                """, [project_id])
                
                doc_result = cur.fetchone()
                if not doc_result:
                    logger.warning("⚠️  未找到招标文档，跳过")
                    continue
                
                doc_version_id, filename = doc_result
                logger.info(f"📄 文档: {filename}")
                
                # 4. 检查已标记的范本数量
                cur.execute("""
                    SELECT COUNT(*)
                    FROM doc_segments
                    WHERE doc_version_id = %s 
                      AND meta_json->>'is_potential_template' = 'true'
                """, [doc_version_id])
                
                existing_templates = cur.fetchone()[0]
                logger.info(f"已标记范本: {existing_templates} 个")
                
                if existing_templates > 0:
                    logger.info("✅ 已有范本标记，跳过")
                    
                    # 检查目录正文填充情况
                    cur.execute("""
                        SELECT COUNT(*) as total,
                               SUM(CASE WHEN body_content IS NOT NULL AND body_content != '' THEN 1 ELSE 0 END) as filled
                        FROM tender_directory_nodes
                        WHERE project_id = %s
                    """, [project_id])
                    
                    total, filled = cur.fetchone()
                    logger.info(f"目录节点: {total} 个，已填充: {filled} 个")
                    
                    if filled == 0:
                        logger.info("💡 建议: 重新生成目录以填充正文")
                    continue
                
                # 5. 执行标记
                logger.info("🔨 开始标记范本...")
                
                cur.execute("""
                    SELECT id, content_text, meta_json
                    FROM doc_segments
                    WHERE doc_version_id = %s
                    ORDER BY segment_no
                """, [doc_version_id])
                
                chunks = cur.fetchall()
                total_chunks = len(chunks)
                
                marked_count = 0
                for chunk_id, content, meta_json in chunks:
                    template_info = identify_potential_template(content, meta_json or {})
                    if template_info:
                        meta_json = meta_json or {}
                        meta_json.update(template_info)
                        
                        cur.execute("""
                            UPDATE doc_segments
                            SET meta_json = %s
                            WHERE id = %s
                        """, [psycopg.types.json.Json(meta_json), chunk_id])
                        
                        marked_count += 1
                
                conn.commit()
                logger.info(f"✅ 已标记 {marked_count}/{total_chunks} 个chunks")
                logger.info("💡 下一步: 前端重新生成目录")

if __name__ == "__main__":
    main()

