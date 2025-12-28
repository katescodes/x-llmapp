from typing import List, Optional

from ..services.dao import chat_dao


def create_session(
    title: str,
    default_kb_ids: List[str],
    search_mode: str,
    model_id: Optional[str],
    owner_id: Optional[str] = None,
) -> str:
    return chat_dao.create_session(title, default_kb_ids, search_mode, model_id, owner_id)


def append_message(session_id: str, role: str, content: str, metadata: Optional[dict] = None) -> str:
    return chat_dao.append_message(session_id, role, content, metadata)


def list_sessions(page: int = 1, page_size: int = 20, owner_id: Optional[str] = None):
    return chat_dao.list_sessions(page, page_size, owner_id)


def get_session(session_id: str):
    return chat_dao.get_session_with_messages(session_id)


def update_session_kb_ids(session_id: str, kb_ids: List[str]):
    chat_dao.update_session_kb_ids(session_id, kb_ids)


def update_session_meta(session_id: str, patch: dict):
    chat_dao.update_session_meta(session_id, patch)


def update_session_summary(session_id: str, summary: Optional[str]):
    chat_dao.update_session_summary(session_id, summary)


def delete_session(session_id: str):
    chat_dao.delete_session(session_id)
