"""
招投标应用 - 数据访问层 (DAO)
负责所有数据库操作，包括轻量级 KB 入库
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def _id(prefix: str) -> str:
    """生成带前缀的UUID"""
    return f"{prefix}_{uuid.uuid4().hex}"


# ==================== 目录排序工具函数 ====================

_num_re = re.compile(r"^\d+$")

def _parse_numbering_key(numbering: str):
    """
    解析编号为排序键
    "1.2.10" -> (1, 2, 10)
    非数字片段放到末尾确保稳定
    """
    parts = (numbering or "").strip().strip(".").split(".")
    key = []
    for p in parts:
        p = p.strip()
        if _num_re.match(p):
            key.append(int(p))
        else:
            # 非数字：放一个很大的数并附加字符串，保证稳定
            key.append(10**9)
            key.append(p)
    return tuple(key)

def _infer_parent_numbering(numbering: str) -> Optional[str]:
    """
    推导父节点编号
    "1.2.3" -> "1.2"
    "1" -> None
    """
    if not numbering:
        return None
    s = numbering.strip().strip(".")
    if "." not in s:
        return None
    return s.rsplit(".", 1)[0]

def _stable_node_id(project_id: str, numbering: str, fallback_idx: int) -> str:
    """
    生成稳定的节点ID
    尽量基于 project_id + numbering，确保同一项目同一编号ID固定。
    注意：模板 outline 可能出现重复 numbering（例如同级 order_no 重复），仅用 numbering 会导致主键冲突；
    因此这里把 fallback_idx 一并纳入稳定 key，确保同一批次 replace_directory 内也能稳定且唯一。
    """
    if numbering:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"tender:{project_id}:{numbering}:{fallback_idx}"))
    return f"tdn_{uuid.uuid4().hex}_{fallback_idx}"


class TenderDAO:
    """招投标 DAO + 轻量 KB 入库"""

    def __init__(self, pool: ConnectionPool):
        """
        初始化 DAO
        
        Args:
            pool: PostgreSQL 连接池（同步）
        """
        self.pool = pool

    # ==================== 工具方法 ====================

    def _fetchone(self, sql: str, params: Tuple = ()) -> Optional[Dict[str, Any]]:
        """执行查询并返回单行"""
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                return cur.fetchone()

    def _fetchall(self, sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """执行查询并返回所有行"""
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                return list(cur.fetchall())

    def _execute(self, sql: str, params: Tuple = ()) -> None:
        """执行 SQL 语句（无返回值）"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.commit()

    # ==================== 项目管理 ====================

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """获取项目信息"""
        return self._fetchone(
            "SELECT id, kb_id, name, description, created_at FROM tender_projects WHERE id=%s",
            (project_id,),
        )

    def create_project(self, kb_id: str, name: str, description: Optional[str], owner_id: Optional[str]) -> Dict[str, Any]:
        """创建项目"""
        pid = _id("tp")
        row = self._fetchone(
            """
            INSERT INTO tender_projects (id, kb_id, name, description, owner_id, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            RETURNING id, kb_id, name, description, owner_id, created_at
            """,
            (pid, kb_id, name, description, owner_id),
        )
        return row or {"id": pid, "kb_id": kb_id, "name": name, "description": description, "owner_id": owner_id}

    def list_projects(self, owner_id: Optional[str]) -> List[Dict[str, Any]]:
        """列出项目（按owner_id过滤）"""
        if owner_id:
            return self._fetchall(
                """
                SELECT id, kb_id, name, description, owner_id, created_at
                FROM tender_projects
                WHERE owner_id=%s
                ORDER BY created_at DESC
                """,
                (owner_id,),
            )
        return self._fetchall(
            """
            SELECT id, kb_id, name, description, owner_id, created_at
            FROM tender_projects
            ORDER BY created_at DESC
            """,
            (),
        )
    
    def update_project(self, project_id: str, name: Optional[str], description: Optional[str]) -> Dict[str, Any]:
        """更新项目信息"""
        # 构建动态 SQL（只更新提供的字段）
        updates = []
        params = []
        
        if name is not None:
            updates.append("name=%s")
            params.append(name)
        
        if description is not None:
            updates.append("description=%s")
            params.append(description)
        
        if not updates:
            # 没有要更新的字段，直接返回当前数据
            return self.get_project(project_id) or {}
        
        # updated_at 会由触发器自动更新
        sql = f"UPDATE tender_projects SET {', '.join(updates)} WHERE id=%s RETURNING *"
        params.append(project_id)
        
        row = self._fetchone(sql, tuple(params))
        return row or {}
    
    def delete_project(self, project_id: str) -> None:
        """删除项目（级联删除由外键约束处理）"""
        self._execute(
            "DELETE FROM tender_projects WHERE id=%s",
            (project_id,),
        )

    # ==================== 任务运行管理 ====================

    def create_run(self, project_id: str, kind: str) -> str:
        """创建运行任务"""
        rid = _id("tr")
        self._execute(
            """
            INSERT INTO tender_runs (id, project_id, run_type, kind, status, progress, message, result_json)
            VALUES (%s, %s, %s, %s, 'pending', NULL, NULL, NULL)
            """,
            (rid, project_id, kind, kind),  # 同时填充 run_type 和 kind
        )
        return rid

    def update_run(
        self,
        run_id: str,
        status: str,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        result_json: Any = None,
    ):
        """更新运行任务状态"""
        # 根据状态设置 finished_at
        finished_clause = ", finished_at=NOW()" if status in ('success', 'failed') else ""
        self._execute(
            f"""
            UPDATE tender_runs
            SET status=%s,
                progress=COALESCE(%s, progress),
                message=COALESCE(%s, message),
                result_json=COALESCE(%s, result_json)
                {finished_clause}
            WHERE id=%s
            """,
            (status, progress, message, json.dumps(result_json) if result_json is not None else None, run_id),
        )

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """获取运行任务信息"""
        row = self._fetchone("SELECT * FROM tender_runs WHERE id=%s", (run_id,))
        if row and isinstance(row.get("result_json"), str):
            try:
                row["result_json"] = json.loads(row["result_json"])
            except Exception:
                pass
        return row

    # ==================== 资产管理 ====================

    def create_asset(
        self,
        project_id: str,
        kind: str,
        filename: Optional[str],
        mime_type: Optional[str],
        size_bytes: Optional[int],
        kb_doc_id: Optional[str],
        storage_path: Optional[str],
        bidder_name: Optional[str],
        meta_json: Dict[str, Any],
    ) -> Dict[str, Any]:
        """创建资产记录"""
        aid = _id("ta")
        row = self._fetchone(
            """
            INSERT INTO tender_project_assets
              (id, project_id, kind, filename, mime_type, size_bytes, kb_doc_id, storage_path, bidder_name, meta_json, created_at)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
            RETURNING *
            """,
            (aid, project_id, kind, filename, mime_type, size_bytes, kb_doc_id, storage_path, bidder_name, json.dumps(meta_json or {})),
        )
        return row or {}

    def list_assets(self, project_id: str) -> List[Dict[str, Any]]:
        """列出项目的所有资产"""
        return self._fetchall(
            "SELECT * FROM tender_project_assets WHERE project_id=%s ORDER BY created_at ASC",
            (project_id,),
        )

    def get_asset_by_id(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取单个资产"""
        return self._fetchone(
            "SELECT * FROM tender_project_assets WHERE id=%s",
            (asset_id,),
        )

    def delete_asset(self, asset_id: str):
        """删除资产"""
        self._execute(
            "DELETE FROM tender_project_assets WHERE id=%s",
            (asset_id,),
        )

    def get_assets_by_ids(self, project_id: str, asset_ids: List[str]) -> List[Dict[str, Any]]:
        """根据ID列表获取资产"""
        if not asset_ids:
            return []
        placeholders = ",".join(["%s"] * len(asset_ids))
        return self._fetchall(
            f"SELECT * FROM tender_project_assets WHERE project_id=%s AND id IN ({placeholders})",
            tuple([project_id] + asset_ids),
        )

    def get_assets_by_kb_doc_id(self, kb_doc_id: str) -> List[Dict[str, Any]]:
        """根据知识库文档ID查找关联的资产"""
        return self._fetchall(
            "SELECT * FROM tender_project_assets WHERE kb_doc_id=%s",
            (kb_doc_id,),
        )

    def update_asset_meta(self, asset_id: str, meta_json: Dict[str, Any]):
        """更新资产的 meta_json（用于模板解析后更新）"""
        self._execute(
            "UPDATE tender_project_assets SET meta_json=%s WHERE id=%s",
            (json.dumps(meta_json), asset_id),
        )

    def update_asset_storage_path(self, asset_id: str, storage_path: Optional[str]):
        """更新资产 storage_path（用于恢复旧数据/补写落盘路径）"""
        self._execute(
            "UPDATE tender_project_assets SET storage_path=%s WHERE id=%s",
            (storage_path, asset_id),
        )

    # ==================== 规则集管理（已弃用） ====================
    # 注意：以下方法已弃用，规则文件现在直接作为审核上下文叠加
    # 保留这些方法是为了向后兼容，避免线上代码调用时报错
    # 可在确认前端完全移除相关调用后删除

    # create_rule_set, list_rule_sets, get_rule_sets_by_ids 已删除

    # ==================== KB 轻量入库 ====================

    def create_kb_document(
        self,
        kb_id: str,
        filename: str,
        content_hash: str,
        meta_json: Dict[str, Any],
        kb_category: str = "tender_app",
    ) -> str:
        """创建 KB 文档记录"""
        doc_id = _id("doc")
        self._execute(
            """
            INSERT INTO kb_documents (id, kb_id, filename, source, content_hash, status, kb_category, created_at, updated_at, meta_json)
            VALUES (%s, %s, %s, %s, %s, 'ready', %s, NOW(), NOW(), %s::jsonb)
            """,
            (doc_id, kb_id, filename, f"upload://{filename}", content_hash, kb_category, json.dumps(meta_json or {})),
        )
        return doc_id

    def insert_kb_chunks(
        self,
        kb_id: str,
        doc_id: str,
        chunks: List[Dict[str, Any]],
        kb_category: str = "tender_app",
    ) -> List[str]:
        """批量插入 KB chunks"""
        chunk_ids: List[str] = []
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                for c in chunks:
                    cid = _id("chunk")
                    chunk_ids.append(cid)
                    title = c.get("title") or ""
                    url = c.get("url") or ""
                    position = int(c.get("position") or 0)
                    content = c.get("content") or ""
                    cur.execute(
                        """
                        INSERT INTO kb_chunks (chunk_id, kb_id, doc_id, title, url, position, content, kb_category, created_at, tsv)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), to_tsvector('simple', %s))
                        """,
                        (cid, kb_id, doc_id, title, url, position, content, kb_category, content),
                    )
            conn.commit()
        return chunk_ids

    def lookup_chunks(self, chunk_ids: List[str]) -> List[Dict[str, Any]]:
        """根据 chunk_ids 查询 chunks"""
        if not chunk_ids:
            return []
        placeholders = ",".join(["%s"] * len(chunk_ids))
        return self._fetchall(
            f"""
            SELECT chunk_id, doc_id, title, url, position, content
            FROM kb_chunks
            WHERE chunk_id IN ({placeholders})
            """,
            tuple(chunk_ids),
        )

    def load_chunks_by_doc_ids(self, doc_ids: List[str], limit: int) -> List[Dict[str, Any]]:
        """根据 doc_ids 加载 chunks"""
        if not doc_ids:
            return []
        placeholders = ",".join(["%s"] * len(doc_ids))
        return self._fetchall(
            f"""
            SELECT chunk_id, doc_id, title, url, position, content
            FROM kb_chunks
            WHERE doc_id IN ({placeholders})
            ORDER BY doc_id ASC, position ASC
            LIMIT %s
            """,
            tuple(doc_ids + [limit]),
        )

    # ==================== 项目信息 ====================

    def upsert_project_info(
        self,
        project_id: str,
        data_json: Dict[str, Any],
        evidence_chunk_ids: List[str],
    ):
        """插入或更新项目信息"""
        self._execute(
            """
            INSERT INTO tender_project_info (project_id, data_json, evidence_chunk_ids_json, updated_at)
            VALUES (%s, %s::jsonb, %s::jsonb, NOW())
            ON CONFLICT (project_id) DO UPDATE SET
              data_json=EXCLUDED.data_json,
              evidence_chunk_ids_json=EXCLUDED.evidence_chunk_ids_json,
              updated_at=NOW()
            """,
            (project_id, json.dumps(data_json or {}), json.dumps(evidence_chunk_ids or [])),
        )

    def get_project_info(self, project_id: str) -> Optional[Dict[str, Any]]:
        """获取项目信息"""
        row = self._fetchone(
            "SELECT project_id, data_json, evidence_chunk_ids_json, updated_at FROM tender_project_info WHERE project_id=%s",
            (project_id,),
        )
        if not row:
            return None
        # JSON 字段反序列化
        for k in ("data_json", "evidence_chunk_ids_json"):
            if isinstance(row.get(k), str):
                try:
                    row[k] = json.loads(row[k])
                except Exception:
                    pass
        return row

    # ==================== 风险管理 ====================

    def replace_risks(self, project_id: str, items: List[Dict[str, Any]]):
        """替换项目的所有风险"""
        with self.pool.connection() as conn:
            with conn.transaction():  # 显式事务保护
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM tender_risks WHERE project_id=%s", (project_id,))
                    for it in items:
                        cur.execute(
                            """
                            INSERT INTO tender_risks
                              (id, project_id, risk_type, title, description, suggestion, severity, tags_json, evidence_chunk_ids_json)
                            VALUES
                              (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                            """,
                            (
                                _id("risk"),
                                project_id,
                                it.get("risk_type") or "other",
                                it.get("title") or "",
                                it.get("description") or "",
                                it.get("suggestion") or "",
                                it.get("severity") or "medium",
                                json.dumps(it.get("tags") or []),
                                json.dumps(it.get("evidence_chunk_ids") or []),
                            ),
                        )
            # with transaction() 自动提交或回滚，无需手动 commit

    def list_risks(self, project_id: str) -> List[Dict[str, Any]]:
        """列出项目的所有风险"""
        rows = self._fetchall(
            "SELECT id, project_id, risk_type, title, description, suggestion, severity, tags_json as tags, evidence_chunk_ids_json as evidence_chunk_ids, created_at FROM tender_risks WHERE project_id=%s ORDER BY created_at ASC",
            (project_id,),
        )
        # JSON 字段反序列化
        for r in rows:
            for k in ("tags", "evidence_chunk_ids"):
                if isinstance(r.get(k), str):
                    try:
                        r[k] = json.loads(r[k])
                    except Exception:
                        r[k] = []
                elif r.get(k) is None:
                    r[k] = []
        return rows

    # ==================== 目录管理 ====================

    def replace_directory(self, project_id: str, nodes: List[Dict[str, Any]]):
        """
        替换项目目录（兼容旧入参并自动生成树结构）
        入参：
        - 旧：[{numbering, level, title, required, notes, evidence_chunk_ids}]
        - 新：[{id, parent_id, order_no, numbering, level, title, is_required, source, meta_json, evidence_chunk_ids}]
        
        最终：落库时强制生成 parent_id + order_no，保证树形+稳定顺序
        """
        # 1) 归一化 + 排序
        norm = []
        for idx, n in enumerate(nodes or []):
            numbering = (n.get("numbering") or "").strip()
            level = n.get("level")
            if level is None:
                # 无 level 就按 numbering 推导
                level = len(numbering.strip(".").split(".")) if numbering else 1
            title = (n.get("title") or "").strip()
            is_required = bool(n.get("is_required", n.get("required", False)))
            source = (n.get("source") or "tender").strip()  # tender/template/manual
            evidence = n.get("evidence_chunk_ids") or []
            notes = n.get("notes") or (n.get("meta_json") or {}).get("notes") or ""
            volume = (n.get("volume") or (n.get("meta_json") or {}).get("volume") or "").strip()

            meta = dict(n.get("meta_json") or {})
            if notes:
                meta["notes"] = notes
            if volume:
                meta["volume"] = volume

            norm.append({
                "raw": n,
                "numbering": numbering,
                "level": int(level),
                "title": title,
                "is_required": is_required,
                "source": source,
                "evidence": list(evidence),
                "meta": meta,
                "_idx": idx,
            })

        # 2) 自然排序
        norm.sort(key=lambda x: (_parse_numbering_key(x["numbering"]), x["_idx"]))

        # 3) 生成 id / parent_id / order_no
        by_numbering_id: Dict[str, str] = {}
        used_ids: set = set()  # 跟踪已使用的ID，避免重复
        out_rows = []
        for order_no, n in enumerate(norm, start=1):
            # 优先使用原有ID，但如果重复则生成新ID
            nid = n["raw"].get("id")
            if nid and nid in used_ids:
                # ID重复，强制生成新ID
                nid = None
            if not nid:
                nid = _stable_node_id(project_id, n["numbering"], n["_idx"])
            
            # 再次检查，如果还是重复（理论上不应该发生），使用随机UUID
            if nid in used_ids:
                nid = f"tdn_{uuid.uuid4().hex}"
            
            used_ids.add(nid)
            by_numbering_id[n["numbering"]] = nid
            out_rows.append((order_no, nid, n))

        # 4) 写库（事务：先删后插）
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tender_directory_nodes WHERE project_id=%s", (project_id,))
                for order_no, nid, n in out_rows:
                    parent_num = _infer_parent_numbering(n["numbering"])
                    parent_id = by_numbering_id.get(parent_num) if parent_num else None
                    cur.execute(
                        """
                        INSERT INTO tender_directory_nodes
                          (id, project_id, parent_id, order_no, level, numbering, title,
                           is_required, source, evidence_chunk_ids_json, meta_json)
                        VALUES
                          (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)
                        """,
                        (
                            nid,
                            project_id,
                            parent_id,
                            order_no,
                            n["level"],
                            n["numbering"],
                            n["title"],
                            n["is_required"],
                            n["source"],
                            json.dumps(n["evidence"]),
                            json.dumps(n["meta"]),
                        ),
                    )
            conn.commit()

    def list_directory(self, project_id: str) -> List[Dict[str, Any]]:
        """列出项目的目录结构（按 order_no 排序）"""
        rows = self._fetchall(
            """
            SELECT id, project_id, parent_id, order_no, level, numbering, title,
                   is_required, source, evidence_chunk_ids_json as evidence_chunk_ids, meta_json
            FROM tender_directory_nodes
            WHERE project_id=%s
            ORDER BY order_no ASC, id ASC
            """,
            (project_id,),
        )
        # 展平 notes / volume，反序列化 JSON 字段
        for r in rows:
            # 处理 evidence_chunk_ids
            if isinstance(r.get("evidence_chunk_ids"), str):
                try:
                    r["evidence_chunk_ids"] = json.loads(r["evidence_chunk_ids"])
                except Exception:
                    r["evidence_chunk_ids"] = []
            elif r.get("evidence_chunk_ids") is None:
                r["evidence_chunk_ids"] = []
            
            # 处理 meta_json
            meta = r.get("meta_json") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            r["notes"] = meta.get("notes") or ""
            r["volume"] = meta.get("volume") or ""
            # 保留 meta_json 供其他用途
        return rows
    
    def update_node_meta_json(self, node_id: str, meta_json: Dict[str, Any]) -> None:
        """
        更新单个目录节点的 meta_json
        
        Args:
            node_id: 节点 ID
            meta_json: 新的 meta_json 字典
        """
        self._execute(
            "UPDATE tender_directory_nodes SET meta_json = %s WHERE id = %s",
            (json.dumps(meta_json), node_id)
        )
    
    def batch_update_node_meta_json(self, updates: List[Dict[str, Any]]) -> int:
        """
        批量更新目录节点的 meta_json
        
        Args:
            updates: 更新列表，每项格式: {"id": node_id, "meta_json": new_meta_json}
            
        Returns:
            更新的节点数量
        """
        if not updates:
            return 0
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                for update in updates:
                    node_id = update.get("id")
                    meta_json = update.get("meta_json")
                    if node_id and meta_json is not None:
                        cur.execute(
                            "UPDATE tender_directory_nodes SET meta_json = %s WHERE id = %s",
                            (json.dumps(meta_json), node_id)
                        )
        
        return len(updates)
    
    def get_latest_semantic_outline_nodes(self, project_id: str, outline_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取项目的语义目录节点
        
        Args:
            project_id: 项目 ID
            outline_id: 语义目录 ID（可选，如果不指定则获取最新的）
            
        Returns:
            语义目录节点列表
        """
        if outline_id:
            # 指定了 outline_id，直接查询
            return self._fetchall(
                """
                SELECT node_id, outline_id, project_id, parent_id, level, order_no, numbering,
                       title, summary, tags, evidence_chunk_ids, covered_req_ids
                FROM tender_semantic_outline_nodes
                WHERE project_id = %s AND outline_id = %s
                ORDER BY order_no ASC
                """,
                (project_id, outline_id)
            )
        else:
            # 获取最新的 outline_id
            return self._fetchall(
                """
                SELECT node_id, outline_id, project_id, parent_id, level, order_no, numbering,
                       title, summary, tags, evidence_chunk_ids, covered_req_ids
                FROM tender_semantic_outline_nodes
                WHERE project_id = %s
                  AND outline_id = (
                      SELECT outline_id
                      FROM tender_semantic_outlines
                      WHERE project_id = %s
                      ORDER BY created_at DESC
                      LIMIT 1
                  )
                ORDER BY order_no ASC
                """,
                (project_id, project_id)
            )

    # ==================== 审核项管理 ====================

    def replace_review_items(self, project_id: str, items: List[Dict[str, Any]]):
        """替换项目的所有审核项"""
        with self.pool.connection() as conn:
            with conn.transaction():  # 显式事务保护
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM tender_review_items WHERE project_id=%s", (project_id,))
                    for it in items:
                        cur.execute(
                            """
                            INSERT INTO tender_review_items
                              (id, project_id, dimension, tender_requirement, bid_response, result, remark, is_hard,
                               tender_evidence_chunk_ids_json, bid_evidence_chunk_ids_json)
                            VALUES
                              (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                            """,
                            (
                                _id("rev"),
                                project_id,
                                it.get("dimension") or "其他",
                                it.get("requirement_text") or "",
                                it.get("response_text") or "",
                                it.get("result") or "risk",
                                it.get("remark") or "",
                                bool(it.get("rigid", False)),
                                json.dumps(it.get("tender_evidence_chunk_ids") or []),
                                json.dumps(it.get("bid_evidence_chunk_ids") or []),
                            ),
                        )
            # with transaction() 自动提交或回滚，无需手动 commit

    def list_review_items(self, project_id: str) -> List[Dict[str, Any]]:
        """列出项目的所有审核项"""
        rows = self._fetchall(
            """SELECT id, project_id, dimension, tender_requirement as requirement_text, 
                      bid_response as response_text, result, is_hard as rigid, remark,
                      tender_evidence_chunk_ids_json as tender_evidence_chunk_ids, 
                      bid_evidence_chunk_ids_json as bid_evidence_chunk_ids, created_at 
               FROM tender_review_items 
               WHERE project_id=%s 
               ORDER BY created_at ASC""",
            (project_id,),
        )
        # 确保数组字段格式正确，反序列化 JSON 字段
        for r in rows:
            for k in ("tender_evidence_chunk_ids", "bid_evidence_chunk_ids"):
                if isinstance(r.get(k), str):
                    try:
                        r[k] = json.loads(r[k])
                    except Exception:
                        r[k] = []
                elif r.get(k) is None:
                    r[k] = []
        return rows

    # ==================== 兼容旧 API ====================

    def create_project_document_binding(
        self,
        project_id: str,
        role: str,
        kb_doc_id: str,
        bidder_name: Optional[str],
        filename: Optional[str],
    ):
        """创建项目文档绑定（兼容旧 API）"""
        bid = _id("tpd")
        self._execute(
            """
            INSERT INTO tender_project_documents (id, project_id, doc_role, kb_doc_id, bidder_name)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (bid, project_id, role, kb_doc_id, bidder_name),
        )

    def list_project_documents(self, project_id: str) -> List[Dict[str, Any]]:
        """列出项目文档绑定（兼容旧 API）"""
        return self._fetchall(
            """
            SELECT id, project_id, doc_role as role, kb_doc_id, bidder_name, created_at
            FROM tender_project_documents
            WHERE project_id=%s
            ORDER BY created_at ASC
            """,
            (project_id,),
        )

    # ==================== 格式模板管理 ====================

    def create_format_template(
        self,
        name: str,
        description: Optional[str],
        style_config: Dict[str, Any],
        owner_id: Optional[str],
        is_public: bool = False,
    ) -> Dict[str, Any]:
        """创建格式模板"""
        tid = _id("tpl")
        row = self._fetchone(
            """
            INSERT INTO format_templates
              (id, name, description, style_config, owner_id, is_public, created_at, updated_at)
            VALUES
              (%s, %s, %s, %s::jsonb, %s, %s, NOW(), NOW())
            RETURNING *
            """,
            (tid, name, description, json.dumps(style_config or {}), owner_id, is_public),
        )
        if row:
            # 转换 datetime 字段为 ISO 字符串
            for k in ("created_at", "updated_at", "template_spec_analyzed_at"):
                if row.get(k) and hasattr(row[k], "isoformat"):
                    row[k] = row[k].isoformat()
        return row or {}

    def get_format_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """获取格式模板"""
        row = self._fetchone(
            "SELECT * FROM format_templates WHERE id=%s",
            (template_id,),
        )
        if row:
            # 反序列化 JSON 字段
            for k in ("style_config", "template_spec_diagnostics_json", "parse_result_json"):
                if isinstance(row.get(k), str):
                    try:
                        row[k] = json.loads(row[k])
                    except Exception:
                        pass
            # 转换 datetime 字段为 ISO 字符串
            for k in ("created_at", "updated_at", "template_spec_analyzed_at", "parse_updated_at"):
                if row.get(k) and hasattr(row[k], "isoformat"):
                    row[k] = row[k].isoformat()
        return row

    def list_format_templates(self, owner_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出格式模板"""
        if owner_id:
            rows = self._fetchall(
                """
                SELECT * FROM format_templates
                WHERE owner_id=%s OR is_public=true
                ORDER BY created_at DESC
                """,
                (owner_id,),
            )
        else:
            rows = self._fetchall(
                "SELECT * FROM format_templates WHERE is_public=true ORDER BY created_at DESC",
                (),
            )
        
        for row in rows:
            # 反序列化 JSON 字段
            for k in ("style_config", "template_spec_diagnostics_json", "parse_result_json"):
                if isinstance(row.get(k), str):
                    try:
                        row[k] = json.loads(row[k])
                    except Exception:
                        pass
            # 转换 datetime 字段为 ISO 字符串
            for k in ("created_at", "updated_at", "template_spec_analyzed_at", "parse_updated_at"):
                if row.get(k) and hasattr(row[k], "isoformat"):
                    row[k] = row[k].isoformat()
        return rows

    def update_format_template_spec(
        self,
        template_id: str,
        template_sha256: str,
        template_spec_json: str,
        template_spec_version: str,
        template_spec_diagnostics_json: Optional[str] = None,
    ):
        """更新格式模板的 spec 分析结果"""
        self._execute(
            """
            UPDATE format_templates
            SET template_sha256=%s,
                template_spec_json=%s,
                template_spec_version=%s,
                template_spec_analyzed_at=NOW(),
                template_spec_diagnostics_json=%s,
                updated_at=NOW()
            WHERE id=%s
            """,
            (template_sha256, template_spec_json, template_spec_version, template_spec_diagnostics_json, template_id),
        )

    def update_format_template_storage_path(self, template_id: str, template_storage_path: str) -> None:
        """更新格式模板 docx 存储路径（用于导出时加载底板）"""
        self._execute(
            """
            UPDATE format_templates
            SET template_storage_path=%s,
                updated_at=NOW()
            WHERE id=%s
            """,
            (template_storage_path, template_id),
        )

    def update_format_template_parse_result(
        self,
        template_id: str,
        parse_status: str,
        parse_result_json: Dict[str, Any],
        parse_error: Optional[str] = None,
        preview_docx_path: Optional[str] = None,
        preview_pdf_path: Optional[str] = None,
    ) -> None:
        """更新格式模板确定性解析结果与预览文件路径"""
        self._execute(
            """
            UPDATE format_templates
            SET parse_status=%s,
                parse_error=%s,
                parse_result_json=%s::jsonb,
                parse_updated_at=NOW(),
                preview_docx_path=%s,
                preview_pdf_path=%s,
                updated_at=NOW()
            WHERE id=%s
            """,
            (
                parse_status,
                parse_error,
                json.dumps(parse_result_json or {}, ensure_ascii=False),
                preview_docx_path,
                preview_pdf_path,
                template_id,
            ),
        )

    def clear_format_template_preview_paths(self, template_id: str) -> None:
        """清空模板的预览路径（用于重新生成）"""
        self._execute(
            """
            UPDATE format_templates
            SET preview_docx_path=NULL,
                preview_pdf_path=NULL,
                updated_at=NOW()
            WHERE id=%s
            """,
            (template_id,),
        )

    def create_format_template_asset(
        self,
        template_id: str,
        asset_type: str,
        variant: str,
        storage_path: str,
        file_name: Optional[str] = None,
        content_type: Optional[str] = None,
        width_px: Optional[int] = None,
        height_px: Optional[int] = None,
    ) -> Dict[str, Any]:
        """创建格式模板资产记录（header/footer 图片、preview 文件等）"""
        aid = _id("fta")
        row = self._fetchone(
            """
            INSERT INTO format_template_assets
              (id, template_id, asset_type, variant, file_name, content_type, storage_path, width_px, height_px, created_at)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING *
            """,
            (
                aid,
                template_id,
                asset_type,
                variant or "DEFAULT",
                file_name,
                content_type,
                storage_path,
                width_px,
                height_px,
            ),
        )
        return row or {}

    def list_format_template_assets(self, template_id: str) -> List[Dict[str, Any]]:
        """列出某模板的所有资产"""
        return self._fetchall(
            """
            SELECT *
            FROM format_template_assets
            WHERE template_id=%s
            ORDER BY created_at DESC
            """,
            (template_id,),
        )

    def delete_format_template_assets(self, template_id: str, asset_types: Optional[List[str]] = None) -> None:
        """删除某模板的资产记录（可按类型过滤）"""
        if asset_types:
            self._execute(
                "DELETE FROM format_template_assets WHERE template_id=%s AND asset_type = ANY(%s)",
                (template_id, asset_types),
            )
            return
        self._execute("DELETE FROM format_template_assets WHERE template_id=%s", (template_id,))

    def get_format_template_by_sha256(self, sha256: str) -> Optional[Dict[str, Any]]:
        """根据 SHA256 查找模板（用于缓存查找）"""
        row = self._fetchone(
            """
            SELECT * FROM format_templates
            WHERE template_sha256=%s
            ORDER BY template_spec_analyzed_at DESC
            LIMIT 1
            """,
            (sha256,),
        )
        if row:
            for k in ("style_config", "template_spec_diagnostics_json"):
                if isinstance(row.get(k), str):
                    try:
                        row[k] = json.loads(row[k])
                    except Exception:
                        pass
            # 转换 datetime 字段为 ISO 字符串
            for k in ("created_at", "updated_at", "template_spec_analyzed_at"):
                if row.get(k) and hasattr(row[k], "isoformat"):
                    row[k] = row[k].isoformat()
        return row

    def delete_format_template(self, template_id: str):
        """删除格式模板"""
        self._execute(
            "DELETE FROM format_templates WHERE id=%s",
            (template_id,),
        )
    
    def update_format_template_meta(
        self,
        template_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        is_public: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """更新格式模板元数据"""
        updates = []
        params = []
        
        if name is not None:
            updates.append("name=%s")
            params.append(name)
        
        if description is not None:
            updates.append("description=%s")
            params.append(description)
        
        if is_public is not None:
            updates.append("is_public=%s")
            params.append(is_public)
        
        if not updates:
            return self.get_format_template(template_id) or {}
    
    def set_format_template_storage(
        self,
        template_id: str,
        storage_path: str,
        sha256: Optional[str] = None
    ) -> None:
        """
        设置格式模板的文件存储路径和 SHA256
        
        Args:
            template_id: 模板ID
            storage_path: 存储路径
            sha256: 文件 SHA256（可选）
        """
        if sha256:
            self._execute(
                """
                UPDATE format_templates
                SET template_storage_path=%s,
                    template_sha256=%s,
                    updated_at=NOW()
                WHERE id=%s
                """,
                (storage_path, sha256, template_id),
            )
        else:
            self._execute(
                """
                UPDATE format_templates
                SET template_storage_path=%s,
                    updated_at=NOW()
                WHERE id=%s
                """,
                (storage_path, template_id),
            )
    
    def set_format_template_analysis(
        self,
        template_id: str,
        status: str,
        analysis_json: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> None:
        """
        设置格式模板的分析结果
        
        Args:
            template_id: 模板ID
            status: 分析状态 (PENDING/SUCCESS/FAILED)
            analysis_json: 分析结果JSON
            error: 错误信息（失败时）
        """
        self._execute(
            """
            UPDATE format_templates
            SET analysis_status=%s,
                analysis_json=%s::jsonb,
                analysis_error=%s,
                analysis_updated_at=NOW(),
                updated_at=NOW()
            WHERE id=%s
            """,
            (
                status,
                json.dumps(analysis_json or {}, ensure_ascii=False) if analysis_json else None,
                error,
                template_id,
            ),
        )
    
    def set_format_template_parse(
        self,
        template_id: str,
        status: str,
        parse_json: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        preview_docx_path: Optional[str] = None,
        preview_pdf_path: Optional[str] = None
    ) -> None:
        """
        设置格式模板的解析结果
        
        Args:
            template_id: 模板ID
            status: 解析状态 (PENDING/SUCCESS/FAILED)
            parse_json: 解析结果JSON
            error: 错误信息（失败时）
            preview_docx_path: 预览DOCX路径
            preview_pdf_path: 预览PDF路径
        """
        self._execute(
            """
            UPDATE format_templates
            SET parse_status=%s,
                parse_result_json=%s::jsonb,
                parse_error=%s,
                parse_updated_at=NOW(),
                preview_docx_path=%s,
                preview_pdf_path=%s,
                updated_at=NOW()
            WHERE id=%s
            """,
            (
                status,
                json.dumps(parse_json or {}, ensure_ascii=False),
                error,
                preview_docx_path,
                preview_pdf_path,
                template_id,
            ),
        )
    
    def set_directory_root_format_template(
        self,
        project_id: str,
        template_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        设置项目目录根节点的格式模板ID
        
        逻辑：
        1. 查找根节点（parent_id IS NULL 或 level=1 且最小 order_no）
        2. 合并 meta_json，写入 format_template_id
        
        Args:
            project_id: 项目ID
            template_id: 模板ID
            
        Returns:
            更新后的根节点，如果找不到返回 None
        """
        # 1. 查找根节点
        root = self._fetchone(
            """
            SELECT * FROM tender_directory_nodes
            WHERE project_id=%s AND parent_id IS NULL
            ORDER BY order_no ASC
            LIMIT 1
            """,
            (project_id,),
        )
        
        if not root:
            # 降级：查找 level=1 的第一个节点
            root = self._fetchone(
                """
                SELECT * FROM tender_directory_nodes
                WHERE project_id=%s AND level=1
                ORDER BY order_no ASC
                LIMIT 1
                """,
                (project_id,),
            )
        
        if not root:
            return None
        
        # 2. 合并 meta_json
        meta_json = root.get("meta_json") or {}
        if isinstance(meta_json, str):
            try:
                meta_json = json.loads(meta_json)
            except Exception:
                meta_json = {}
        
        meta_json["format_template_id"] = template_id
        
        # 3. 更新节点
        updated = self._fetchone(
            """
            UPDATE tender_directory_nodes
            SET meta_json=%s::jsonb,
                updated_at=NOW()
            WHERE id=%s
            RETURNING *
            """,
            (json.dumps(meta_json, ensure_ascii=False), root["id"]),
        )
        
        return updated
    
    def get_directory_root_format_template(
        self,
        project_id: str
    ) -> Optional[str]:
        """
        获取项目目录根节点绑定的格式模板ID
        
        Args:
            project_id: 项目ID
            
        Returns:
            模板ID，如果未绑定返回 None
        """
        root = self._fetchone(
            """
            SELECT meta_json FROM tender_directory_nodes
            WHERE project_id=%s AND parent_id IS NULL
            ORDER BY order_no ASC
            LIMIT 1
            """,
            (project_id,),
        )
        
        if not root:
            # 降级：查找 level=1 的第一个节点
            root = self._fetchone(
                """
                SELECT meta_json FROM tender_directory_nodes
                WHERE project_id=%s AND level=1
                ORDER BY order_no ASC
                LIMIT 1
                """,
                (project_id,),
            )
        
        if not root:
            return None
        
        meta_json = root.get("meta_json") or {}
        if isinstance(meta_json, str):
            try:
                meta_json = json.loads(meta_json)
            except Exception:
                return None
        
        return meta_json.get("format_template_id")
        
        updates.append("updated_at=NOW()")
        sql = f"UPDATE format_templates SET {', '.join(updates)} WHERE id=%s RETURNING *"
        params.append(template_id)
        
        row = self._fetchone(sql, tuple(params))
        if row:
            # 反序列化 JSON 字段
            for k in ("style_config", "template_spec_diagnostics_json"):
                if isinstance(row.get(k), str):
                    try:
                        row[k] = json.loads(row[k])
                    except Exception:
                        pass
            # 转换 datetime 字段为 ISO 字符串
            for k in ("created_at", "updated_at", "template_spec_analyzed_at"):
                if row.get(k) and hasattr(row[k], "isoformat"):
                    row[k] = row[k].isoformat()
        return row or {}
    
    # ==================== 范本片段管理 ====================
    
    def create_fragment(
        self,
        owner_type: str,
        owner_id: str,
        source_file_key: str,
        source_file_sha256: Optional[str],
        fragment_type: str,
        title: str,
        title_norm: str,
        path_hint: Optional[str],
        heading_level: Optional[int],
        start_body_index: int,
        end_body_index: int,
        confidence: Optional[float],
        diagnostics_json: Optional[str],
    ) -> str:
        """创建范本片段（直接插入，不去重）"""
        fid = _id("frag")
        self._execute(
            """
            INSERT INTO doc_fragment
              (id, owner_type, owner_id, source_file_key, source_file_sha256,
               fragment_type, title, title_norm, path_hint, heading_level,
               start_body_index, end_body_index, confidence, diagnostics_json,
               created_at, updated_at)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (fid, owner_type, owner_id, source_file_key, source_file_sha256,
             fragment_type, title, title_norm, path_hint, heading_level,
             start_body_index, end_body_index, confidence, diagnostics_json),
        )
        return fid
    
    def upsert_fragment(
        self,
        owner_type: str,
        owner_id: str,
        source_file_key: str,
        source_file_sha256: Optional[str],
        fragment_type: str,
        title: str,
        title_norm: str,
        path_hint: Optional[str],
        heading_level: Optional[int],
        start_body_index: int,
        end_body_index: int,
        confidence: Optional[float],
        diagnostics_json: Optional[str],
    ) -> str:
        """
        插入或更新范本片段（去重）
        
        去重键：(owner_type, owner_id, fragment_type, source_file_key, start_body_index)
        这确保同一份文件、同一位置的同一类型片段不会重复
        """
        # 先尝试查找是否已存在
        existing = self._fetchone(
            """
            SELECT id FROM doc_fragment
            WHERE owner_type=%s AND owner_id=%s 
              AND fragment_type=%s AND source_file_key=%s 
              AND start_body_index=%s
            """,
            (owner_type, owner_id, fragment_type, source_file_key, start_body_index),
        )
        
        if existing:
            # 更新现有记录
            fid = existing["id"]
            self._execute(
                """
                UPDATE doc_fragment SET
                  source_file_sha256=%s,
                  title=%s,
                  title_norm=%s,
                  path_hint=%s,
                  heading_level=%s,
                  end_body_index=%s,
                  confidence=%s,
                  diagnostics_json=%s,
                  updated_at=NOW()
                WHERE id=%s
                """,
                (source_file_sha256, title, title_norm, path_hint, heading_level,
                 end_body_index, confidence, diagnostics_json, fid),
            )
            return fid
        else:
            # 插入新记录
            fid = _id("frag")
            self._execute(
                """
                INSERT INTO doc_fragment
                  (id, owner_type, owner_id, source_file_key, source_file_sha256,
                   fragment_type, title, title_norm, path_hint, heading_level,
                   start_body_index, end_body_index, confidence, diagnostics_json,
                   created_at, updated_at)
                VALUES
                  (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                """,
                (fid, owner_type, owner_id, source_file_key, source_file_sha256,
                 fragment_type, title, title_norm, path_hint, heading_level,
                 start_body_index, end_body_index, confidence, diagnostics_json),
            )
            return fid
    
    def delete_fragments_by_owner(self, owner_type: str, owner_id: str):
        """删除指定所有者的所有片段（用于重新抽取）"""
        self._execute(
            "DELETE FROM doc_fragment WHERE owner_type=%s AND owner_id=%s",
            (owner_type, owner_id),
        )
    
    def list_fragments(self, owner_type: str, owner_id: str) -> List[Dict[str, Any]]:
        """列出指定所有者的所有片段"""
        return self._fetchall(
            """
            SELECT id, owner_type, owner_id, source_file_key, source_file_sha256,
                   fragment_type, title, title_norm, path_hint, heading_level,
                   start_body_index, end_body_index, confidence, diagnostics_json,
                   created_at, updated_at
            FROM doc_fragment
            WHERE owner_type=%s AND owner_id=%s
            ORDER BY start_body_index ASC
            """,
            (owner_type, owner_id),
        )

    def list_sample_fragments(self, project_id: str) -> List[Dict[str, Any]]:
        """
        列出某项目下的“范本片段”（doc_fragment）。

        约定：
        - owner_type 固定为 PROJECT
        - owner_id = project_id

        返回字段（至少）：
        id, fragment_type, title, confidence, source_file_key, start_body_index, end_body_index, created_at
        """
        return self._fetchall(
            """
            SELECT id,
                   fragment_type,
                   title,
                   confidence,
                   source_file_key,
                   start_body_index,
                   end_body_index,
                   created_at
            FROM doc_fragment
            WHERE owner_type=%s AND owner_id=%s
            ORDER BY created_at DESC NULLS LAST, start_body_index ASC
            """,
            ("PROJECT", project_id),
        )
    
    def get_fragment_by_id(self, fragment_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取片段"""
        return self._fetchone(
            """
            SELECT id, owner_type, owner_id, source_file_key, source_file_sha256,
                   fragment_type, title, title_norm, path_hint, heading_level,
                   start_body_index, end_body_index, confidence, diagnostics_json,
                   created_at, updated_at
            FROM doc_fragment
            WHERE id=%s
            """,
            (fragment_id,),
        )
    
    def find_fragments_by_type(
        self,
        owner_type: str,
        owner_id: str,
        fragment_type: str
    ) -> List[Dict[str, Any]]:
        """根据类型查找片段"""
        return self._fetchall(
            """
            SELECT id, owner_type, owner_id, source_file_key, source_file_sha256,
                   fragment_type, title, title_norm, path_hint, heading_level,
                   start_body_index, end_body_index, confidence, diagnostics_json,
                   created_at, updated_at
            FROM doc_fragment
            WHERE owner_type=%s AND owner_id=%s AND fragment_type=%s
            ORDER BY confidence DESC NULLS LAST, (end_body_index - start_body_index) DESC
            """,
            (owner_type, owner_id, fragment_type),
        )
    
    # ==================== 章节正文管理 ====================
    
    def upsert_section_body(
        self,
        project_id: str,
        node_id: str,
        source: str,
        fragment_id: Optional[str],
        content_html: Optional[str],
        content_json: Optional[object] = None,
    ):
        """插入或更新章节正文"""
        import json as json_module
        
        # 将 content_json 转为 JSON 字符串（如果需要）
        content_json_str = None
        if content_json is not None:
            if isinstance(content_json, str):
                content_json_str = content_json
            else:
                content_json_str = json_module.dumps(content_json, ensure_ascii=False)
        
        bid = _id("psb")
        self._execute(
            """
            INSERT INTO project_section_body
              (id, project_id, node_id, source, fragment_id, content_html, content_json, updated_at, created_at)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (project_id, node_id) DO UPDATE SET
              source=EXCLUDED.source,
              fragment_id=EXCLUDED.fragment_id,
              content_html=EXCLUDED.content_html,
              content_json=EXCLUDED.content_json,
              updated_at=NOW()
            """,
            (bid, project_id, node_id, source, fragment_id, content_html, content_json_str),
        )
    
    def get_section_body(self, project_id: str, node_id: str) -> Optional[Dict[str, Any]]:
        """获取章节正文"""
        return self._fetchone(
            """
            SELECT id, project_id, node_id, source, fragment_id, content_html, content_json,
                   updated_at, created_at
            FROM project_section_body
            WHERE project_id=%s AND node_id=%s
            """,
            (project_id, node_id),
        )
    
    def list_section_bodies(self, project_id: str) -> List[Dict[str, Any]]:
        """列出项目的所有章节正文"""
        return self._fetchall(
            """
            SELECT id, project_id, node_id, source, fragment_id, content_html,
                   updated_at, created_at
            FROM project_section_body
            WHERE project_id=%s
            ORDER BY created_at ASC
            """,
            (project_id,),
        )
    
    def delete_section_body(self, project_id: str, node_id: str):
        """删除章节正文"""
        self._execute(
            "DELETE FROM project_section_body WHERE project_id=%s AND node_id=%s",
            (project_id, node_id),
        )

    # ==================== 语义目录生成 ====================

    def create_semantic_outline(
        self,
        project_id: str,
        mode: str,
        max_depth: int,
        status: str,
        coverage_rate: float,
        diagnostics_json: Dict[str, Any],
    ) -> str:
        """创建语义目录记录"""
        outline_id = _id("smo")
        self._execute(
            """
            INSERT INTO tender_semantic_outlines
              (outline_id, project_id, mode, max_depth, status, coverage_rate, 
               diagnostics_json, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, NOW(), NOW())
            """,
            (outline_id, project_id, mode, max_depth, status, coverage_rate, json.dumps(diagnostics_json)),
        )
        return outline_id

    def get_semantic_outline(self, outline_id: str) -> Optional[Dict[str, Any]]:
        """获取语义目录"""
        return self._fetchone(
            """
            SELECT outline_id, project_id, mode, max_depth, status, coverage_rate,
                   diagnostics_json, created_at, updated_at
            FROM tender_semantic_outlines
            WHERE outline_id=%s
            """,
            (outline_id,),
        )

    def get_latest_semantic_outline(self, project_id: str) -> Optional[Dict[str, Any]]:
        """获取项目最新的语义目录"""
        return self._fetchone(
            """
            SELECT outline_id, project_id, mode, max_depth, status, coverage_rate,
                   diagnostics_json, created_at, updated_at
            FROM tender_semantic_outlines
            WHERE project_id=%s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (project_id,),
        )

    def list_semantic_outlines(self, project_id: str) -> List[Dict[str, Any]]:
        """列出项目的所有语义目录"""
        return self._fetchall(
            """
            SELECT outline_id, project_id, mode, max_depth, status, coverage_rate,
                   diagnostics_json, created_at, updated_at
            FROM tender_semantic_outlines
            WHERE project_id=%s
            ORDER BY created_at DESC
            """,
            (project_id,),
        )

    def save_requirement_items(
        self,
        outline_id: str,
        project_id: str,
        requirements: List[Dict[str, Any]],
    ) -> None:
        """批量保存要求项"""
        if not requirements:
            return
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                for req in requirements:
                    cur.execute(
                        """
                        INSERT INTO tender_requirement_items
                          (req_id, project_id, outline_id, req_type, title, content,
                           params_json, score_hint, must_level, source_chunk_ids,
                           confidence, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, NOW(), NOW())
                        ON CONFLICT (req_id) DO UPDATE SET
                          req_type=EXCLUDED.req_type,
                          title=EXCLUDED.title,
                          content=EXCLUDED.content,
                          params_json=EXCLUDED.params_json,
                          score_hint=EXCLUDED.score_hint,
                          must_level=EXCLUDED.must_level,
                          source_chunk_ids=EXCLUDED.source_chunk_ids,
                          confidence=EXCLUDED.confidence,
                          updated_at=NOW()
                        """,
                        (
                            req["req_id"],
                            project_id,
                            outline_id,
                            req["req_type"],
                            req["title"],
                            req["content"],
                            json.dumps(req.get("params")),
                            req.get("score_hint"),
                            req["must_level"],
                            req["source_chunk_ids"],
                            req.get("confidence", 0.8),
                        ),
                    )
            conn.commit()

    def get_requirement_items(self, outline_id: str) -> List[Dict[str, Any]]:
        """获取语义目录的所有要求项"""
        return self._fetchall(
            """
            SELECT req_id, project_id, outline_id, req_type, title, content,
                   params_json, score_hint, must_level, source_chunk_ids,
                   confidence, created_at, updated_at
            FROM tender_requirement_items
            WHERE outline_id=%s
            ORDER BY created_at ASC
            """,
            (outline_id,),
        )

    def save_semantic_outline_nodes(
        self,
        outline_id: str,
        project_id: str,
        nodes_flat: List[Dict[str, Any]],
    ) -> None:
        """批量保存语义目录节点（扁平化）"""
        if not nodes_flat:
            return
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                for node in nodes_flat:
                    cur.execute(
                        """
                        INSERT INTO tender_semantic_outline_nodes
                          (node_id, outline_id, project_id, parent_id, level, order_no,
                           numbering, title, summary, tags, evidence_chunk_ids,
                           covered_req_ids, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                        ON CONFLICT (node_id) DO UPDATE SET
                          parent_id=EXCLUDED.parent_id,
                          level=EXCLUDED.level,
                          order_no=EXCLUDED.order_no,
                          numbering=EXCLUDED.numbering,
                          title=EXCLUDED.title,
                          summary=EXCLUDED.summary,
                          tags=EXCLUDED.tags,
                          evidence_chunk_ids=EXCLUDED.evidence_chunk_ids,
                          covered_req_ids=EXCLUDED.covered_req_ids,
                          updated_at=NOW()
                        """,
                        (
                            node["node_id"],
                            outline_id,
                            project_id,
                            node.get("parent_id"),
                            node["level"],
                            node["order_no"],
                            node.get("numbering"),
                            node["title"],
                            node.get("summary"),
                            node.get("tags", []),
                            node.get("evidence_chunk_ids", []),
                            node.get("covered_req_ids", []),
                        ),
                    )
            conn.commit()

    def get_semantic_outline_nodes(self, outline_id: str) -> List[Dict[str, Any]]:
        """获取语义目录的所有节点（扁平化）"""
        return self._fetchall(
            """
            SELECT node_id, outline_id, project_id, parent_id, level, order_no,
                   numbering, title, summary, tags, evidence_chunk_ids,
                   covered_req_ids, created_at, updated_at
            FROM tender_semantic_outline_nodes
            WHERE outline_id=%s
            ORDER BY order_no ASC
            """,
            (outline_id,),
        )
