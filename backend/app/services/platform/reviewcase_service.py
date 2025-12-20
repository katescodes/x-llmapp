"""
ReviewCase 服务 - 统一审核案例管理
提供跨业务系统的审核案例、运行、发现管理功能
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def _case_id(prefix: str = "rc") -> str:
    """生成审核案例 ID"""
    return f"{prefix}_{uuid.uuid4().hex}"


def _run_id(prefix: str = "rr") -> str:
    """生成审核运行 ID"""
    return f"{prefix}_{uuid.uuid4().hex}"


def _finding_id(prefix: str = "rf") -> str:
    """生成审核发现 ID"""
    return f"{prefix}_{uuid.uuid4().hex}"


class ReviewCaseService:
    """ReviewCase 审核案例服务"""

    def __init__(self, pool: ConnectionPool):
        """
        初始化服务
        
        Args:
            pool: PostgreSQL 连接池
        """
        self.pool = pool

    def create_case(
        self,
        namespace: str,
        project_id: str,
        tender_doc_version_ids: Optional[List[str]] = None,
        bid_doc_version_ids: Optional[List[str]] = None,
        attachment_doc_version_ids: Optional[List[str]] = None
    ) -> str:
        """
        创建审核案例
        
        Args:
            namespace: 业务命名空间，如 "tender"
            project_id: 项目ID
            tender_doc_version_ids: 招标文档版本ID列表
            bid_doc_version_ids: 投标文档版本ID列表
            attachment_doc_version_ids: 附件文档版本ID列表
            
        Returns:
            case_id: 案例ID
        """
        case_id = _case_id()
        
        tender_ids_json = json.dumps(tender_doc_version_ids or [])
        bid_ids_json = json.dumps(bid_doc_version_ids or [])
        attachment_ids_json = json.dumps(attachment_doc_version_ids or [])
        
        sql = """
            INSERT INTO review_cases (
                id, namespace, project_id, 
                tender_doc_version_ids, bid_doc_version_ids, attachment_doc_version_ids,
                created_at
            ) VALUES (
                %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, now()
            )
        """
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    case_id,
                    namespace,
                    project_id,
                    tender_ids_json,
                    bid_ids_json,
                    attachment_ids_json
                ))
        
        return case_id

    def create_run(
        self,
        case_id: str,
        model_id: Optional[str] = None,
        rule_set_version_id: Optional[str] = None,
        status: str = "running"
    ) -> str:
        """
        创建审核运行
        
        Args:
            case_id: 案例ID
            model_id: 模型ID
            rule_set_version_id: 规则集版本ID（可选）
            status: 初始状态，默认 "running"
            
        Returns:
            run_id: 运行ID
        """
        run_id = _run_id()
        
        sql = """
            INSERT INTO review_runs (
                id, case_id, status, model_id, rule_set_version_id, 
                result_json, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, '{}'::jsonb, now(), now()
            )
        """
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    run_id,
                    case_id,
                    status,
                    model_id,
                    rule_set_version_id
                ))
        
        return run_id

    def update_run_status(
        self,
        run_id: str,
        status: str,
        result_json: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        更新审核运行状态
        
        Args:
            run_id: 运行ID
            status: 状态（running | succeeded | failed）
            result_json: 结果摘要（可选）
        """
        sql = """
            UPDATE review_runs
            SET status = %s,
                updated_at = now()
        """
        params = [status]
        
        if result_json is not None:
            sql += ", result_json = %s::jsonb"
            params.append(json.dumps(result_json))
        
        sql += " WHERE id = %s"
        params.append(run_id)
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))

    def create_finding(
        self,
        run_id: str,
        source: str,
        result: str,
        dimension: Optional[str] = None,
        requirement_text: Optional[str] = None,
        response_text: Optional[str] = None,
        rigid: bool = False,
        remark: Optional[str] = None,
        evidence_jsonb: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        创建审核发现
        
        Args:
            run_id: 运行ID
            source: 来源（"compare" | "rule"）
            result: 结果（pass | risk | fail）
            dimension: 维度
            requirement_text: 招标要求
            response_text: 投标响应
            rigid: 是否刚性要求
            remark: 备注
            evidence_jsonb: 证据链
            
        Returns:
            finding_id: 发现ID
        """
        finding_id = _finding_id()
        
        evidence_json = json.dumps(evidence_jsonb or {})
        
        sql = """
            INSERT INTO review_findings (
                id, run_id, source, dimension, requirement_text, response_text,
                result, rigid, remark, evidence_jsonb, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, now()
            )
        """
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    finding_id,
                    run_id,
                    source,
                    dimension,
                    requirement_text,
                    response_text,
                    result,
                    rigid,
                    remark,
                    evidence_json
                ))
        
        return finding_id

    def batch_create_findings(
        self,
        run_id: str,
        findings: List[Dict[str, Any]]
    ) -> List[str]:
        """
        批量创建审核发现
        
        Args:
            run_id: 运行ID
            findings: 发现列表，每个包含：source, result, dimension 等字段
            
        Returns:
            finding_ids: 发现ID列表
        """
        finding_ids = []
        
        sql = """
            INSERT INTO review_findings (
                id, run_id, source, dimension, requirement_text, response_text,
                result, rigid, remark, evidence_jsonb, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, now()
            )
        """
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                for finding in findings:
                    finding_id = _finding_id()
                    finding_ids.append(finding_id)
                    
                    evidence_json = json.dumps(finding.get("evidence_jsonb", {}))
                    
                    cur.execute(sql, (
                        finding_id,
                        run_id,
                        finding.get("source", "compare"),
                        finding.get("dimension"),
                        finding.get("requirement_text"),
                        finding.get("response_text"),
                        finding.get("result", "risk"),
                        finding.get("rigid", False),
                        finding.get("remark"),
                        evidence_json
                    ))
        
        return finding_ids

    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        """
        获取审核案例信息
        
        Args:
            case_id: 案例ID
            
        Returns:
            案例信息字典或 None
        """
        sql = """
            SELECT id, namespace, project_id, 
                   tender_doc_version_ids, bid_doc_version_ids, attachment_doc_version_ids,
                   created_at
            FROM review_cases
            WHERE id = %s
        """
        
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, (case_id,))
                return cur.fetchone()

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        获取审核运行信息
        
        Args:
            run_id: 运行ID
            
        Returns:
            运行信息字典或 None
        """
        sql = """
            SELECT id, case_id, status, model_id, rule_set_version_id,
                   result_json, created_at, updated_at
            FROM review_runs
            WHERE id = %s
        """
        
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, (run_id,))
                return cur.fetchone()

    def list_findings_by_run(
        self,
        run_id: str,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        获取运行的所有发现
        
        Args:
            run_id: 运行ID
            limit: 最大返回数量
            
        Returns:
            发现列表
        """
        sql = """
            SELECT id, run_id, source, dimension, requirement_text, response_text,
                   result, rigid, remark, evidence_jsonb, created_at
            FROM review_findings
            WHERE run_id = %s
            ORDER BY created_at
            LIMIT %s
        """
        
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, (run_id, limit))
                return list(cur.fetchall())

    def list_cases_by_project(
        self,
        project_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取项目的所有审核案例
        
        Args:
            project_id: 项目ID
            limit: 最大返回数量
            
        Returns:
            案例列表
        """
        sql = """
            SELECT id, namespace, project_id, 
                   tender_doc_version_ids, bid_doc_version_ids, attachment_doc_version_ids,
                   created_at
            FROM review_cases
            WHERE project_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """
        
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, (project_id, limit))
                return list(cur.fetchall())

    def list_runs_by_case(
        self,
        case_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取案例的所有审核运行
        
        Args:
            case_id: 案例ID
            limit: 最大返回数量
            
        Returns:
            运行列表
        """
        sql = """
            SELECT id, case_id, status, model_id, rule_set_version_id,
                   result_json, created_at, updated_at
            FROM review_runs
            WHERE case_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """
        
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, (case_id, limit))
                return list(cur.fetchall())

