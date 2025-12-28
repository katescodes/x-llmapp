"""
用户文档管理 API 路由
支持文档上传、分类管理、文档查询和分析
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.utils.permission import require_permission
from app.utils.auth import get_current_user_sync
from app.models.user import TokenData
from app.schemas.user_documents import (
    UserDocCategoryCreateReq,
    UserDocCategoryOut,
    UserDocCategoryUpdateReq,
    UserDocumentAnalyzeReq,
    UserDocumentOut,
    UserDocumentUpdateReq,
)
from app.services.user_document_service import UserDocumentService
from app.services.db.postgres import _get_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user-documents", tags=["user-documents"])


def _get_service(request: Request = None) -> UserDocumentService:
    """获取用户文档服务实例"""
    pool = _get_pool()
    return UserDocumentService(pool)


# ==================== 分类管理 ====================

@router.post("/categories", response_model=UserDocCategoryOut)
def create_category(
    req: UserDocCategoryCreateReq,
    request: Request,
    user: TokenData = Depends(require_permission("tender.userdoc")),
):
    """
    创建文档分类
    
    权限要求：tender.userdoc
    """
    service = _get_service(request)
    
    category = service.create_category(
        project_id=req.project_id,
        category_name=req.category_name,
        category_desc=req.category_desc,
        display_order=req.display_order,
    )
    
    return category


@router.get("/categories", response_model=List[UserDocCategoryOut])
def list_categories(
    project_id: Optional[str] = None,
    request: Request = None,
    user: TokenData = Depends(get_current_user_sync),
):
    """
    列出文档分类
    
    Args:
        project_id: 项目ID（可选，为空则列出所有分类）
    
    权限要求：已登录用户
    """
    service = _get_service(request)
    
    categories = service.list_categories(project_id=project_id)
    
    return categories


@router.get("/categories/{category_id}", response_model=UserDocCategoryOut)
def get_category(
    category_id: str,
    request: Request,
    user: TokenData = Depends(get_current_user_sync),
):
    """
    获取单个分类详情
    
    权限要求：已登录用户
    """
    service = _get_service(request)
    
    category = service.get_category(category_id)
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    return category


@router.patch("/categories/{category_id}", response_model=UserDocCategoryOut)
def update_category(
    category_id: str,
    req: UserDocCategoryUpdateReq,
    request: Request,
    user: TokenData = Depends(require_permission("tender.userdoc")),
):
    """
    更新文档分类
    
    权限要求：tender.userdoc
    """
    service = _get_service(request)
    
    # 检查分类是否存在
    category = service.get_category(category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # 更新分类
    updated_category = service.update_category(
        category_id=category_id,
        category_name=req.category_name,
        category_desc=req.category_desc,
        display_order=req.display_order,
    )
    
    return updated_category


@router.delete("/categories/{category_id}")
def delete_category(
    category_id: str,
    request: Request,
    user: TokenData = Depends(require_permission("tender.userdoc")),
):
    """
    删除文档分类
    
    权限要求：tender.userdoc
    """
    service = _get_service(request)
    
    # 检查分类是否存在
    category = service.get_category(category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # 删除分类
    service.delete_category(category_id)
    
    return {"message": "Category deleted successfully"}


# ==================== 文档管理 ====================

@router.post("/documents", response_model=UserDocumentOut)
async def upload_document(
    project_id: str = Form(...),
    doc_name: str = Form(...),
    file: UploadFile = File(...),
    category_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    doc_tags: Optional[str] = Form(None),  # JSON字符串，前端传递数组
    request: Request = None,
    user: TokenData = Depends(require_permission("tender.userdoc")),
):
    """
    上传用户文档
    
    权限要求：tender.userdoc
    
    - 支持多种文件类型（PDF、Word、图片等）
    - 自动入库到知识库，用于检索
    """
    service = _get_service(request)
    
    # 解析标签
    import json
    tags_list = []
    if doc_tags:
        try:
            tags_list = json.loads(doc_tags)
        except Exception as e:
            logger.warning(f"解析文档标签失败: {e}")
    
    # 上传文档
    try:
        document = await service.upload_document(
            project_id=project_id,
            file=file,
            doc_name=doc_name,
            category_id=category_id,
            description=description,
            doc_tags=tags_list,
            owner_id=user.user_id if user else None,
        )
        
        return document
    except Exception as e:
        logger.error(f"上传文档失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"上传文档失败: {str(e)}")


@router.get("/documents", response_model=List[UserDocumentOut])
def list_documents(
    project_id: Optional[str] = None,
    category_id: Optional[str] = None,
    request: Request = None,
    user: TokenData = Depends(get_current_user_sync),
):
    """
    列出用户文档
    
    Args:
        project_id: 项目ID（可选，为空则列出所有文档）
        category_id: 分类ID（可选）
    
    权限要求：已登录用户
    """
    service = _get_service(request)
    
    documents = service.list_documents(
        project_id=project_id,
        category_id=category_id,
    )
    
    return documents


@router.get("/documents/{doc_id}", response_model=UserDocumentOut)
def get_document(
    doc_id: str,
    request: Request,
    user: TokenData = Depends(get_current_user_sync),
):
    """
    获取单个文档详情
    
    权限要求：已登录用户
    """
    service = _get_service(request)
    
    document = service.get_document(doc_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return document


@router.patch("/documents/{doc_id}", response_model=UserDocumentOut)
def update_document(
    doc_id: str,
    req: UserDocumentUpdateReq,
    request: Request,
    user: TokenData = Depends(require_permission("tender.userdoc")),
):
    """
    更新文档信息
    
    权限要求：tender.userdoc
    """
    service = _get_service(request)
    
    # 检查文档是否存在
    document = service.get_document(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # 更新文档
    updated_document = service.update_document(
        doc_id=doc_id,
        doc_name=req.doc_name,
        category_id=req.category_id,
        description=req.description,
        doc_tags=req.doc_tags,
    )
    
    return updated_document


@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: str,
    request: Request,
    user: TokenData = Depends(require_permission("tender.userdoc")),
):
    """
    删除文档
    
    权限要求：tender.userdoc
    """
    service = _get_service(request)
    
    # 检查文档是否存在
    document = service.get_document(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # 删除文档
    service.delete_document(doc_id)
    
    return {"message": "Document deleted successfully"}


@router.post("/documents/{doc_id}/analyze", response_model=UserDocumentOut)
def analyze_document(
    doc_id: str,
    req: UserDocumentAnalyzeReq,
    request: Request,
    user: TokenData = Depends(require_permission("tender.userdoc")),
):
    """
    使用 AI 分析文档
    
    权限要求：tender.userdoc
    
    - 提取文档摘要
    - 识别关键信息
    - 确定适用场景
    """
    service = _get_service(request)
    
    # 检查文档是否存在
    document = service.get_document(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # 分析文档
    try:
        analyzed_document = service.analyze_document(
            doc_id=doc_id,
            model_id=req.model_id,
        )
        
        return analyzed_document
    except Exception as e:
        logger.error(f"分析文档失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"分析文档失败: {str(e)}")
