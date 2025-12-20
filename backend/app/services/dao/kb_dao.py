import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from psycopg.rows import dict_row

from app.services.db.postgres import get_conn


def _iso(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def create_kb(name: str, description: str = "", category_id: str | None = None) -> str:
    kb_id = uuid.uuid4().hex
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO knowledge_bases(id, name, description, category_id)
                VALUES (%s, %s, %s, %s)
                """,
                (kb_id, name[:200], description[:2000], category_id),
            )
        conn.commit()
    return kb_id


def list_kbs() -> List[Dict]:
    with get_conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT 
                    kb.id, kb.name, kb.description, kb.created_at, kb.updated_at, kb.category_id,
                    cat.name as category_name,
                    cat.display_name as category_display_name,
                    cat.color as category_color,
                    cat.icon as category_icon
                FROM knowledge_bases kb
                LEFT JOIN kb_categories cat ON kb.category_id = cat.id
                ORDER BY kb.created_at DESC
                """
            )
            rows = cur.fetchall()
    result = []
    for row in rows:
        data = dict(row)
        data["created_at"] = _iso(data.get("created_at"))
        data["updated_at"] = _iso(data.get("updated_at"))
        result.append(data)
    return result


def get_kb(kb_id: str) -> Optional[Dict]:
    with get_conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT 
                    kb.id, kb.name, kb.description, kb.created_at, kb.updated_at, kb.category_id,
                    cat.name as category_name,
                    cat.display_name as category_display_name,
                    cat.color as category_color,
                    cat.icon as category_icon
                FROM knowledge_bases kb
                LEFT JOIN kb_categories cat ON kb.category_id = cat.id
                WHERE kb.id=%s
                """,
                (kb_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    data = dict(row)
    data["created_at"] = _iso(data.get("created_at"))
    data["updated_at"] = _iso(data.get("updated_at"))
    return data


def update_kb(kb_id: str, name: str, description: str, category_id: str | None = None) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE knowledge_bases
                SET name=%s, description=%s, category_id=%s, updated_at=now()
                WHERE id=%s
                """,
                (name[:200], description[:2000], category_id, kb_id),
            )
        conn.commit()


def delete_kb(kb_id: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM knowledge_bases WHERE id=%s", (kb_id,))
        conn.commit()


def create_document(
    kb_id: str,
    filename: str,
    source: str,
    status: str,
    meta: dict | None,
    content_hash: str,
    kb_category: str = "general_doc",
) -> str:
    doc_id = uuid.uuid4().hex
    kb_category = (kb_category or "general_doc")[:32]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO kb_documents(
                    id, kb_id, filename, source, content_hash, status, meta_json, kb_category
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    doc_id,
                    kb_id,
                    filename[:255],
                    source,
                    content_hash,
                    status,
                    json.dumps(meta or {}),
                    kb_category,
                ),
            )
        conn.commit()
    return doc_id


