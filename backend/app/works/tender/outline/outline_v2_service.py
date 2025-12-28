"""
语义目录生成统一入口 (v2)
供 Router/TenderService 调用的统一接口
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from psycopg_pool import ConnectionPool

from app.works.tender.outline import RequirementExtractionService, OutlineSynthesisService
from app.schemas.semantic_outline import (
    OutlineMode,
    OutlineStatus,
    SemanticOutlineNode,
)

logger = logging.getLogger(__name__)


def generate_outline_v2(
    pool: ConnectionPool,
    project_id: str,
    *,
    asset_id: Optional[str] = None,
    owner_id: Optional[str] = None,
    run_id: Optional[str] = None,
    mode: str = "FAST",
    max_depth: int = 5,
    llm_orchestrator: Any = None,
) -> Dict[str, Any]:
    """
    生成语义目录（统一入口）
    
    Args:
        pool: 数据库连接池
        project_id: 项目ID
        asset_id: 资产ID（可选）
        owner_id: 所有者ID（可选）
        run_id: 运行ID（可选）
        mode: 生成模式 FAST/FULL
        max_depth: 最大层级
        llm_orchestrator: LLM编排器
        
    Returns:
        Dict包含:
            - outline_id: 目录ID
            - status: 状态
            - node_count: 节点数量
            - nodes: 节点列表（扁平化）
    """
    logger.info(
        f"generate_outline_v2 start: project_id={project_id}, "
        f"mode={mode}, max_depth={max_depth}"
    )
    
    # 1. 从数据库获取项目chunks（tender文档的segments）
    from app.services.dao.tender_dao import TenderDAO
    
    dao = TenderDAO(pool)
    
    # 获取项目的tender文档chunks
    # 这里需要从 doc_segments 或旧的 kb_chunks 中读取
    # 为了兼容性，先尝试新表，再fallback到旧表
    chunks = []
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # 尝试从新表读取（doc_segments）
                cur.execute(
                    """
                    SELECT ds.segment_id as chunk_id, ds.content, ds.position
                    FROM doc_segments ds
                    JOIN document_versions dv ON ds.doc_version_id = dv.doc_version_id
                    JOIN documents d ON dv.document_id = d.document_id
                    WHERE d.project_id = %s 
                      AND d.doc_type = 'tender'
                      AND dv.is_current = TRUE
                    ORDER BY ds.position
                    """,
                    (project_id,)
                )
                rows = cur.fetchall()
                if rows:
                    chunks = [
                        {
                            "chunk_id": row['chunk_id'],
                            "content": row['content'],
                            "position": row['position'],
                        }
                        for row in rows
                    ]
                    logger.info(f"Loaded {len(chunks)} chunks from doc_segments")
                
                # Fallback：从旧表读取
                if not chunks:
                    cur.execute(
                        """
                        SELECT kc.chunk_id, kc.text as content, kc.position
                        FROM kb_chunks kc
                        JOIN kb_documents kd ON kc.doc_id = kd.doc_id
                        WHERE kd.project_id = %s 
                          AND kd.kind = 'tender'
                        ORDER BY kc.position
                        """,
                        (project_id,)
                    )
                    rows = cur.fetchall()
                    chunks = [
                        {
                            "chunk_id": row['chunk_id'],
                            "content": row['content'],
                            "position": row['position'],
                        }
                        for row in rows
                    ]
                    logger.info(f"Loaded {len(chunks)} chunks from kb_chunks (legacy)")
    
    except Exception as e:
        logger.error(f"Failed to load chunks for project {project_id}: {e}", exc_info=True)
        raise ValueError(f"Failed to load project chunks: {e}")
    
    if not chunks:
        logger.warning(f"No chunks found for project {project_id}")
        return {
            "outline_id": None,
            "status": "failed",
            "message": "未找到招标文档内容",
            "node_count": 0,
            "nodes": [],
        }
    
    # 2. 阶段A：抽取要求项
    req_extraction_service = RequirementExtractionService(llm_orchestrator)
    requirements = req_extraction_service.extract_requirements(chunks, mode=mode)
    
    logger.info(f"Extracted {len(requirements)} requirements")
    
    if not requirements:
        logger.warning("No requirements extracted")
        return {
            "outline_id": None,
            "status": "failed",
            "message": "未能抽取到有效的要求项",
            "node_count": 0,
            "nodes": [],
        }
    
    # 3. 阶段B：合成目录
    outline_synthesis_service = OutlineSynthesisService(llm_orchestrator)
    outline_nodes = outline_synthesis_service.synthesize_outline(
        requirements, mode=mode, max_depth=max_depth
    )
    
    logger.info(f"Synthesized {len(outline_nodes)} L1 nodes")
    
    # 4. 扁平化节点（用于存储到数据库）
    nodes_flat = _flatten_outline_nodes(outline_nodes)
    
    logger.info(f"Total flattened nodes: {len(nodes_flat)}")
    
    # 5. 存储到数据库
    import time
    outline_id = None
    try:
        # 创建outline记录
        outline_id = dao.create_semantic_outline(
            project_id=project_id,
            status="success",
            mode=mode,
            max_depth=max_depth,
            node_count=len(nodes_flat),
            owner_id=owner_id,
        )
        
        # 保存节点
        dao.save_semantic_outline_nodes(outline_id, project_id, nodes_flat)
        
        logger.info(f"Saved outline: outline_id={outline_id}")
        
    except Exception as e:
        logger.error(f"Failed to save outline: {e}", exc_info=True)
        raise ValueError(f"Failed to save outline: {e}")
    
    # 6. 返回结果
    return {
        "outline_id": outline_id,
        "status": "success",
        "mode": mode,
        "max_depth": max_depth,
        "node_count": len(nodes_flat),
        "l1_count": len(outline_nodes),
        "requirement_count": len(requirements),
        "nodes": nodes_flat,
    }


def _flatten_outline_nodes(
    nodes: List[SemanticOutlineNode],
    parent_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    扁平化目录树（递归）
    
    Args:
        nodes: 目录树
        parent_id: 父节点ID
        
    Returns:
        扁平化的节点列表
    """
    flat = []
    
    for node in nodes:
        # 当前节点
        node_dict = {
            "node_id": node.node_id,
            "parent_node_id": parent_id,
            "level": node.level,
            "numbering": node.numbering,
            "title": node.title,
            "summary": node.summary,
            "tags": node.tags,
            "evidence_chunk_ids": node.evidence_chunk_ids,
            "covered_req_ids": node.covered_req_ids,
        }
        flat.append(node_dict)
        
        # 递归处理子节点
        if node.children:
            child_flat = _flatten_outline_nodes(node.children, parent_id=node.node_id)
            flat.extend(child_flat)
    
    return flat

