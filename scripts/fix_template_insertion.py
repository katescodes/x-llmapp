#!/usr/bin/env python
"""
修复范本插入功能的一键脚本

问题诊断和修复流程：
1. 检查数据库中是否有标记为潜在范本的chunks
2. 如果没有，为现有项目补打标记
3. 验证范本匹配和填充功能是否正常

使用方法：
  # 诊断问题（不修改数据）
  python scripts/fix_template_insertion.py --diagnose
  
  # 诊断特定项目
  python scripts/fix_template_insertion.py --diagnose --project-id <项目ID>
  
  # 修复特定项目
  python scripts/fix_template_insertion.py --fix --project-id <项目ID>
  
  # 修复所有项目
  python scripts/fix_template_insertion.py --fix --all
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


def diagnose_project(pool, project_id: str) -> dict:
    """诊断项目的范本功能状态"""
    logger.info(f"📊 诊断项目: {project_id}")
    
    result = {
        'project_id': project_id,
        'has_tender_doc': False,
        'total_chunks': 0,
        'marked_chunks': 0,
        'potential_templates': 0,
        'issues': []
    }
    
    try:
        # 1. 检查是否有招标文档
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT dv.id, dv.filename
                    FROM tender_project_documents tpd
                    JOIN documents d ON d.id = tpd.kb_doc_id
                    JOIN document_versions dv ON dv.document_id = d.id
                    WHERE tpd.project_id = %s AND tpd.doc_role = 'tender'
                    ORDER BY dv.created_at DESC
                    LIMIT 1
                """, [project_id])
                
                doc_version_row = cur.fetchone()
                if not doc_version_row:
                    result['issues'].append("❌ 未找到招标文档")
                    return result
                
                doc_version_id = doc_version_row['id']
                filename = doc_version_row['filename']
                result['has_tender_doc'] = True
                result['tender_filename'] = filename
                logger.info(f"  ✓ 找到招标文档: {filename}")
                
                # 2. 统计chunks
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM doc_segments
                    WHERE doc_version_id = %s
                """, [doc_version_id])
                count_row = cur.fetchone()
                result['total_chunks'] = count_row['count'] if count_row else 0
                logger.info(f"  ✓ 文档分片总数: {result['total_chunks']}")
                
                # 3. 统计已标记的chunks
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM doc_segments
                    WHERE doc_version_id = %s
                    AND meta_json->>'is_potential_template' = 'true'
                """, [doc_version_id])
                marked_row = cur.fetchone()
                result['marked_chunks'] = marked_row['count'] if marked_row else 0
                logger.info(f"  ✓ 已标记为范本的chunks: {result['marked_chunks']}")
                
                # 4. 检查潜在范本（采样前50个未标记的chunks）
                cur.execute("""
                    SELECT id, content_text, meta_json
                    FROM doc_segments
                    WHERE doc_version_id = %s
                    AND (
                        meta_json->>'is_potential_template' IS NULL
                        OR meta_json->>'is_potential_template' = 'false'
                    )
                    ORDER BY segment_no
                    LIMIT 50
                """, [doc_version_id])
                
                chunks = cur.fetchall()
                potential_count = 0
                
                for chunk_id, content_text, meta_json in chunks:
                    # meta_json可能是str或dict，需要解析
                    import json as json_module
                    if isinstance(meta_json, str):
                        try:
                            meta_dict = json_module.loads(meta_json)
                        except:
                            meta_dict = {}
                    else:
                        meta_dict = meta_json or {}
                    
                    template_info = identify_potential_template(
                        chunk_text=content_text,
                        chunk_meta=meta_dict,
                    )
                    if template_info:
                        potential_count += 1
                
                result['potential_templates'] = potential_count
                if potential_count > 0:
                    logger.info(f"  ⚠️  发现 {potential_count} 个未标记的潜在范本（采样50个chunks）")
                    result['issues'].append(f"发现 {potential_count} 个未标记的范本，需要运行修复")
                else:
                    logger.info(f"  ✓ 未发现遗漏的范本（采样50个chunks）")
                
                # 5. 检查目录节点是否有body_content
                cur.execute("""
                    SELECT COUNT(*) as total, COUNT(body_content) as with_body
                    FROM tender_directory_nodes
                    WHERE project_id = %s
                """, [project_id])
                
                node_row = cur.fetchone()
                if node_row:
                    result['total_nodes'] = node_row['total']
                    result['nodes_with_body'] = node_row['with_body'] or 0
                    
                    if result['total_nodes'] > 0:
                        logger.info(f"  ✓ 目录节点总数: {result['total_nodes']}")
                        logger.info(f"  ✓ 有正文内容的节点: {result['nodes_with_body']}")
                        
                        if result['nodes_with_body'] == 0 and result['marked_chunks'] > 0:
                            result['issues'].append("目录节点没有正文，但有标记的范本 - 可能需要重新生成目录")
    
    except Exception as e:
        logger.error(f"诊断失败: {e}", exc_info=True)
        result['issues'].append(f"诊断出错: {str(e)}")
    
    return result


