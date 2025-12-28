from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Depends

from ..schemas.kb import (
    DocumentOut,
    ImportResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    KnowledgeBaseUpdate,
)
from ..services import kb_service
from ..schemas.types import KbCategory
from app.models.user import TokenData
from app.utils.auth import get_current_user
from app.utils.permission import require_permission, require_resource_access, DataFilter

router = APIRouter(prefix="/api/kb", tags=["knowledge-base"])


@router.get("", response_model=List[KnowledgeBaseOut])
def list_kbs(current_user: TokenData = Depends(get_current_user)):
    """
    获取知识库列表
    
    - 管理员可以看到所有知识库
    - 普通用户只能看到自己创建的知识库
    """
    # 获取数据过滤条件
    filter_cond = DataFilter.get_owner_filter(current_user, "knowledge_base")
    
    if filter_cond.get("all"):
        # 管理员可以查看所有知识库
        return kb_service.list_kbs()
    else:
        # 普通用户只能查看自己的知识库
        owner_id = filter_cond.get("owner_id")
        return kb_service.list_kbs_by_owner(owner_id)


@router.post("", response_model=KnowledgeBaseOut)
def create_kb(
    payload: KnowledgeBaseCreate,
    current_user: TokenData = Depends(require_permission("kb.create"))
):
    """
    创建知识库
    
    权限要求：kb.create
    """
    # 创建知识库时自动设置 owner_id
    kb_id = kb_service.create_kb(
        payload.name, 
        payload.description or "", 
        payload.category_id,
        owner_id=current_user.user_id
    )
    return kb_service.get_kb_or_raise(kb_id)


@router.put("/{kb_id}", response_model=KnowledgeBaseOut)
def update_kb(
    kb_id: str, 
    payload: KnowledgeBaseUpdate,
    current_user: TokenData = Depends(require_permission("kb.edit"))
):
    """
    更新知识库
    
    权限要求：kb.edit
    只能修改自己创建的知识库（管理员可以修改所有）
    """
    try:
        # 检查访问权限
        kb = kb_service.get_kb_or_raise(kb_id)
        owner_id = kb.get("owner_id")
        if owner_id:
            require_resource_access(current_user, owner_id, "knowledge_base", "knowledge base")
        
        kb_service.update_kb(kb_id, payload.name, payload.description, payload.category_id)
    except ValueError as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return kb_service.get_kb_or_raise(kb_id)


@router.delete("/{kb_id}")
def delete_kb(
    kb_id: str,
    current_user: TokenData = Depends(require_permission("kb.delete"))
):
    """
    删除知识库
    
    权限要求：kb.delete
    只能删除自己创建的知识库（管理员可以删除所有）
    """
    try:
        # 检查访问权限
        kb = kb_service.get_kb_or_raise(kb_id)
        owner_id = kb.get("owner_id")
        if owner_id:
            require_resource_access(current_user, owner_id, "knowledge_base", "knowledge base")
        
        kb_service.delete_kb(kb_id)
    except ValueError as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "ok"}


@router.get("/{kb_id}/docs", response_model=List[DocumentOut])
def list_docs(
    kb_id: str,
    current_user: TokenData = Depends(require_permission("kb.view"))
):
    """
    获取知识库文档列表
    
    权限要求：kb.view
    """
    try:
        # 检查访问权限
        kb = kb_service.get_kb_or_raise(kb_id)
        owner_id = kb.get("owner_id")
        if owner_id:
            require_resource_access(current_user, owner_id, "knowledge_base", "knowledge base")
        
        docs = kb_service.list_documents(kb_id)
    except ValueError as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return docs


@router.delete("/{kb_id}/docs/{doc_id}")
def delete_doc(
    kb_id: str, 
    doc_id: str,
    current_user: TokenData = Depends(require_permission("kb.delete"))
):
    """
    删除知识库文档
    
    权限要求：kb.delete
    """
    try:
        # 检查访问权限
        kb = kb_service.get_kb_or_raise(kb_id)
        owner_id = kb.get("owner_id")
        if owner_id:
            require_resource_access(current_user, owner_id, "knowledge_base", "knowledge base")
        
        kb_service.delete_document(kb_id, doc_id)
    except ValueError as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "ok"}


@router.post("/{kb_id}/import", response_model=ImportResponse)
async def import_docs(
    kb_id: str,
    files: List[UploadFile] = File(...),
    kb_category: KbCategory = Form("general_doc"),
    current_user: TokenData = Depends(require_permission("kb.upload"))
):
    """
    上传文档到知识库
    
    权限要求：kb.upload
    """
    # 检查访问权限
    kb = kb_service.get_kb_or_raise(kb_id)
    owner_id = kb.get("owner_id")
    if owner_id:
        require_resource_access(current_user, owner_id, "knowledge_base", "knowledge base")
    
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个文件")
    results = []
    for upload in files:
        try:
            data = await upload.read()
            if not data:
                results.append(
                    {
                        "filename": upload.filename or "unknown",
                        "status": "failed",
                        "error": "文件内容为空",
                    }
                )
                continue
            result = await kb_service.import_document(
                kb_id,
                upload.filename or "unnamed",
                data,
                kb_category=kb_category,
            )
            results.append(result)
        except ValueError as exc:
            results.append(
                {
                    "filename": upload.filename or "unknown",
                    "status": "failed",
                    "error": str(exc),
                }
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "filename": upload.filename or "unknown",
                    "status": "failed",
                    "error": f"导入失败: {exc}",
                }
            )
    return ImportResponse(items=results)

