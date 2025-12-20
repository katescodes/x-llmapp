import json
import uuid
from typing import List, Optional

from psycopg.rows import dict_row

from app.services.db.postgres import get_conn


def create_session(
    title: str,
    default_kb_ids: List[str],
    search_mode: str,
    model_id: str | None,
) -> str:
    session_id = uuid.uuid4().hex
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_sessions(
                    id, title, default_kb_ids_json, search_mode, model_id, meta_json, summary
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session_id,
                    title[:200],
                    json.dumps(default_kb_ids),
                    search_mode,
                    model_id,
                    json.dumps({}),
                    None,
                ),
            )
        conn.commit()
    return session_id


def append_message(
    session_id: str,
    role: str,
    content: str,
    metadata: dict | None = None,
) -> str:
    message_id = uuid.uuid4().hex
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_messages(id, session_id, role, content, metadata_json)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (message_id, session_id, role, content, json.dumps(metadata or {})),
            )
            cur.execute(
                "UPDATE chat_sessions SET updated_at=now() WHERE id=%s",
                (session_id,),
            )
        conn.commit()
    return message_id


def list_sessions(page: int, page_size: int) -> List[dict]:
    offset = max(0, (page - 1) * page_size)
    with get_conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, title, created_at, updated_at, default_kb_ids_json, search_mode, model_id, meta_json, summary
                FROM chat_sessions
                ORDER BY updated_at DESC
                LIMIT %s OFFSET %s
                """,
                (page_size, offset),
            )
            rows = cur.fetchall()
    sessions = []
    for row in rows:
        data = dict(row)
        data["default_kb_ids"] = row["default_kb_ids_json"] or []
        data["meta"] = row["meta_json"] or {}
        data["summary"] = row.get("summary")
        data.pop("default_kb_ids_json", None)
        data.pop("meta_json", None)
        sessions.append(data)
    return sessions


def get_session(session_id: str) -> Optional[dict]:
    with get_conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, title, created_at, updated_at, default_kb_ids_json, search_mode, model_id, meta_json, summary
                FROM chat_sessions
                WHERE id=%s
                """,
                (session_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    data = dict(row)
    data["default_kb_ids"] = row["default_kb_ids_json"] or []
    data["meta"] = row["meta_json"] or {}
    data["summary"] = row.get("summary")
    data.pop("default_kb_ids_json", None)
    data.pop("meta_json", None)
    return data


def get_session_with_messages(session_id: str) -> Optional[dict]:
    session = get_session(session_id)
    if not session:
        return None
    with get_conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, role, content, created_at, metadata_json
                FROM chat_messages
                WHERE session_id=%s
                ORDER BY created_at ASC
                """,
                (session_id,),
            )
            rows = cur.fetchall()
    messages = []
    for row in rows:
        msg = dict(row)
        msg["metadata"] = row["metadata_json"] or {}
        msg.pop("metadata_json", None)
        messages.append(msg)
    session["messages"] = messages
    return session


def update_session_kb_ids(session_id: str, kb_ids: List[str]) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE chat_sessions
                SET default_kb_ids_json=%s, updated_at=now()
                WHERE id=%s
                """,
                (json.dumps(kb_ids), session_id),
            )
        conn.commit()


def update_session_meta(session_id: str, patch: dict) -> None:
    if not patch:
        return
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE chat_sessions
                SET meta_json = coalesce(meta_json, '{}'::jsonb) || %s::jsonb,
                    updated_at=now()
                WHERE id=%s
                """,
                (json.dumps(patch), session_id),
            )
        conn.commit()


def update_session_summary(session_id: str, summary: Optional[str]) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE chat_sessions
                SET summary=%s,
                    updated_at=now()
                WHERE id=%s
                """,
                (summary, session_id),
            )
        conn.commit()


def delete_session(session_id: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chat_sessions WHERE id=%s", (session_id,))
        conn.commit()

