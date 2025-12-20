import uuid
from datetime import datetime
from typing import Dict, List, Optional

from psycopg.rows import dict_row

from app.services.db.postgres import get_conn


def _iso(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def create_category(name: str, display_name: str, color: str = "#6b7280", icon: str = "📁", description: str = "") -> str:
    """创建新的知识库分类"""
    category_id = f"cat_{uuid.uuid4().hex[:8]}"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO kb_categories(id, name, display_name, color, icon, description)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (category_id, name, display_name, color, icon, description[:500]),
            )
        conn.commit()
    return category_id


def list_categories() -> List[Dict]:
    """获取所有分类"""
    with get_conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, name, display_name, color, icon, description, created_at
                FROM kb_categories
                ORDER BY created_at ASC
                """
            )
            rows = cur.fetchall()
    result = []
    for row in rows:
        data = dict(row)
        data["created_at"] = _iso(data.get("created_at"))
        result.append(data)
    return result


def get_category(category_id: str) -> Optional[Dict]:
    """获取单个分类"""
    with get_conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, name, display_name, color, icon, description, created_at
                FROM kb_categories WHERE id=%s
                """,
                (category_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    data = dict(row)
    data["created_at"] = _iso(data.get("created_at"))
    return data


def update_category(
    category_id: str,
    display_name: Optional[str] = None,
    color: Optional[str] = None,
    icon: Optional[str] = None,
    description: Optional[str] = None,
) -> None:
    """更新分类信息"""
    updates = []
    params = []
    
    if display_name is not None:
        updates.append("display_name=%s")
        params.append(display_name[:100])
    if color is not None:
        updates.append("color=%s")
        params.append(color[:20])
    if icon is not None:
        updates.append("icon=%s")
        params.append(icon[:10])
    if description is not None:
        updates.append("description=%s")
        params.append(description[:500])
    
    if not updates:
        return
    
    params.append(category_id)
    sql = f"UPDATE kb_categories SET {', '.join(updates)} WHERE id=%s"
    
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()


def delete_category(category_id: str) -> None:
    """删除分类（会将使用该分类的知识库的 category_id 设为 NULL）"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM kb_categories WHERE id=%s", (category_id,))
        conn.commit()


def category_exists(name: str) -> bool:
    """检查分类名称是否已存在"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM kb_categories WHERE name=%s LIMIT 1",
                (name,),
            )
            return cur.fetchone() is not None

