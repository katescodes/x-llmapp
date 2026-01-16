"""
格式范本提取服务
整合文档解析、章节定位、LLM识别，完成端到端提取
"""
from __future__ import annotations
import logging
import uuid
from typing import List, Dict, Any, Optional

from app.works.tender.snippet.doc_blocks import extract_blocks, blocks_to_text
from app.works.tender.snippet.snippet_locator import locate_format_chapter
from app.works.tender.snippet.snippet_llm import (
    detect_snippets,
    validate_snippet_bounds,
    slice_blocks
)

logger = logging.getLogger(__name__)


async def extract_format_snippets(
    file_path: str,
    project_id: str,
    source_file_id: Optional[str] = None,
    model_id: str = "gpt-oss-120b"
) -> List[Dict[str, Any]]:
    """
    从招标文件中提取格式范本
    
    完整流程：
    1. 文档 -> blocks
    2. 定位"格式范本"章节
    3. LLM 识别各个范本边界
    4. 切片并返回
    
    Args:
        file_path: 招标文件路径（.docx 或 .pdf）
        project_id: 项目 ID
        source_file_id: 来源文件 ID
        model_id: LLM 模型 ID
        
    Returns:
        提取的范本列表
    """
    logger.info(f"开始提取格式范本: file={file_path}, project={project_id}")
    
    # 1. 提取文档 blocks
    try:
        all_blocks = extract_blocks(file_path)
        logger.info(f"文档 blocks 提取完成: {len(all_blocks)} 个块")
    except Exception as e:
        logger.error(f"文档 blocks 提取失败: {e}")
        raise ValueError(f"文档解析失败: {str(e)}")
    
    if not all_blocks:
        raise ValueError("文档为空，无法提取范本")
    
    # 2. 策略：优先定位"格式范本"章节，找不到则全文扫描
    chapter_blocks = None
    try:
        chapter_blocks = locate_format_chapter(all_blocks)
        if chapter_blocks and len(chapter_blocks) > 10:  # 至少有10个块才算有效
            logger.info(f"✅ 定位到格式章节: {len(chapter_blocks)} 个块 ({len(chapter_blocks)/len(all_blocks)*100:.1f}%)")
        else:
            logger.warning(f"⚠️ 格式章节太小（{len(chapter_blocks) if chapter_blocks else 0}块），改用全文扫描")
            chapter_blocks = None
    except Exception as e:
        logger.warning(f"格式章节定位失败: {e}")
        chapter_blocks = None
    
    # 如果没有找到格式章节，使用全文
    if not chapter_blocks:
        logger.info("📖 使用全文扫描模式（更全面，但可能识别到非范文内容）")
        chapter_blocks = all_blocks
    
    # 3. LLM 识别范本边界
    try:
        snippet_spans = detect_snippets(chapter_blocks, model_id=model_id)
        logger.info(f"LLM 识别完成: {len(snippet_spans)} 个范本")
    except Exception as e:
        logger.error(f"LLM 识别失败: {e}")
        raise ValueError(f"范本识别失败: {str(e)}")
    
    if not snippet_spans:
        # 如果第一次没识别到，且之前是用格式章节，则尝试全文
        if chapter_blocks != all_blocks:
            logger.warning("格式章节未识别到范本，尝试全文扫描...")
            try:
                snippet_spans = detect_snippets(all_blocks, model_id=model_id)
                logger.info(f"全文扫描识别完成: {len(snippet_spans)} 个范本")
                chapter_blocks = all_blocks  # 切换到全文模式
            except Exception as e2:
                logger.error(f"全文扫描也失败: {e2}")
    
    if not snippet_spans:
        raise ValueError("未识别到任何格式范本，请检查文档内容")
    
    # 4. 验证并切片
    snippets = []
    for span in snippet_spans:
        # 验证边界
        if not validate_snippet_bounds(span, chapter_blocks):
            logger.warning(f"跳过无效范本: {span.get('title')}")
            continue
        
        # 切片 blocks
        snippet_blocks = slice_blocks(
            chapter_blocks,
            span["startBlockId"],
            span["endBlockId"]
        )
        
        if not snippet_blocks:
            logger.warning(f"范本切片失败: {span.get('title')}")
            continue
        
        # ✨ 过滤目录项：如果所有块都是TOC样式，则跳过
        toc_blocks = [b for b in snippet_blocks if 'toc' in b.get('styleName', '').lower()]
        if len(toc_blocks) == len(snippet_blocks):
            logger.warning(f"跳过目录项: {span.get('title')} (全部为TOC样式)")
            continue
        
        # 如果大部分是TOC（>80%），也跳过
        if len(toc_blocks) > len(snippet_blocks) * 0.8:
            logger.warning(f"跳过目录项: {span.get('title')} ({len(toc_blocks)}/{len(snippet_blocks)} 为TOC)")
            continue
        
        # 构建范本记录
        # 使用 project_id + source_file_id + start_block_id + end_block_id 生成确定性ID
        # 确保即使同一个项目有多个相同norm_key的范本，也不会冲突
        import hashlib
        id_string = f"{project_id}_{source_file_id or file_path}_{span['startBlockId']}_{span['endBlockId']}"
        deterministic_id = hashlib.md5(id_string.encode()).hexdigest()[:16]
        
        # 提取纯文本内容
        content_text = blocks_to_text(snippet_blocks, include_tables=True)
        
        snippet = {
            "id": f"snip_{deterministic_id}",
            "project_id": project_id,
            "source_file_id": source_file_id or file_path,
            "norm_key": span["norm_key"],
            "title": span["title"],
            "start_block_id": span["startBlockId"],
            "end_block_id": span["endBlockId"],
            "blocks_json": snippet_blocks,
            "content_text": content_text,
            "suggest_outline_titles": span.get("suggestOutlineTitles", []),
            "confidence": span.get("confidence", 0.5)
        }
        
        snippets.append(snippet)
        logger.info(f"范本提取成功: {snippet['title']} ({len(snippet_blocks)} blocks, {len(content_text)} chars)")
    
    logger.info(f"格式范本提取完成: {len(snippets)} 个有效范本")
    return snippets


