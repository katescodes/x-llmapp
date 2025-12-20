"""
DocStore 服务 - 统一文档管理
提供跨业务系统的文档存储、版本管理、片段管理等功能
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Any, Dict, List, Optional

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def _doc_id(prefix: str = "doc") -> str:
    """生成文档 ID"""
    return f"{prefix}_{uuid.uuid4().hex}"


def _doc_version_id(prefix: str = "dv") -> str:
    """生成文档版本 ID"""
    return f"{prefix}_{uuid.uuid4().hex}"


def _segment_id(prefix: str = "seg") -> str:
    """生成片段 ID"""
    return f"{prefix}_{uuid.uuid4().hex}"


def _compute_sha256(content: bytes) -> str:
    """计算 SHA256 哈希"""
    return hashlib.sha256(content).hexdigest()


class DocStoreService:
    """DocStore 文档管理服务"""

    def __init__(self, pool: ConnectionPool):
        """
        初始化服务
        
        Args:
            pool: PostgreSQL 连接池
        """
        self.pool = pool

    def create_document(
        self,
        namespace: str,
        doc_type: str,
        owner_id: Optional[str] = None
    ) -> str:
        """
        创建文档（逻辑文档）
        
        Args:
            namespace: 业务命名空间，如 "tender"
            doc_type: 文档类型，如 "tender", "bid", "template", "custom_rule"
            owner_id: 文档所有者ID
            
        Returns:
            document_id: 文档ID
        """
        doc_id = _doc_id()
        
        sql = """
            INSERT INTO documents (id, namespace, doc_type, owner_id, created_at)
            VALUES (%s, %s, %s, %s, now())
        """
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (doc_id, namespace, doc_type, owner_id))
        
        return doc_id

    def create_document_version(
        self,
        document_id: str,
        filename: str,
        file_content: bytes,
        storage_path: Optional[str] = None
    ) -> str:
        """
        创建文档版本
        
        Args:
            document_id: 文档ID
            filename: 文件名
            file_content: 文件内容（用于计算哈希）
            storage_path: 存储路径（可选）
            
        Returns:
            version_id: 版本ID
        """
        version_id = _doc_version_id()
        sha256 = _compute_sha256(file_content)
        
        sql = """
            INSERT INTO document_versions (
                id, document_id, sha256, filename, storage_path, created_at
            ) VALUES (%s, %s, %s, %s, %s, now())
        """
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (version_id, document_id, sha256, filename, storage_path))
        
        return version_id

    def create_segments(
        self,
        doc_version_id: str,
        segments: List[Dict[str, Any]]
    ) -> List[str]:
        """
        批量创建文档片段
        
        Args:
            doc_version_id: 文档版本ID
            segments: 片段列表，每个片段包含：
                - segment_no: 片段序号
                - content_text: 文本内容
                - meta_json: 元数据（可选）
                
        Returns:
            segment_ids: 片段ID列表
        """
        segment_ids = []
        
        sql = """
            INSERT INTO doc_segments (
                id, doc_version_id, segment_no, content_text, meta_json, created_at
            ) VALUES (%s, %s, %s, %s, %s::jsonb, now())
        """
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                for seg in segments:
                    seg_id = _segment_id()
                    segment_ids.append(seg_id)
                    
                    # 将 meta_json 转换为 JSON 字符串
                    import json
                    meta_json_str = json.dumps(seg.get("meta_json", {}))
                    
                    cur.execute(sql, (
                        seg_id,
                        doc_version_id,
                        seg.get("segment_no", 0),
                        seg.get("content_text", ""),
                        meta_json_str
                    ))
        
        return segment_ids

    def get_document_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """
        获取文档版本信息
        
        Args:
            version_id: 版本ID
            
        Returns:
            版本信息字典或 None
        """
        sql = """
            SELECT id, document_id, sha256, filename, storage_path, created_at
            FROM document_versions
            WHERE id = %s
        """
        
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, (version_id,))
                return cur.fetchone()

    def get_segments_by_version(
        self,
        doc_version_id: str,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        获取文档版本的所有片段
        
        Args:
            doc_version_id: 文档版本ID
            limit: 最大返回数量
            
        Returns:
            片段列表
        """
        sql = """
            SELECT id, doc_version_id, segment_no, content_text, meta_json, created_at
            FROM doc_segments
            WHERE doc_version_id = %s
            ORDER BY segment_no
            LIMIT %s
        """
        
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, (doc_version_id, limit))
                return list(cur.fetchall())

    def count_segments_by_version(self, doc_version_id: str) -> int:
        """
        统计文档版本的片段数量
        
        Args:
            doc_version_id: 文档版本ID
            
        Returns:
            片段数量
        """
        sql = """
            SELECT COUNT(*) FROM doc_segments
            WHERE doc_version_id = %s
        """
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (doc_version_id,))
                row = cur.fetchone()
                return int(row[0] if row else 0)

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        获取文档信息
        
        Args:
            document_id: 文档ID
            
        Returns:
            文档信息字典或 None
        """
        sql = """
            SELECT id, namespace, doc_type, owner_id, created_at
            FROM documents
            WHERE id = %s
        """
        
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, (document_id,))
                return cur.fetchone()

    def get_latest_version_by_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        获取文档的最新版本
        
        Args:
            document_id: 文档ID
            
        Returns:
            最新版本信息或 None
        """
        sql = """
            SELECT id, document_id, sha256, filename, storage_path, created_at
            FROM document_versions
            WHERE document_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """
        
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, (document_id,))
                return cur.fetchone()

