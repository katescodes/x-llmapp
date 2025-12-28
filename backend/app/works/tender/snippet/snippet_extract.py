"""
格式范本提取服务
整合文档解析、章节定位、LLM识别，完成端到端提取
"""
from __future__ import annotations
import logging
import uuid
from typing import List, Dict, Any, Optional

from app.works.tender.snippet.doc_blocks import extract_blocks
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
    
    # 2. 定位"格式范本"章节
    try:
        chapter_blocks = locate_format_chapter(all_blocks)
        logger.info(f"格式章节定位完成: {len(chapter_blocks)} 个块")
    except Exception as e:
        logger.warning(f"格式章节定位失败，使用全部blocks: {e}")
        chapter_blocks = all_blocks
    
    if not chapter_blocks:
        logger.warning("格式章节为空，使用全部blocks")
        chapter_blocks = all_blocks
    
    # 3. LLM 识别范本边界
    try:
        snippet_spans = detect_snippets(chapter_blocks, model_id=model_id)
        logger.info(f"LLM 识别完成: {len(snippet_spans)} 个范本")
    except Exception as e:
        logger.error(f"LLM 识别失败: {e}")
        raise ValueError(f"范本识别失败: {str(e)}")
    
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
        
        # 构建范本记录
        snippet = {
            "id": f"snip_{uuid.uuid4().hex[:16]}",
            "project_id": project_id,
            "source_file_id": source_file_id or file_path,
            "norm_key": span["norm_key"],
            "title": span["title"],
            "start_block_id": span["startBlockId"],
            "end_block_id": span["endBlockId"],
            "blocks_json": snippet_blocks,
            "suggest_outline_titles": span.get("suggestOutlineTitles", []),
            "confidence": span.get("confidence", 0.5)
        }
        
        snippets.append(snippet)
        logger.info(f"范本提取成功: {snippet['title']} ({len(snippet_blocks)} blocks)")
    
    logger.info(f"格式范本提取完成: {len(snippets)} 个有效范本")
    return snippets


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
            for snippet in snippets:
                try:
                    cur.execute(
                        """
                        INSERT INTO tender_format_snippets (
                            id, project_id, source_file_id, norm_key, title,
                            start_block_id, end_block_id, blocks_json,
                            suggest_outline_titles, confidence
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (id) DO UPDATE SET
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
                            snippet["suggest_outline_titles"],
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
                    start_block_id, end_block_id, blocks_json,
                    suggest_outline_titles, confidence, created_at
                FROM tender_format_snippets
                WHERE project_id = %s
                ORDER BY created_at DESC
                """,
                (project_id,)
            )
            
            rows = cur.fetchall()
            
            snippets = []
            for row in rows:
                snippets.append({
                    "id": row['id'],
                    "project_id": row['project_id'],
                    "source_file_id": row['source_file_id'],
                    "norm_key": row['norm_key'],
                    "title": row['title'],
                    "start_block_id": row['start_block_id'],
                    "end_block_id": row['end_block_id'],
                    "blocks_json": json.loads(row['blocks_json']) if row.get('blocks_json') else [],
                    "suggest_outline_titles": row.get('suggest_outline_titles') or [],
                    "confidence": row['confidence'],
                    "created_at": row['created_at'].isoformat() if row.get('created_at') else None
                })
            
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
                    start_block_id, end_block_id, blocks_json,
                    suggest_outline_titles, confidence, created_at
                FROM tender_format_snippets
                WHERE id = %s
                """,
                (snippet_id,)
            )
            
            row = cur.fetchone()
            if not row:
                return None
            
            return {
                "id": row['id'],
                "project_id": row['project_id'],
                "source_file_id": row['source_file_id'],
                "norm_key": row['norm_key'],
                "title": row['title'],
                "start_block_id": row['start_block_id'],
                "end_block_id": row['end_block_id'],
                "blocks_json": json.loads(row['blocks_json']) if row.get('blocks_json') else [],
                "suggest_outline_titles": row.get('suggest_outline_titles') or [],
                "confidence": row['confidence'],
                "created_at": row['created_at'].isoformat() if row.get('created_at') else None
            }