def update_document_status(doc_id: str, status: str, meta: dict | None = None) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE kb_documents
                SET status=%s, updated_at=now(), meta_json=%s
                WHERE id=%s
                """,
                (status, json.dumps(meta or {}), doc_id),
            )
        conn.commit()


def get_document(doc_id: str) -> Optional[Dict]:
    with get_conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, kb_id, filename, source, status, created_at, updated_at, meta_json, content_hash, kb_category
                FROM kb_documents
                WHERE id=%s
                """,
                (doc_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            result = dict(row)
            result["meta"] = row["meta_json"] or {}
            result["created_at"] = _iso(result.get("created_at"))
            result["updated_at"] = _iso(result.get("updated_at"))
            result.pop("meta_json", None)
            result["kb_category"] = row.get("kb_category", "general_doc")
            return result


def delete_document(doc_id: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM kb_documents WHERE id=%s", (doc_id,))
        conn.commit()


def document_exists(kb_id: str, content_hash: str) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM kb_documents
                WHERE kb_id=%s AND content_hash=%s AND status='ready'
                LIMIT 1
                """,
                (kb_id, content_hash),
            )
            return cur.fetchone() is not None


def list_documents(kb_id: str) -> List[Dict]:
    with get_conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, filename, source, status, created_at, updated_at, meta_json, kb_category
                FROM kb_documents
                WHERE kb_id=%s
                ORDER BY created_at DESC
                """,
                (kb_id,),
            )
            rows = cur.fetchall()
    documents = []
    for row in rows:
        data = dict(row)
        data["meta"] = row["meta_json"] or {}
        data["created_at"] = _iso(data.get("created_at"))
        data["updated_at"] = _iso(data.get("updated_at"))
        data.pop("meta_json", None)
        data["kb_category"] = row.get("kb_category", "general_doc")
        documents.append(data)
    return documents


def upsert_chunk(
    chunk_id: str,
    kb_id: str,
    doc_id: str,
    title: str | None,
    url: str | None,
    position: int,
    content: str,
    kb_category: str = "general_doc",
) -> None:
    kb_category = (kb_category or "general_doc")[:32]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO kb_chunks(
                    chunk_id, kb_id, doc_id, title, url, position, content, created_at, tsv, kb_category
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, now(),
                    to_tsvector('simple', coalesce(%s,'') || ' ' || coalesce(%s,'') || ' ' || %s),
                    %s
                )
                ON CONFLICT (chunk_id) DO UPDATE SET
                    kb_id = EXCLUDED.kb_id,
                    doc_id = EXCLUDED.doc_id,
                    title = EXCLUDED.title,
                    url = EXCLUDED.url,
                    position = EXCLUDED.position,
                    content = EXCLUDED.content,
                    tsv = EXCLUDED.tsv,
                    kb_category = EXCLUDED.kb_category
                """,
                (
                    chunk_id,
                    kb_id,
                    doc_id,
                    title,
                    url,
                    position,
                    content,
                    title,
                    url,
                    content,
                    kb_category,
                ),
            )
        conn.commit()


def delete_chunks_by_doc(doc_id: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM kb_chunks WHERE doc_id=%s", (doc_id,))
        conn.commit()


def delete_chunks_by_kb(kb_id: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM kb_chunks WHERE kb_id=%s", (kb_id,))
        conn.commit()


def get_kb_names(kb_ids: List[str]) -> Dict[str, str]:
    if not kb_ids:
        return {}
    with get_conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, name FROM knowledge_bases
                WHERE id = ANY(%s)
                """,
                (kb_ids,),
            )
            return {row["id"]: row["name"] for row in cur.fetchall()}


def get_documents_meta(doc_ids: List[str]) -> Dict[str, Dict[str, str]]:
    if not doc_ids:
        return {}
    with get_conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, kb_id, filename, source, status, created_at, updated_at, meta_json, kb_category
                FROM kb_documents
                WHERE id = ANY(%s)
                """,
                (doc_ids,),
            )
            rows = cur.fetchall()
    results: Dict[str, Dict[str, str]] = {}
    for row in rows:
        meta = dict(row)
        meta["meta"] = row["meta_json"] or {}
        meta["created_at"] = _iso(meta.get("created_at"))
        meta["updated_at"] = _iso(meta.get("updated_at"))
        meta.pop("meta_json", None)
        meta["kb_category"] = row.get("kb_category", "general_doc")
        results[row["id"]] = meta
    return results


def get_chunks_by_ids(chunk_ids: List[str]) -> Dict[str, Dict[str, str]]:
    if not chunk_ids:
        return {}
    with get_conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT chunk_id, kb_id, doc_id, title, url, position, content, kb_category
                FROM kb_chunks
                WHERE chunk_id = ANY(%s)
                """,
                (chunk_ids,),
            )
            rows = cur.fetchall()
    return {row["chunk_id"]: dict(row) for row in rows}


def count_chunks_by_doc(doc_id: str) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM kb_chunks WHERE doc_id=%s", (doc_id,))
            row = cur.fetchone()
            return int(row[0] if row else 0)