def print_diagnosis_report(results: list):
    """打印诊断报告"""
    logger.info("\n" + "="*70)
    logger.info("📋 诊断报告")
    logger.info("="*70)
    
    total_projects = len(results)
    projects_with_issues = sum(1 for r in results if r.get('issues'))
    projects_need_fix = sum(1 for r in results if r.get('potential_templates', 0) > 0)
    
    logger.info(f"\n总计: {total_projects} 个项目")
    logger.info(f"  - 有问题的项目: {projects_with_issues}")
    logger.info(f"  - 需要修复的项目: {projects_need_fix}")
    
    for result in results:
        if result.get('issues'):
            logger.info(f"\n项目 {result['project_id']}:")
            for issue in result['issues']:
                logger.info(f"  {issue}")
    
    if projects_need_fix > 0:
        logger.info("\n" + "="*70)
        logger.info("💡 修复建议:")
        logger.info("  运行以下命令修复问题：")
        logger.info("  python scripts/fix_template_insertion.py --fix --all")
        logger.info("="*70)
    else:
        logger.info("\n" + "="*70)
        logger.info("✅ 所有项目的范本功能正常")
        logger.info("="*70)


def fix_project(pool, project_id: str) -> tuple:
    """修复单个项目"""
    logger.info(f"🔧 修复项目: {project_id}")
    
    # 先诊断
    diagnosis = diagnose_project(pool, project_id)
    
    if not diagnosis['has_tender_doc']:
        logger.warning("无招标文档，跳过")
        return 0, 0
    
    if diagnosis['potential_templates'] == 0:
        logger.info("未发现需要标记的范本，跳过")
        return diagnosis['total_chunks'], 0
    
    # 执行标记
    logger.info(f"开始标记范本...")
    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            # 获取文档版本ID
            cur.execute("""
                SELECT dv.id
                FROM tender_project_documents tpd
                JOIN documents d ON d.id = tpd.kb_doc_id
                JOIN document_versions dv ON dv.document_id = d.id
                WHERE tpd.project_id = %s AND tpd.doc_role = 'tender'
                ORDER BY dv.created_at DESC
                LIMIT 1
            """, [project_id])
            
            doc_version_id = cur.fetchone()[0]
            
            # 获取未标记的chunks
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
            marked_count = 0
            
            logger.info(f"处理 {total_chunks} 个chunks...")
            
            for chunk_id, content_text, meta_json in chunks:
                # meta_json可能是str或dict，需要解析
                import json as json_module
                if isinstance(meta_json, str):
                    try:
                        meta_dict = json_module.loads(meta_json)
                    except:
                        meta_dict = {}
                else:
                    meta_dict = meta_json or {}
                
                template_info = identify_potential_template(
                    chunk_text=content_text,
                    chunk_meta=meta_dict,
                )
                
                if template_info:
                    # 合并到原有 meta_json
                    import json
                    updated_meta = {**meta_dict, **template_info}
                    
                    # 更新数据库
                    cur.execute("""
                        UPDATE doc_segments
                        SET meta_json = %s::jsonb
                        WHERE id = %s
                    """, [json.dumps(updated_meta), chunk_id])
                    
                    marked_count += 1
                    
                    if marked_count <= 5:
                        logger.info(
                            f"  ✓ 标记范本 #{marked_count}: "
                            f"{content_text[:50]}... (score={template_info.get('template_score')})"
                        )
            
            conn.commit()
    
    logger.info(f"✅ 完成! 处理 {total_chunks} 个chunks, 标记 {marked_count} 个范本")
    return total_chunks, marked_count


