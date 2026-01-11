"""
招标文件格式范本 API
"""
from __future__ import annotations
import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from psycopg_pool import ConnectionPool

from app.utils.permission import require_permission
from app.models.user import TokenData
from app.works.tender.snippet.snippet_extract import (
    extract_format_snippets,
    save_snippets_to_db,
    get_snippets_by_project,
    get_snippet_by_id,
    clean_duplicate_snippets
)
from app.works.tender.snippet.snippet_matcher import (
    match_snippets_to_nodes,
    suggest_manual_matches
)
from app.works.tender.snippet.snippet_applier import (
    apply_snippet_to_node,
    batch_apply_snippets,
    identify_placeholders
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
    content_text: Optional[str] = Field(None, description="范本纯文本内容")
    suggest_outline_titles: List[str]
    confidence: float
    created_at: Optional[str]


class SnippetDetailOut(SnippetOut):
    """范本详情输出（包含完整blocks）"""
    blocks_json: List[Dict[str, Any]]
    content_text: str = Field("", description="范本纯文本内容（完整）")


class ApplySnippetRequest(BaseModel):
    """应用范本到节点请求"""
    snippet_id: str = Field(..., description="范本ID")
    mode: str = Field("replace", description="应用模式：replace|append")


class DirectoryNodeInput(BaseModel):
    """目录节点输入"""
    id: str
    title: str
    level: Optional[int] = None


class MatchSnippetsRequest(BaseModel):
    """匹配范文请求"""
    directory_nodes: List[DirectoryNodeInput] = Field(..., description="目录节点列表")
    confidence_threshold: float = Field(0.7, description="置信度阈值", ge=0.0, le=1.0)


class MatchResult(BaseModel):
    """匹配结果"""
    node_id: str
    node_title: str
    snippet_id: str
    snippet_title: str
    confidence: float
    match_type: str


class MatchSnippetsResponse(BaseModel):
    """匹配范文响应"""
    matches: List[MatchResult]
    unmatched_nodes: List[Dict[str, str]]
    unmatched_snippets: List[Dict[str, str]]
    suggestions: List[Dict[str, Any]]
    stats: Dict[str, Any]


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
    user: TokenData = Depends(require_permission("tender.edit"))
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
        logger.info(f"📝 准备保存 {len(snippets)} 个范文到数据库")
        for i, s in enumerate(snippets, 1):
            logger.info(f"  {i}. {s['title']} (norm_key={s['norm_key']}, confidence={s.get('confidence', 0)})")
        
        saved_count = save_snippets_to_db(snippets, db_pool)
        logger.info(f"✅ 保存完成: {saved_count} 个范文已保存到数据库")
        
        # 3. 清理重复范文（保留置信度最高的）
        logger.info(f"🧹 开始清理重复范文: project={project_id}")
        deleted_count = clean_duplicate_snippets(project_id, db_pool)
        if deleted_count > 0:
            logger.info(f"🗑️ 清理了 {deleted_count} 个重复范文")
        else:
            logger.info(f"✅ 没有重复范文需要清理")
        
        logger.info(f"🎉 范本提取完成: 最终保存 {saved_count - deleted_count} 个范文")
        
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
                content_text=s.get("content_text", "")[:500] + "..." if len(s.get("content_text", "")) > 500 else s.get("content_text", ""),  # 预览版本，截取前500字
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
    user: TokenData = Depends(require_permission("tender.edit"))
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
        
        snippets_out = []
        for s in snippets:
            try:
                # 确保 suggest_outline_titles 是列表
                suggest_titles = s.get("suggest_outline_titles", [])
                if not isinstance(suggest_titles, list):
                    logger.warning(f"suggest_outline_titles is not a list: {type(suggest_titles)}, converting...")
                    suggest_titles = []
                
                snippet_out = SnippetOut(
                id=s["id"],
                project_id=s["project_id"],
                source_file_id=s.get("source_file_id"),
                norm_key=s["norm_key"],
                title=s["title"],
                start_block_id=s["start_block_id"],
                end_block_id=s["end_block_id"],
                    content_text=s.get("content_text", "")[:500] + "..." if len(s.get("content_text", "")) > 500 else s.get("content_text", ""),  # 预览版本
                    suggest_outline_titles=suggest_titles,
                confidence=s.get("confidence", 0.5),
                created_at=s.get("created_at")
            )
                snippets_out.append(snippet_out)
            except Exception as e:
                logger.error(f"Error creating SnippetOut for {s.get('id')}: {e}, data: {s}")
                raise
        
        logger.info(f"获取范本列表成功: {len(snippets_out)} 个范本")
        return snippets_out
    
    except Exception as e:
        logger.error(f"获取范本列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取范本列表失败: {str(e)}")


@router.post("/projects/{project_id}/format-snippets/clean-duplicates")
async def clean_project_duplicate_snippets(
    project_id: str,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """
    清理项目中的重复范文
    
    保留每个 norm_key 置信度最高的范文，删除其他重复项
    
    Args:
        project_id: 项目 ID
    
    Returns:
        删除的重复范文数量
    """
    logger.info(f"清理项目重复范文: project={project_id}")
    
    try:
        db_pool = _get_pool()
        deleted_count = clean_duplicate_snippets(project_id, db_pool)
        
        return {
            "deleted_count": deleted_count,
            "message": f"成功清理 {deleted_count} 个重复范文"
        }
    
    except Exception as e:
        logger.error(f"清理重复范文失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")


@router.get("/format-snippets/{snippet_id}", response_model=SnippetDetailOut)
async def get_snippet_detail(
    snippet_id: str,
    user: TokenData = Depends(require_permission("tender.edit"))
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
            content_text=snippet.get("content_text", ""),
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
async def apply_snippet_to_outline_node(
    node_id: str,
    request: ApplySnippetRequest,
    user: TokenData = Depends(require_permission("tender.edit"))
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
                
                # 优化：避免多次调用list(row.values())
                meta_value = list(row.values())[0] if row else None
                meta_json = json.loads(meta_value) if meta_value else {}
                
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


@router.post("/projects/{project_id}/snippets/match", response_model=MatchSnippetsResponse)
async def match_snippets(
    project_id: str,
    request: MatchSnippetsRequest,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """
    将范文匹配到目录节点
    
    工作流程：
    1. 获取项目的所有范文
    2. 使用匹配算法找到最佳匹配
    3. 返回匹配结果、未匹配列表、建议列表
    
    Args:
        project_id: 项目 ID
        request: 匹配请求（包含目录节点列表）
    
    Returns:
        匹配结果
    """
    logger.info(f"开始匹配范文: project={project_id}, nodes={len(request.directory_nodes)}")
    
    try:
        # 1. 获取项目的所有范文
        db_pool = _get_pool()
        snippets = get_snippets_by_project(project_id, db_pool)
        
        if not snippets:
            raise HTTPException(
                status_code=404,
                detail="项目没有可用的范文，请先提取格式范文"
            )
        
        logger.info(f"获取到 {len(snippets)} 个范文")
        
        # 2. 转换目录节点格式
        directory_nodes = [
            {
                "id": node.id,
                "title": node.title,
                "level": node.level
            }
            for node in request.directory_nodes
        ]
        
        # 3. 执行匹配
        match_result = match_snippets_to_nodes(
            snippets=snippets,
            directory_nodes=directory_nodes,
            confidence_threshold=request.confidence_threshold
        )
        
        # 4. 生成建议
        suggestions = suggest_manual_matches(
            unmatched_nodes=match_result["unmatched_nodes"],
            unmatched_snippets=match_result["unmatched_snippets"]
        )
        
        logger.info(
            f"匹配完成: {len(match_result['matches'])} 个匹配, "
            f"{len(suggestions)} 个建议"
        )
        
        # 5. 构建响应
        return MatchSnippetsResponse(
            matches=[MatchResult(**m) for m in match_result["matches"]],
            unmatched_nodes=match_result["unmatched_nodes"],
            unmatched_snippets=match_result["unmatched_snippets"],
            suggestions=suggestions,
            stats=match_result["stats"]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"匹配范文失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"匹配范文失败: {str(e)}")


@router.delete("/format-snippets/{snippet_id}")
async def delete_snippet(
    snippet_id: str,
    user: TokenData = Depends(require_permission("tender.edit"))
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


# ============= Phase 4: 范文应用 =============

class ApplySnippetRequest(BaseModel):
    """应用范文请求"""
    snippet_id: str = Field(..., description="范文ID")
    node_id: str = Field(..., description="节点ID")
    mode: str = Field("replace", description="应用模式: replace|append")
    auto_fill: bool = Field(True, description="是否自动填充占位符")
    custom_values: Optional[Dict[str, str]] = Field(None, description="自定义填充值")


class ApplySnippetResponse(BaseModel):
    """应用范文响应"""
    success: bool
    node_id: str
    node_title: str
    snippet_id: str
    snippet_title: str
    placeholders_found: int
    placeholders_filled: int
    mode: str
    message: str


class BatchApplyRequest(BaseModel):
    """批量应用范文请求"""
    matches: List[Dict[str, str]] = Field(..., description="匹配列表 [{node_id, snippet_id}]")
    mode: str = Field("replace", description="应用模式")
    auto_fill: bool = Field(True, description="是否自动填充占位符")


class BatchApplyResponse(BaseModel):
    """批量应用范文响应"""
    success_count: int
    failed_count: int
    total: int
    results: List[Dict[str, Any]]
    errors: List[str]


@router.post("/projects/{project_id}/snippets/apply", response_model=ApplySnippetResponse)
async def apply_snippet(
    project_id: str,
    request: ApplySnippetRequest,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """
    将范文应用到节点
    
    Args:
        project_id: 项目ID
        request: 应用请求
    
    Returns:
        应用结果
    """
    logger.info(f"应用范文: project={project_id}, snippet={request.snippet_id}, node={request.node_id}")
    
    try:
        db_pool = _get_pool()
        
        result = apply_snippet_to_node(
            snippet_id=request.snippet_id,
            node_id=request.node_id,
            project_id=project_id,
            db_pool=db_pool,
            mode=request.mode,
            auto_fill=request.auto_fill,
            custom_values=request.custom_values
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        logger.info(f"✅ 范文应用成功: {result['node_title']}")
        return ApplySnippetResponse(**result)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"应用范文失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"应用范文失败: {str(e)}")


@router.post("/projects/{project_id}/snippets/batch-apply", response_model=BatchApplyResponse)
async def batch_apply(
    project_id: str,
    request: BatchApplyRequest,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """
    批量应用范文到节点
    
    Args:
        project_id: 项目ID
        request: 批量应用请求
    
    Returns:
        批量应用结果
    """
    logger.info(f"批量应用范文: project={project_id}, count={len(request.matches)}")
    
    try:
        db_pool = _get_pool()
        
        result = batch_apply_snippets(
            matches=request.matches,
            project_id=project_id,
            db_pool=db_pool,
            mode=request.mode,
            auto_fill=request.auto_fill
        )
        
        logger.info(f"✅ 批量应用完成: {result['success_count']}/{result['total']} 成功")
        return BatchApplyResponse(**result)
    
    except Exception as e:
        logger.error(f"批量应用范文失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量应用范文失败: {str(e)}")


@router.get("/projects/{project_id}/snippets/{snippet_id}/placeholders")
async def get_snippet_placeholders(
    project_id: str,
    snippet_id: str,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """
    获取范文中的占位符
    
    Args:
        project_id: 项目ID
        snippet_id: 范文ID
    
    Returns:
        占位符列表
    """
    logger.info(f"获取范文占位符: project={project_id}, snippet={snippet_id}")
    
    try:
        db_pool = _get_pool()
        snippet = get_snippet_by_id(snippet_id, db_pool)
        
        if not snippet or snippet.get("project_id") != project_id:
            raise HTTPException(status_code=404, detail="范文不存在")
        
        # 将blocks转换为文本
        blocks_json = snippet.get("blocks_json", [])
        text = _blocks_to_text(blocks_json)
        
        # 识别占位符
        placeholders = identify_placeholders(text)
        
        logger.info(f"✅ 找到 {len(placeholders)} 个占位符")
        return {
            "snippet_id": snippet_id,
            "snippet_title": snippet["title"],
            "placeholders": placeholders,
            "total": len(placeholders)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取占位符失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取占位符失败: {str(e)}")


def _blocks_to_text(blocks: List[Dict[str, Any]]) -> str:
    """将blocks转换为文本"""
    parts = []
    for block in blocks:
        block_type = block.get("type", "")
        # 支持多种段落类型
        if block_type in ("p", "paragraph", "heading", "h1", "h2", "h3", "h4", "h5", "h6"):
            text = block.get("text", "").strip()
            if text:
                parts.append(text)
        elif block_type == "table":
            table_data = block.get("data", {})
            rows = table_data.get("rows", [])
            if rows:
                header = rows[0] if len(rows) > 0 else []
                if header:
                    parts.append(" | ".join(str(cell) for cell in header))
                    parts.append(" | ".join(["---"] * len(header)))
                for row in rows[1:]:
                    parts.append(" | ".join(str(cell) for cell in row))
                parts.append("")
    return "\n".join(parts)