def clean_duplicate_snippets(project_id: str, db_pool) -> int:
    """
    清理项目中的重复范文（保留置信度最高的）
    
    按 (project_id, source_file_id, start_block_id, end_block_id) 去重
    只有完全相同位置的范本才会被认为是重复的
    
    Args:
        project_id: 项目ID
        db_pool: 数据库连接池
        
    Returns:
        删除的重复范文数量
    """
    logger.info(f"开始清理项目重复范文: project={project_id}")
    
    with db_pool.connection() as conn:
        with conn.cursor() as cur:
            # 找出重复的范文（同一文件的相同位置）
            cur.execute("""
                WITH ranked_snippets AS (
                    SELECT 
                        id,
                        source_file_id,
                        start_block_id,
                        end_block_id,
                        confidence,
                        ROW_NUMBER() OVER (
                            PARTITION BY project_id, source_file_id, start_block_id, end_block_id
                            ORDER BY confidence DESC, created_at DESC
                        ) as rn
                    FROM tender_format_snippets
                    WHERE project_id = %s
                )
                DELETE FROM tender_format_snippets
                WHERE id IN (
                    SELECT id FROM ranked_snippets WHERE rn > 1
                )
            """, (project_id,))
            
            deleted_count = cur.rowcount
            conn.commit()
            
            logger.info(f"清理完成: 删除了 {deleted_count} 个重复范文")
            return deleted_count