def main():
    parser = argparse.ArgumentParser(
        description='诊断和修复范本插入功能',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 诊断所有项目
  python scripts/fix_template_insertion.py --diagnose --all
  
  # 诊断特定项目
  python scripts/fix_template_insertion.py --diagnose --project-id abc123
  
  # 修复特定项目
  python scripts/fix_template_insertion.py --fix --project-id abc123
  
  # 修复所有项目
  python scripts/fix_template_insertion.py --fix --all
        """
    )
    
    parser.add_argument('--diagnose', action='store_true', help='诊断问题（不修改数据）')
    parser.add_argument('--fix', action='store_true', help='修复问题')
    parser.add_argument('--project-id', type=str, help='项目ID（处理单个项目）')
    parser.add_argument('--all', action='store_true', help='处理所有项目')
    
    args = parser.parse_args()
    
    if not args.diagnose and not args.fix:
        parser.error("必须指定 --diagnose 或 --fix")
    
    if not args.project_id and not args.all:
        parser.error("必须指定 --project-id 或 --all")
    
    # 获取数据库连接
    pool = _get_pool()
    
    try:
        if args.diagnose:
            # 诊断模式
            if args.project_id:
                result = diagnose_project(pool, args.project_id)
                print_diagnosis_report([result])
            else:
                # 诊断所有项目
                with pool.connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT DISTINCT tpd.project_id, tp.name, tp.created_at
                            FROM tender_project_documents tpd
                            JOIN tender_projects tp ON tp.project_id = tpd.project_id
                            WHERE tpd.doc_role = 'tender'
                            ORDER BY tp.created_at DESC
                            LIMIT 20
                        """)
                        projects = cur.fetchall()
                
                logger.info(f"找到 {len(projects)} 个项目（显示前20个）")
                results = []
                
                for project_id, project_name, _ in projects:
                    logger.info(f"\n{'='*60}")
                    logger.info(f"项目: {project_name}")
                    result = diagnose_project(pool, project_id)
                    results.append(result)
                
                print_diagnosis_report(results)
        
        elif args.fix:
            # 修复模式
            if args.project_id:
                total, marked = fix_project(pool, args.project_id)
                logger.info(f"\n✅ 完成! 处理 {total} 个chunks, 标记 {marked} 个范本")
            else:
                # 修复所有项目
                with pool.connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT DISTINCT tpd.project_id, tp.name, tp.created_at
                            FROM tender_project_documents tpd
                            JOIN tender_projects tp ON tp.project_id = tpd.project_id
                            WHERE tpd.doc_role = 'tender'
                            ORDER BY tp.created_at DESC
                        """)
                        projects = cur.fetchall()
                
                logger.info(f"找到 {len(projects)} 个项目")
                
                total_processed = 0
                total_marked = 0
                
                for project_id, project_name, _ in projects:
                    logger.info(f"\n{'='*60}")
                    logger.info(f"项目: {project_name}")
                    
                    try:
                        processed, marked = fix_project(pool, project_id)
                        total_processed += processed
                        total_marked += marked
                    except Exception as e:
                        logger.error(f"修复失败: {e}", exc_info=True)
                
                logger.info(f"\n{'='*60}")
                logger.info("📊 总结:")
                logger.info(f"  处理chunks总数: {total_processed}")
                logger.info(f"  标记范本总数: {total_marked}")
                logger.info("="*60)
    
    except KeyboardInterrupt:
        logger.warning("\n⚠️  用户中断")
    except Exception as e:
        logger.error(f"\n❌ 失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

