"""
招标文件格式范本 API
"""
from __future__ import annotations
import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from psycopg_pool import ConnectionPool

from app.utils.auth import get_current_user_sync
from app.services.tender.snippet_extract import (
    extract_format_snippets,
    save_snippets_to_db,
    get_snippets_by_project,
    get_snippet_by_id
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/apps/tender", tags=["格式范本"])


def _get_pool() -> ConnectionPool:
    """从 postgres 模块获取连接池"""
    from app.services.db.postgres import _get_pool as get_sync_pool
    return get_sync_pool()


# ============= Schemas =============

class ExtractSnippetsRequest(BaseModel):
    """提取范本请求"""
    source_file_path: str = Field(..., description="招标文件路径")
    source_file_id: Optional[str] = Field(None, description="来源文件ID")
    model_id: str = Field("gpt-oss-120b", description="LLM模型ID")


class SnippetOut(BaseModel):
    """范本输出"""
    id: str
    project_id: str
    source_file_id: Optional[str]
    norm_key: str
    title: str
    start_block_id: str
    end_block_id: str
    suggest_outline_titles: List[str]
    confidence: float
    created_at: Optional[str]


class SnippetDetailOut(SnippetOut):
    """范本详情输出（包含完整blocks）"""
    blocks_json: List[Dict[str, Any]]


class ApplySnippetRequest(BaseModel):
    """应用范本到节点请求"""
    snippet_id: str = Field(..., description="范本ID")
    mode: str = Field("replace", description="应用模式：replace|append")


class ExtractSnippetsResponse(BaseModel):
    """提取范本响应"""
    snippets: List[SnippetOut]
    total: int
    message: str


# ============= APIs =============

@router.post("/projects/{project_id}/extract-format-snippets", response_model=ExtractSnippetsResponse)
async def extract_snippets_from_file(
    project_id: str,
    request: ExtractSnippetsRequest,
    user=Depends(get_current_user_sync)
):
    """
    从招标文件提取格式范本
    
    工作流程：
    1. 解析文档（DOCX/PDF）提取 blocks
    2. 定位"格式范本"章节
    3. LLM 识别各个范本边界
    4. 切片并保存到数据库
    
    Args:
        project_id: 项目 ID
        request: 提取请求
    
    Returns:
        提取的范本列表
    """
    logger.info(f"开始提取格式范本: project={project_id}, file={request.source_file_path}")
    
    try:
        # 1. 提取范本
        snippets = await extract_format_snippets(
            file_path=request.source_file_path,
            project_id=project_id,
            source_file_id=request.source_file_id,
            model_id=request.model_id
        )
        
        if not snippets:
            raise HTTPException(
                status_code=400,
                detail="未识别到任何格式范本，请检查文档内容"
            )
        
        # 2. 保存到数据库
        db_pool = _get_pool()
        saved_count = save_snippets_to_db(snippets, db_pool)
        
        logger.info(f"范本提取完成: {saved_count} 个范本已保存")
        
        # 3. 返回结果（不包含 blocks_json）
        snippets_out = [
            SnippetOut(
                id=s["id"],
                project_id=s["project_id"],
                source_file_id=s.get("source_file_id"),
                norm_key=s["norm_key"],
                title=s["title"],
                start_block_id=s["start_block_id"],
                end_block_id=s["end_block_id"],
                suggest_outline_titles=s.get("suggest_outline_titles", []),
                confidence=s.get("confidence", 0.5),
                created_at=None  # 新提取的还没有 created_at
            )
            for s in snippets
        ]
        
        return ExtractSnippetsResponse(
            snippets=snippets_out,
            total=len(snippets_out),
            message=f"成功提取 {len(snippets_out)} 个格式范本"
        )
    
    except ValueError as e:
        logger.error(f"范本提取失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"范本提取失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"范本提取失败: {str(e)}")


@router.get("/projects/{project_id}/format-snippets", response_model=List[SnippetOut])
async def list_project_snippets(
    project_id: str,
    user=Depends(get_current_user_sync)
):
    """
    获取项目的所有格式范本
    
    Args:
        project_id: 项目 ID
    
    Returns:
        范本列表
    """
    logger.info(f"获取项目范本列表: project={project_id}")
    
    try:
        db_pool = _get_pool()
        snippets = get_snippets_by_project(project_id, db_pool)
        
        snippets_out = [
            SnippetOut(
                id=s["id"],
                project_id=s["project_id"],
                source_file_id=s.get("source_file_id"),
                norm_key=s["norm_key"],
                title=s["title"],
                start_block_id=s["start_block_id"],
                end_block_id=s["end_block_id"],
                suggest_outline_titles=s.get("suggest_outline_titles", []),
                confidence=s.get("confidence", 0.5),
                created_at=s.get("created_at")
            )
            for s in snippets
        ]
        
        logger.info(f"获取范本列表成功: {len(snippets_out)} 个范本")
        return snippets_out
    
    except Exception as e:
        logger.error(f"获取范本列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取范本列表失败: {str(e)}")


@router.get("/format-snippets/{snippet_id}", response_model=SnippetDetailOut)
async def get_snippet_detail(
    snippet_id: str,
    user=Depends(get_current_user_sync)
):
    """
    获取范本详情（包含完整 blocks_json）
    
    用于：
    - 侧边栏预览
    - 应用到目录节点前查看内容
    
    Args:
        snippet_id: 范本 ID
    
    Returns:
        范本详情
    """
    logger.info(f"获取范本详情: snippet_id={snippet_id}")
    
    try:
        db_pool = _get_pool()
        snippet = get_snippet_by_id(snippet_id, db_pool)
        
        if not snippet:
            raise HTTPException(status_code=404, detail="范本不存在")
        
        return SnippetDetailOut(
            id=snippet["id"],
            project_id=snippet["project_id"],
            source_file_id=snippet.get("source_file_id"),
            norm_key=snippet["norm_key"],
            title=snippet["title"],
            start_block_id=snippet["start_block_id"],
            end_block_id=snippet["end_block_id"],
            blocks_json=snippet.get("blocks_json", []),
            suggest_outline_titles=snippet.get("suggest_outline_titles", []),
            confidence=snippet.get("confidence", 0.5),
            created_at=snippet.get("created_at")
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取范本详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取范本详情失败: {str(e)}")


@router.post("/outline-nodes/{node_id}/apply-snippet")
async def apply_snippet_to_node(
    node_id: str,
    request: ApplySnippetRequest,
    user=Depends(get_current_user_sync)
):
    """
    将格式范本应用到目录节点
    
    应用逻辑：
    1. 获取范本的 blocks_json
    2. 将 blocks 写入节点的正文存储（meta_json.snippet_blocks）
    3. 前端渲染时根据 block 类型显示：
       - paragraph -> <p>
       - table -> <table>
    
    Args:
        node_id: 目录节点 ID
        request: 应用请求
    
    Returns:
        应用结果
    """
    logger.info(f"应用范本到节点: node={node_id}, snippet={request.snippet_id}, mode={request.mode}")
    
    try:
        db_pool = _get_pool()
        
        # 1. 获取范本详情
        snippet = get_snippet_by_id(request.snippet_id, db_pool)
        if not snippet:
            raise HTTPException(status_code=404, detail="范本不存在")
        
        blocks_json = snippet.get("blocks_json", [])
        if not blocks_json:
            raise HTTPException(status_code=400, detail="范本内容为空")
        
        # 2. 更新节点的 meta_json
        import json
        
        with db_pool.connection() as conn:
            with conn.cursor() as cur:
                # 获取当前 meta_json
                cur.execute(
                    "SELECT meta_json FROM tender_directory_nodes WHERE id = %s",
                    (node_id,)
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="目录节点不存在")
                
                meta_json = json.loads(row[0]) if row[0] else {}
                
                # 应用范本
                if request.mode == "replace":
                    meta_json["snippet_blocks"] = blocks_json
                    meta_json["snippet_id"] = request.snippet_id
                elif request.mode == "append":
                    existing_blocks = meta_json.get("snippet_blocks", [])
                    meta_json["snippet_blocks"] = existing_blocks + blocks_json
                    meta_json["snippet_id"] = request.snippet_id
                else:
                    raise HTTPException(status_code=400, detail=f"不支持的应用模式: {request.mode}")
                
                # 更新数据库
                cur.execute(
                    """
                    UPDATE tender_directory_nodes
                    SET meta_json = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (json.dumps(meta_json, ensure_ascii=False), node_id)
                )
                
                conn.commit()
        
        logger.info(f"范本应用成功: {len(blocks_json)} 个块已应用到节点 {node_id}")
        
        return {
            "success": True,
            "message": f"范本 {snippet['title']} 已成功应用",
            "blocks_count": len(blocks_json),
            "node_id": node_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"应用范本失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"应用范本失败: {str(e)}")


@router.delete("/format-snippets/{snippet_id}")
async def delete_snippet(
    snippet_id: str,
    user=Depends(get_current_user_sync)
):
    """
    删除格式范本
    
    Args:
        snippet_id: 范本 ID
    
    Returns:
        删除结果
    """
    logger.info(f"删除范本: snippet_id={snippet_id}")
    
    try:
        db_pool = _get_pool()
        
        with db_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM tender_format_snippets WHERE id = %s",
                    (snippet_id,)
                )
                
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="范本不存在")
                
                conn.commit()
        
        logger.info(f"范本删除成功: {snippet_id}")
        
        return {
            "success": True,
            "message": "范本已删除"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除范本失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除范本失败: {str(e)}")