def save_snippets_to_db(snippets: List[Dict[str, Any]], db_pool) -> int:
    """
    将范本保存到数据库
    
    Args:
        snippets: 范本列表
        db_pool: 数据库连接池
        
    Returns:
        保存的范本数量
    """
    import json
    import psycopg
    
    if not snippets:
        return 0
    
    logger.info(f"开始保存范本到数据库: {len(snippets)} 个")
    
    saved_count = 0
    with db_pool.connection() as conn:
        with conn.cursor() as cur:
            for i, snippet in enumerate(snippets, 1):
                try:
                    logger.info(f"  [{i}/{len(snippets)}] 保存: {snippet['title']} (id={snippet['id']}, start={snippet['start_block_id']}, end={snippet['end_block_id']})")
                    
                    # 确保 suggest_outline_titles 是列表
                    suggest_titles = snippet.get("suggest_outline_titles", [])
                    if not isinstance(suggest_titles, list):
                        suggest_titles = []
                    
                    cur.execute(
                        """
                        INSERT INTO tender_format_snippets (
                            id, project_id, source_file_id, norm_key, title,
                            start_block_id, end_block_id, blocks_json, content_text,
                            suggest_outline_titles, confidence
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            content_text = EXCLUDED.content_text,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (
                            snippet["id"],
                            snippet["project_id"],
                            snippet["source_file_id"],
                            snippet["norm_key"],
                            snippet["title"],
                            snippet["start_block_id"],
                            snippet["end_block_id"],
                            json.dumps(snippet["blocks_json"], ensure_ascii=False),
                            snippet.get("content_text", ""),
                            suggest_titles,  # PostgreSQL 会自动处理 Python 列表到 TEXT[] 的转换
                            snippet["confidence"]
                        )
                    )
                    saved_count += 1
                except Exception as e:
                    logger.error(f"保存范本失败: {snippet['title']}, {e}")
            
            conn.commit()
    
    logger.info(f"范本保存完成: {saved_count}/{len(snippets)}")
    return saved_count


def get_snippets_by_project(project_id: str, db_pool) -> List[Dict[str, Any]]:
    """
    获取项目的所有格式范本
    
    Args:
        project_id: 项目 ID
        db_pool: 数据库连接池
        
    Returns:
        范本列表
    """
    import json
    
    with db_pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    id, project_id, source_file_id, norm_key, title,
                    start_block_id, end_block_id, blocks_json, content_text,
                    suggest_outline_titles, confidence, created_at
                FROM tender_format_snippets
                WHERE project_id = %s
                ORDER BY created_at DESC
                """,
                (project_id,)
            )
            
            rows = cur.fetchall()
            
            snippets = []
            for i, row in enumerate(rows):
                try:
                    print(f"Processing row {i}: id={row.get('id')}")
                    
                    # 处理 suggest_outline_titles - PostgreSQL TEXT[] 直接返回为 Python 列表
                    suggest_titles = row.get('suggest_outline_titles')
                    print(f"  suggest_titles type: {type(suggest_titles)}, value: {suggest_titles}")
                    if suggest_titles is None:
                        suggest_titles = []
                    elif not isinstance(suggest_titles, list):
                        # 如果不是列表，尝试转换
                        if isinstance(suggest_titles, str):
                            try:
                                suggest_titles = json.loads(suggest_titles)
                            except:
                                suggest_titles = []
                        else:
                            suggest_titles = []
                    
                    # 处理 blocks_json - PostgreSQL JSONB 直接返回为 Python 对象
                    blocks = row.get('blocks_json')
                    print(f"  blocks type: {type(blocks)}, len: {len(blocks) if isinstance(blocks, list) else 'N/A'}")
                    if blocks is None:
                        blocks = []
                    elif not isinstance(blocks, list):
                        # 如果不是列表，尝试转换
                        if isinstance(blocks, str):
                            try:
                                blocks = json.loads(blocks)
                            except:
                                blocks = []
                        else:
                            blocks = []
                    
                    # 处理 created_at
                    created_at = row.get('created_at')
                    if created_at:
                        try:
                            if hasattr(created_at, 'isoformat'):
                                created_at = created_at.isoformat()
                            else:
                                created_at = str(created_at)
                        except Exception as e:
                            print(f"Warning: Failed to convert created_at: {e}")
                            created_at = None
                    
                    snippet_dict = {
                    "id": row['id'],
                    "project_id": row['project_id'],
                    "source_file_id": row['source_file_id'],
                    "norm_key": row['norm_key'],
                    "title": row['title'],
                    "start_block_id": row['start_block_id'],
                    "end_block_id": row['end_block_id'],
                        "blocks_json": blocks,
                        "content_text": row.get('content_text', ''),
                        "suggest_outline_titles": suggest_titles,
                    "confidence": row['confidence'],
                        "created_at": created_at
                    }
                    print(f"  Created snippet dict successfully")
                    snippets.append(snippet_dict)
                except Exception as e:
                    print(f"Error processing row {row.get('id')}: {e}")
                    import traceback
                    traceback.print_exc()
                    raise
            
            print(f"Returning {len(snippets)} snippets")
            return snippets


def get_snippet_by_id(snippet_id: str, db_pool) -> Optional[Dict[str, Any]]:
    """
    根据 ID 获取范本详情
    
    Args:
        snippet_id: 范本 ID
        db_pool: 数据库连接池
        
    Returns:
        范本详情（包含完整 blocks_json）
    """
    import json
    
    with db_pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    id, project_id, source_file_id, norm_key, title,
                    start_block_id, end_block_id, blocks_json, content_text,
                    suggest_outline_titles, confidence, created_at
                FROM tender_format_snippets
                WHERE id = %s
                """,
                (snippet_id,)
            )
            
            row = cur.fetchone()
            if not row:
                return None
            
            # 处理 suggest_outline_titles - PostgreSQL TEXT[] 直接返回为 Python 列表
            suggest_titles = row.get('suggest_outline_titles')
            if suggest_titles is None:
                suggest_titles = []
            elif not isinstance(suggest_titles, list):
                if isinstance(suggest_titles, str):
                    try:
                        suggest_titles = json.loads(suggest_titles)
                    except:
                        suggest_titles = []
                else:
                    suggest_titles = []
            
            # 处理 blocks_json - PostgreSQL JSONB 直接返回为 Python 对象
            blocks = row.get('blocks_json')
            if blocks is None:
                blocks = []
            elif not isinstance(blocks, list):
                if isinstance(blocks, str):
                    try:
                        blocks = json.loads(blocks)
                    except:
                        blocks = []
                else:
                    blocks = []
            
            return {
                "id": row['id'],
                "project_id": row['project_id'],
                "source_file_id": row['source_file_id'],
                "norm_key": row['norm_key'],
                "title": row['title'],
                "start_block_id": row['start_block_id'],
                "end_block_id": row['end_block_id'],
                "blocks_json": blocks,
                "content_text": row.get('content_text', ''),
                "suggest_outline_titles": suggest_titles,
                "confidence": row['confidence'],
                "created_at": row['created_at'].isoformat() if row.get('created_at') else None
            }

