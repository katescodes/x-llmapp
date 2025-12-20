from fastapi import APIRouter, HTTPException
from ..services import history_store

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("/sessions")
def list_sessions(page: int = 1, page_size: int = 20):
    return history_store.list_sessions(page, page_size)


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    session = history_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    session = history_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    history_store.delete_session(session_id)
    return {"status": "ok"}

