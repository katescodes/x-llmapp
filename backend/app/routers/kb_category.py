from typing import List

from fastapi import APIRouter, HTTPException

from ..schemas.kb_category import (
    KbCategoryCreate,
    KbCategoryOut,
    KbCategoryUpdate,
)
from ..services.dao import kb_category_dao

router = APIRouter(prefix="/api/kb-categories", tags=["kb-categories"])


@router.get("", response_model=List[KbCategoryOut])
def list_categories():
    """获取所有知识库分类"""
    return kb_category_dao.list_categories()


@router.post("", response_model=KbCategoryOut)
def create_category(payload: KbCategoryCreate):
    """创建新的知识库分类"""
    # 检查名称是否已存在
    if kb_category_dao.category_exists(payload.name):
        raise HTTPException(status_code=400, detail=f"分类名称 '{payload.name}' 已存在")
    
    category_id = kb_category_dao.create_category(
        name=payload.name,
        display_name=payload.display_name,
        color=payload.color,
        icon=payload.icon,
        description=payload.description or "",
    )
    category = kb_category_dao.get_category(category_id)
    if not category:
        raise HTTPException(status_code=500, detail="创建分类失败")
    return category


@router.put("/{category_id}", response_model=KbCategoryOut)
def update_category(category_id: str, payload: KbCategoryUpdate):
    """更新知识库分类"""
    category = kb_category_dao.get_category(category_id)
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")
    
    try:
        kb_category_dao.update_category(
            category_id=category_id,
            display_name=payload.display_name,
            color=payload.color,
            icon=payload.icon,
            description=payload.description,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"更新失败: {exc}") from exc
    
    updated = kb_category_dao.get_category(category_id)
    if not updated:
        raise HTTPException(status_code=500, detail="更新后获取分类失败")
    return updated


@router.delete("/{category_id}")
def delete_category(category_id: str):
    """删除知识库分类"""
    category = kb_category_dao.get_category(category_id)
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")
    
    try:
        kb_category_dao.delete_category(category_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"删除失败: {exc}") from exc
    
    return {"status": "ok", "message": "分类已删除"}

