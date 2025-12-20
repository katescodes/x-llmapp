from datetime import datetime

from app.services.db.postgres import get_conn


def should_skip(url: str, content_hash: str) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT content_hash FROM doc_cache WHERE url=%s", (url,))
            row = cur.fetchone()
            if not row:
                return False
            return row[0] == content_hash


def upsert(url: str, content_hash: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO doc_cache(url, content_hash, updated_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (url) DO UPDATE
                SET content_hash = EXCLUDED.content_hash,
                    updated_at = EXCLUDED.updated_at
                """,
                (url, content_hash, datetime.utcnow()),
            )
        conn.commit()

