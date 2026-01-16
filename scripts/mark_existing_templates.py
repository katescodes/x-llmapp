#!/usr/bin/env python
"""
为现有项目的文档分片补打格式范本标记

用途：
- 对已入库但未标记的chunks进行范本识别
- 更新 doc_segments 的 meta_json 字段

使用方法：
  python scripts/mark_existing_templates.py --project-id <项目ID>
  python scripts/mark_existing_templates.py --all  # 处理所有项目
"""
import sys
import argparse
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.db.postgres import _get_pool
from app.works.tender.template_matcher import identify_potential_template

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def mark_templates_for_project(pool, project_id: str):
    """为单个项目的chunks标记范本"""
    logger.info(f"Processing project: {project_id}")
    
    # 1. 获取项目的招标文档
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT dv.id
                FROM tender_project_documents tpd
                JOIN doc_versions dv ON dv.asset_id = tpd.asset_id
                WHERE tpd.project_id = %s AND tpd.doc_role = 'tender'
                ORDER BY dv.created_at DESC
                LIMIT 1
            """, [project_id])
            
            doc_version_row = cur.fetchone()
            if not doc_version_row:
                logger.warning(f"No tender document found for project: {project_id}")
                return 0, 0
            
            doc_version_id = doc_version_row[0]
            logger.info(f"Found tender document version: {doc_version_id}")
    
    # 2. 获取所有未标记的chunks
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, content_text, meta_json
                FROM doc_segments
                WHERE doc_version_id = %s
                AND (
                    meta_json->>'is_potential_template' IS NULL
                    OR meta_json->>'is_potential_template' = 'false'
                )
                ORDER BY segment_no
            """, [doc_version_id])
            
            chunks = cur.fetchall()
            total_chunks = len(chunks)
            
            if total_chunks == 0:
                logger.info("No chunks to process (all already marked or no chunks exist)")
                return 0, 0
            
            logger.info(f"Found {total_chunks} chunks to process")
    
    # 3. 逐个识别并更新
    marked_count = 0
    updated_ids = []
    
    for chunk_id, content_text, meta_json in chunks:
        # 调用识别函数
        template_info = identify_potential_template(
            chunk_text=content_text,
            chunk_meta=meta_json or {},
        )
        
        if template_info:
            # 合并到原有 meta_json
            updated_meta = {**(meta_json or {}), **template_info}
            
            # 更新数据库
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    import json
                    cur.execute("""
                        UPDATE doc_segments
                        SET meta_json = %s::jsonb
                        WHERE id = %s
                    """, [json.dumps(updated_meta), chunk_id])
                conn.commit()
            
            marked_count += 1
            updated_ids.append(chunk_id)
            
            logger.debug(
                f"Marked chunk {chunk_id[:8]}... as template "
                f"(score={template_info.get('template_score')})"
            )
    
    logger.info(
        f"Project {project_id}: Marked {marked_count}/{total_chunks} chunks as templates"
    )
    
    # 显示前5个标记的chunk
    if marked_count > 0 and marked_count <= 10:
        logger.info(f"Marked chunk IDs: {', '.join(id[:8] + '...' for id in updated_ids[:5])}")
    
    return total_chunks, marked_count


def mark_templates_for_all_projects(pool):
    """为所有项目标记范本"""
    logger.info("Processing all projects...")
    
    # 获取所有有招标文档的项目
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT tpd.project_id, tp.name
                FROM tender_project_documents tpd
                JOIN tender_projects tp ON tp.id = tpd.project_id
                WHERE tpd.doc_role = 'tender'
                ORDER BY tp.created_at DESC
            """)
            
            projects = cur.fetchall()
    
    if not projects:
        logger.warning("No projects with tender documents found")
        return
    
    logger.info(f"Found {len(projects)} projects to process")
    
    total_processed = 0
    total_marked = 0
    
    for project_id, project_name in projects:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing: {project_name} (ID: {project_id})")
        logger.info('='*60)
        
        try:
            processed, marked = mark_templates_for_project(pool, project_id)
            total_processed += processed
            total_marked += marked
        except Exception as e:
            logger.error(f"Failed to process project {project_id}: {e}", exc_info=True)
    
    logger.info(f"\n{'='*60}")
    logger.info("Summary:")
    logger.info(f"  Total chunks processed: {total_processed}")
    logger.info(f"  Total templates marked: {total_marked}")
    logger.info(f"  Success rate: {total_marked/total_processed*100:.1f}%" if total_processed > 0 else "N/A")
    logger.info('='*60)


def main():
    parser = argparse.ArgumentParser(description='为现有项目的文档分片补打格式范本标记')
    parser.add_argument('--project-id', type=str, help='项目ID（处理单个项目）')
    parser.add_argument('--all', action='store_true', help='处理所有项目')
    parser.add_argument('--dry-run', action='store_true', help='只识别不更新（测试模式）')
    
    args = parser.parse_args()
    
    if not args.project_id and not args.all:
        parser.error("必须指定 --project-id 或 --all")
    
    # 获取数据库连接
    pool = _get_pool()
    
    try:
        if args.dry_run:
            logger.warning("⚠️  DRY RUN MODE: 只识别不更新数据库")
            # 在dry-run模式下，只打印第一个项目的识别结果
            if args.project_id:
                # 查看识别结果但不更新
                with pool.connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT dv.id
                            FROM tender_project_documents tpd
                            JOIN doc_versions dv ON dv.asset_id = tpd.asset_id
                            WHERE tpd.project_id = %s AND tpd.doc_role = 'tender'
                            ORDER BY dv.created_at DESC
                            LIMIT 1
                        """, [args.project_id])
                        doc_version_row = cur.fetchone()
                        if doc_version_row:
                            doc_version_id = doc_version_row[0]
                            cur.execute("""
                                SELECT id, content_text, meta_json
                                FROM doc_segments
                                WHERE doc_version_id = %s
                                AND (
                                    meta_json->>'is_potential_template' IS NULL
                                    OR meta_json->>'is_potential_template' = 'false'
                                )
                                ORDER BY segment_no
                                LIMIT 10
                            """, [doc_version_id])
                            chunks = cur.fetchall()
                            logger.info(f"找到 {len(chunks)} 个未标记的chunks（显示前10个）")
                            for chunk_id, content_text, meta_json in chunks:
                                template_info = identify_potential_template(
                                    chunk_text=content_text,
                                    chunk_meta=meta_json or {},
                                )
                                if template_info:
                                    logger.info(f"✓ Chunk {chunk_id[:8]}... 识别为范本 (score={template_info.get('template_score')})")
                                    logger.info(f"  内容预览: {content_text[:100]}...")
            return
        
        if args.project_id:
            # 处理单个项目
            total, marked = mark_templates_for_project(pool, args.project_id)
            logger.info(f"\n✅ Done! Processed {total} chunks, marked {marked} as templates")
        else:
            # 处理所有项目
            mark_templates_for_all_projects(pool)
            logger.info(f"\n✅ All projects processed!")
    
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Interrupted by user")
    except Exception as e:
        logger.error(f"\n❌ Failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

