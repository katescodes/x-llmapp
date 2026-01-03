"""
申报书应用 - 数据访问层 (DAO)
负责所有数据库操作
"""
from __future__ import annotations

from datetime import datetime
import json
import uuid
from typing import Any, Dict, List, Optional

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def _id(prefix: str) -> str:
    """生成带前缀的UUID"""
    return f"{prefix}_{uuid.uuid4().hex}"


def _serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """序列化数据库行，转换datetime为ISO字符串"""
    if not row:
        return row
    return {
        k: v.isoformat() if isinstance(v, datetime) else v
        for k, v in row.items()
    }


class DeclareDAO:
    """申报书 DAO"""

    def __init__(self, pool: ConnectionPool):
        self.pool = pool

    # ==================== Projects ====================

    def create_project(
        self, kb_id: str, name: str, description: Optional[str] = None, owner_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """创建申报项目"""
        project_id = _id("declare_proj")
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO declare_projects (project_id, kb_id, name, description, owner_id, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                    RETURNING *
                    """,
                    (project_id, kb_id, name, description, owner_id),
                )
                return _serialize_row(cur.fetchone())

    def list_projects(self, owner_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出申报项目"""
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                if owner_id:
                    cur.execute(
                        "SELECT * FROM declare_projects WHERE owner_id=%s ORDER BY created_at DESC",
                        (owner_id,),
                    )
                else:
                    cur.execute("SELECT * FROM declare_projects ORDER BY created_at DESC")
                return [_serialize_row(row) for row in cur.fetchall()]

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """获取项目详情"""
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM declare_projects WHERE project_id=%s", (project_id,))
                row = cur.fetchone()
                return _serialize_row(row) if row else None

    def update_project(
        self,
        project_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """更新项目信息"""
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                updates = []
                params = []
                
                if name is not None:
                    updates.append("name = %s")
                    params.append(name)
                if description is not None:
                    updates.append("description = %s")
                    params.append(description)
                
                if not updates:
                    # 没有更新，直接返回当前项目
                    return self.get_project(project_id)
                
                updates.append("updated_at = NOW()")
                params.append(project_id)
                
                cur.execute(
                    f"UPDATE declare_projects SET {', '.join(updates)} WHERE project_id = %s RETURNING *",
                    tuple(params)
                )
                row = cur.fetchone()
                conn.commit()
                return _serialize_row(row) if row else None

    def delete_project(self, project_id: str):
        """删除项目及所有关联数据"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                # 删除章节
                cur.execute("DELETE FROM declare_sections WHERE project_id = %s", (project_id,))
                # 删除目录节点
                cur.execute("DELETE FROM declare_directory_nodes WHERE project_id = %s", (project_id,))
                # 删除申报要求
                cur.execute("DELETE FROM declare_requirements WHERE project_id = %s", (project_id,))
                # 删除运行记录
                cur.execute("DELETE FROM declare_runs WHERE project_id = %s", (project_id,))
                # 删除资产
                cur.execute("DELETE FROM declare_assets WHERE project_id = %s", (project_id,))
                # 删除项目
                cur.execute("DELETE FROM declare_projects WHERE project_id = %s", (project_id,))
                conn.commit()

    # ==================== Assets ====================

    def create_asset(
        self,
        project_id: str,
        kind: str,
        filename: str,
        asset_type: str = "document",  # 新增参数
        storage_path: Optional[str] = None,
        file_size: Optional[int] = None,
        mime_type: Optional[str] = None,
        document_id: Optional[str] = None,
        doc_version_id: Optional[str] = None,
        meta_json: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """创建资产"""
        asset_id = _id("declare_asset")
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO declare_assets (
                        asset_id, project_id, kind, asset_type, filename, storage_path, file_size, mime_type,
                        document_id, doc_version_id, meta_json, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW(), NOW())
                    RETURNING *
                    """,
                    (
                        asset_id,
                        project_id,
                        kind,
                        asset_type,  # 新增
                        filename,
                        storage_path,
                        file_size,
                        mime_type,
                        document_id,
                        doc_version_id,
                        json.dumps(meta_json or {}),
                    ),
                )
                return _serialize_row(cur.fetchone())

    def list_assets(self, project_id: str, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出资产"""
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                if kind:
                    cur.execute(
                        "SELECT * FROM declare_assets WHERE project_id=%s AND kind=%s ORDER BY created_at DESC",
                        (project_id, kind),
                    )
                else:
                    cur.execute(
                        "SELECT * FROM declare_assets WHERE project_id=%s ORDER BY created_at DESC",
                        (project_id,),
                    )
                return [_serialize_row(row) for row in cur.fetchall()]
    
    def update_asset_meta(self, asset_id: str, meta_json: Dict) -> None:
        """更新资产的meta_json"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE declare_assets SET meta_json=%s::jsonb, updated_at=NOW() WHERE asset_id=%s",
                    (json.dumps(meta_json), asset_id),
                )

    # ==================== Runs ====================

    def create_run(
        self,
        project_id: str,
        task_type: str,
        platform_job_id: Optional[str] = None,
    ) -> str:
        """创建任务运行记录"""
        run_id = _id("declare_run")
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO declare_runs (run_id, project_id, task_type, status, platform_job_id, created_at, updated_at)
                    VALUES (%s, %s, %s, 'pending', %s, NOW(), NOW())
                    """,
                    (run_id, project_id, task_type, platform_job_id),
                )
            conn.commit()
        return run_id

    def update_run(
        self,
        run_id: str,
        status: str,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        result_json: Optional[Dict] = None,
    ):
        """更新任务运行状态"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE declare_runs
                    SET status=%s, progress=%s, message=%s, result_json=%s::jsonb, updated_at=NOW()
                    WHERE run_id=%s
                    """,
                    (status, progress, message, json.dumps(result_json or {}), run_id),
                )
            conn.commit()

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """获取任务运行记录"""
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM declare_runs WHERE run_id=%s", (run_id,))
                row = cur.fetchone()
                return _serialize_row(row) if row else None

    # ==================== Requirements ====================

    def upsert_requirements(
        self,
        project_id: str,
        data_json: Dict[str, Any],
        evidence_chunk_ids: List[str],
        retrieval_trace: Dict[str, Any],
    ):
        """插入或更新申报要求"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO declare_requirements (project_id, data_json, evidence_chunk_ids, retrieval_trace, updated_at)
                    VALUES (%s, %s::jsonb, %s, %s::jsonb, NOW())
                    ON CONFLICT (project_id) DO UPDATE SET
                        data_json=EXCLUDED.data_json,
                        evidence_chunk_ids=EXCLUDED.evidence_chunk_ids,
                        retrieval_trace=EXCLUDED.retrieval_trace,
                        updated_at=NOW()
                    """,
                    (project_id, json.dumps(data_json), evidence_chunk_ids, json.dumps(retrieval_trace)),
                )
            conn.commit()

    def get_requirements(self, project_id: str) -> Optional[Dict[str, Any]]:
        """获取申报要求"""
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM declare_requirements WHERE project_id=%s", (project_id,))
                row = cur.fetchone()
                return _serialize_row(row) if row else None

    # ==================== Directory (版本化) ====================

    def create_directory_version(
        self, 
        project_id: str, 
        source: str = "notice", 
        run_id: Optional[str] = None,
        project_type: str = "默认",
        project_description: Optional[str] = None
    ) -> str:
        """创建目录版本"""
        version_id = _id("declare_dir_ver")
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO declare_directory_versions 
                    (version_id, project_id, source, run_id, project_type, project_description, created_at, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW(), FALSE)
                    """,
                    (version_id, project_id, source, run_id, project_type, project_description),
                )
            conn.commit()
        return version_id

    def upsert_directory_nodes(self, version_id: str, project_id: str, nodes: List[Dict[str, Any]]):
        """批量插入目录节点"""
        if not nodes:
            return
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                # 清除旧版本节点
                cur.execute("DELETE FROM declare_directory_nodes WHERE version_id=%s", (version_id,))
                # 批量插入
                for node in nodes:
                    # 构建 meta_json，包含 notes 等额外信息
                    meta_json = node.get("meta_json", {})
                    if isinstance(meta_json, dict):
                        meta_json = meta_json.copy()
                    else:
                        meta_json = {}
                    
                    # 如果节点有 notes 字段，存入 meta_json
                    if "notes" in node and node.get("notes"):
                        meta_json["notes"] = node["notes"]
                    
                    cur.execute(
                        """
                        INSERT INTO declare_directory_nodes (
                            id, version_id, project_id, parent_id, order_no, numbering, level, title,
                            is_required, source, evidence_chunk_ids_json, meta_json, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, NOW())
                        """,
                        (
                            node.get("id") or _id("declare_node"),
                            version_id,
                            project_id,
                            node.get("parent_id"),
                            node.get("order_no", 0),
                            node.get("numbering", ""),
                            node.get("level", 1),
                            node.get("title", ""),
                            node.get("required", node.get("is_required", True)),
                            node.get("source", "notice"),
                            json.dumps(node.get("evidence_chunk_ids", [])),
                            json.dumps(meta_json),
                        ),
                    )
            conn.commit()

    def set_active_directory_version(self, project_id: str, version_id: str):
        """设置活跃目录版本"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                # 禁用旧版本
                cur.execute(
                    "UPDATE declare_directory_versions SET is_active=FALSE WHERE project_id=%s AND version_id!=%s",
                    (project_id, version_id),
                )
                # 激活新版本
                cur.execute(
                    "UPDATE declare_directory_versions SET is_active=TRUE WHERE version_id=%s",
                    (version_id,),
                )
            conn.commit()

    def get_active_directory_nodes(self, project_id: str) -> List[Dict[str, Any]]:
        """获取活跃目录节点"""
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT dn.*
                    FROM declare_directory_nodes dn
                    JOIN declare_directory_versions dv ON dn.version_id=dv.version_id
                    WHERE dn.project_id=%s AND dv.is_active=TRUE
                    ORDER BY dn.order_no
                    """,
                    (project_id,),
                )
                return [_serialize_row(row) for row in cur.fetchall()]
    
    def get_all_directory_versions(self, project_id: str) -> List[Dict[str, Any]]:
        """获取项目的所有目录版本（按项目类型分组）"""
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT 
                        version_id,
                        project_id,
                        project_type,
                        project_description,
                        source,
                        is_active,
                        created_at
                    FROM declare_directory_versions
                    WHERE project_id=%s
                    ORDER BY created_at DESC, project_type
                    """,
                    (project_id,),
                )
                return [_serialize_row(row) for row in cur.fetchall()]
    
    def get_directory_nodes_by_version(self, version_id: str) -> List[Dict[str, Any]]:
        """根据版本ID获取目录节点"""
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM declare_directory_nodes
                    WHERE version_id=%s
                    ORDER BY order_no
                    """,
                    (version_id,),
                )
                return [_serialize_row(row) for row in cur.fetchall()]

    # ==================== Sections (版本化) ====================

    def create_sections_version(self, project_id: str, run_id: Optional[str] = None) -> str:
        """创建章节版本"""
        version_id = _id("declare_sec_ver")
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO declare_sections_versions (version_id, project_id, run_id, created_at, is_active)
                    VALUES (%s, %s, %s, NOW(), FALSE)
                    """,
                    (version_id, project_id, run_id),
                )
            conn.commit()
        return version_id

    def upsert_section(
        self,
        version_id: str,
        project_id: str,
        node_id: str,
        node_title: str,
        content_md: str,
        evidence_chunk_ids: List[str],
        retrieval_trace: Dict[str, Any],
        meta_json: Optional[Dict] = None,
    ):
        """插入或更新章节"""
        section_id = _id("declare_sec")
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO declare_sections (
                        section_id, version_id, project_id, node_id, node_title, content_md,
                        evidence_chunk_ids, retrieval_trace, meta_json, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, NOW(), NOW())
                    ON CONFLICT (section_id) DO UPDATE SET
                        content_md=EXCLUDED.content_md,
                        evidence_chunk_ids=EXCLUDED.evidence_chunk_ids,
                        retrieval_trace=EXCLUDED.retrieval_trace,
                        updated_at=NOW()
                    """,
                    (
                        section_id,
                        version_id,
                        project_id,
                        node_id,
                        node_title,
                        content_md,
                        evidence_chunk_ids,
                        json.dumps(retrieval_trace),
                        json.dumps(meta_json or {}),
                    ),
                )
            conn.commit()

    def set_active_sections_version(self, project_id: str, version_id: str):
        """设置活跃章节版本"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                # 禁用旧版本
                cur.execute(
                    "UPDATE declare_sections_versions SET is_active=FALSE WHERE project_id=%s AND version_id!=%s",
                    (project_id, version_id),
                )
                # 激活新版本
                cur.execute(
                    "UPDATE declare_sections_versions SET is_active=TRUE WHERE version_id=%s",
                    (version_id,),
                )
            conn.commit()

    def get_active_sections(self, project_id: str, node_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取活跃章节"""
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                if node_id:
                    cur.execute(
                        """
                        SELECT ds.*
                        FROM declare_sections ds
                        JOIN declare_sections_versions dsv ON ds.version_id=dsv.version_id
                        WHERE ds.project_id=%s AND dsv.is_active=TRUE AND ds.node_id=%s
                        """,
                        (project_id, node_id),
                    )
                else:
                    cur.execute(
                        """
                        SELECT ds.*
                        FROM declare_sections ds
                        JOIN declare_sections_versions dsv ON ds.version_id=dsv.version_id
                        WHERE ds.project_id=%s AND dsv.is_active=TRUE
                        ORDER BY ds.created_at
                        """,
                        (project_id,),
                    )
                return [_serialize_row(row) for row in cur.fetchall()]

    # ==================== Documents ====================

    def create_document(
        self,
        project_id: str,
        filename: str,
        storage_path: str,
        file_size: int,
        format: str = "docx",
        version_id: Optional[str] = None,
        meta_json: Optional[Dict] = None,
    ) -> str:
        """创建文档记录"""
        document_id = _id("declare_doc")
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO declare_documents (
                        document_id, project_id, filename, storage_path, file_size, format, version_id, meta_json, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
                    """,
                    (
                        document_id,
                        project_id,
                        filename,
                        storage_path,
                        file_size,
                        format,
                        version_id,
                        json.dumps(meta_json or {}),
                    ),
                )
            conn.commit()
        return document_id

    def get_latest_document(self, project_id: str) -> Optional[Dict[str, Any]]:
        """获取最新文档"""
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM declare_documents WHERE project_id=%s ORDER BY created_at DESC LIMIT 1",
                    (project_id,),
                )
                row = cur.fetchone()
                return _serialize_row(row) if row else None

