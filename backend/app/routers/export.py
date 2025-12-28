"""
文档导出 REST API 路由
提供基于模板的 Word 文档导出接口
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from psycopg_pool import ConnectionPool

from app.services.dao.tender_dao import TenderDAO
from app.services.export.export_service import ExportService
from app.services.export.summary_backfill import (
    backfill_directory_meta_summary,
    get_backfill_statistics,
)
from app.utils.permission import require_permission
from app.utils.auth import get_current_user_sync
from app.models.user import TokenData

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/apps/tender", tags=["export"])


class ExportDocxRequest(BaseModel):
    """导出 Word 文档请求"""
    format_template_id: Optional[str] = None
    include_toc: bool = True
    prefix_numbering: bool = False
    merge_semantic_summary: bool = False


def get_pool(request: Request) -> ConnectionPool:
    """获取数据库连接池"""
    return request.app.state.db_pool


@router.post("/projects/{project_id}/export/docx")
async def export_project_docx(
    project_id: str,
    format_template_id: Optional[str] = Query(None, description="格式模板ID（可选，优先从目录节点获取）"),
    include_toc: bool = Query(True, description="是否包含目录"),
    prefix_numbering: bool = Query(False, description="是否在标题前添加编号"),
    merge_semantic_summary: bool = Query(False, description="是否合并语义目录的summary"),
    pool: ConnectionPool = Depends(get_pool),
    current_user: dict = Depends(get_current_user_sync),
):
    """
    导出项目为 Word 文档
    
    工作流程：
    1. 从 tender_directory_nodes 加载目录树
    2. 确定 format_template_id（优先从根节点 meta_json 获取）
    3. 使用模板母版生成文档（保留页眉页脚）
    4. 按目录树写入标题和正文
    5. 返回 docx 文件
    
    注意：
    - 页眉页脚会从模板中原样保留（包括图片、域代码等）
    - 支持多节文档（A4竖版/A4横版/A3横版）
    - 目录（TOC）需要在 Word 中按 F9 更新页码
    """
    logger.info(
        f"导出文档请求: project_id={project_id}, template={format_template_id}, "
        f"user={current_user.get('username')}"
    )
    
    try:
        # 1. 创建 DAO 和服务
        dao = TenderDAO(pool)
        export_service = ExportService(dao)
        
        # 2. 导出文档
        output_path = await export_service.export_project_to_docx(
            project_id=project_id,
            format_template_id=format_template_id,
            include_toc=include_toc,
            prefix_numbering=prefix_numbering,
            merge_semantic_summary=merge_semantic_summary,
        )
        
        # 3. 返回文件
        if not os.path.exists(output_path):
            raise HTTPException(status_code=500, detail="文档生成失败")
        
        filename = f"project_{project_id}.docx"
        
        logger.info(f"导出成功: {output_path} -> {filename}")
        
        return FileResponse(
            output_path,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=filename,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    
    except ValueError as e:
        logger.error(f"导出失败（参数错误）: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except FileNotFoundError as e:
        logger.error(f"导出失败（文件不存在）: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    
    except Exception as e:
        logger.error(f"导出失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.post("/projects/{project_id}/export/docx-v2", deprecated=True)
async def export_project_docx_post(
    project_id: str,
    req: ExportDocxRequest,
    pool: ConnectionPool = Depends(get_pool),
    current_user: dict = Depends(get_current_user_sync),
):
    """
    导出项目为 Word 文档（POST 版本，支持请求体）
    
    已废弃，推荐使用 GET 版本
    """
    return await export_project_docx(
        project_id=project_id,
        format_template_id=req.format_template_id,
        include_toc=req.include_toc,
        prefix_numbering=req.prefix_numbering,
        merge_semantic_summary=req.merge_semantic_summary,
        pool=pool,
        current_user=current_user,
    )


@router.post("/projects/{project_id}/directory/backfill-summary")
def backfill_summary_from_semantic(
    project_id: str,
    min_title_similarity: float = Query(0.86, ge=0.0, le=1.0, description="title相似度阈值"),
    force_overwrite: bool = Query(False, description="是否强制覆盖已有的summary"),
    pool: ConnectionPool = Depends(get_pool),
    current_user: dict = Depends(get_current_user_sync),
):
    """
    手动回填语义目录的 summary 到项目目录节点
    
    工作流程：
    1. 从 tender_directory_nodes 加载目录节点
    2. 从 tender_semantic_outline_nodes 加载语义目录节点（最新的）
    3. 按 numbering 精确匹配（优先）
    4. 按 title 相似度匹配（兜底）
    5. 批量更新 meta_json.summary
    
    返回：
    - total_updated: 更新的节点数量
    - matched_by_numbering: 通过 numbering 匹配的数量
    - matched_by_title: 通过 title 相似度匹配的数量
    - updated_node_ids: 更新的节点 ID 列表
    """
    logger.info(
        f"手动回填 summary: project_id={project_id}, "
        f"similarity={min_title_similarity}, force={force_overwrite}, "
        f"user={current_user.get('username')}"
    )
    
    try:
        # 1. 创建 DAO 和服务
        dao = TenderDAO(pool)
        export_service = ExportService(dao)
        
        # 2. 获取目录节点
        directory_rows = dao.list_directory(project_id)
        if not directory_rows:
            raise HTTPException(status_code=400, detail="项目没有目录数据")
        
        # 3. 获取语义目录节点
        semantic_rows = dao.get_latest_semantic_outline_nodes(project_id)
        if not semantic_rows:
            raise HTTPException(status_code=400, detail="项目没有语义目录数据")
        
        logger.info(
            f"加载数据: directory={len(directory_rows)}, semantic={len(semantic_rows)}"
        )
        
        # 4. 计算需要更新的节点
        updates = backfill_directory_meta_summary(
            directory_rows=directory_rows,
            semantic_rows=semantic_rows,
            min_title_similarity=min_title_similarity,
            force_overwrite=force_overwrite,
        )
        
        if not updates:
            return {
                "total_updated": 0,
                "matched_by_numbering": 0,
                "matched_by_title": 0,
                "updated_node_ids": [],
                "message": "没有需要回填的节点（所有节点已有 summary 或无法匹配）",
            }
        
        # 5. 批量更新数据库
        count = dao.batch_update_node_meta_json(updates)
        
        # 6. 统计
        stats = get_backfill_statistics(updates)
        stats["database_updated"] = count
        
        # 7. 添加示例节点
        stats["examples"] = [
            {
                "node_id": u["id"],
                "old_summary": u.get("old_summary") or "",
                "new_summary": u.get("new_summary") or "",
                "match_method": u.get("match_method") or "",
            }
            for u in updates[:5]  # 只返回前5个示例
        ]
        
        logger.info(f"回填完成: {stats}")
        
        return stats
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"回填失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"回填失败: {str(e)}")

