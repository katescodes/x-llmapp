from fastapi import APIRouter, HTTPException, Depends
from app.models.user import TokenData
from app.utils.auth import get_current_user
from app.utils.permission import require_resource_access, DataFilter
from ..services import history_store

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("/sessions")
def list_sessions(
    page: int = 1, 
    page_size: int = 20,
    current_user: TokenData = Depends(get_current_user)
):
    """
    获取会话列表（仅返回当前用户的会话，管理员可查看所有）
    
    权限要求：chat.view
    """
    # 获取数据过滤条件
    filter_cond = DataFilter.get_owner_filter(current_user, "chat_session")
    
    if filter_cond.get("all"):
        # 管理员可以查看所有会话
        return history_store.list_sessions(page, page_size)
    else:
        # 普通用户只能查看自己的会话
        return history_store.list_sessions(page, page_size, owner_id=filter_cond.get("owner_id"))


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    获取会话详情
    
    权限要求：chat.view
    """
    session = history_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 检查访问权限
    owner_id = session.get("owner_id") or session.get("user_id")
    if owner_id:
        require_resource_access(current_user, owner_id, "chat_session", "session")
    
    return session


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    删除会话
    
    权限要求：chat.delete
    """
    session = history_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 检查访问权限
    owner_id = session.get("owner_id") or session.get("user_id")
    if owner_id:
        require_resource_access(current_user, owner_id, "chat_session", "session")
    
    history_store.delete_session(session_id)
    return {"status": "ok"}

