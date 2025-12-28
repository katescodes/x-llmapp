"""
RuleSet 服务 - 自定义规则版本化管理
提供规则集的解析、校验、版本化等功能
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Dict, List, Optional, Tuple

import yaml
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def _rule_set_id(prefix: str = "rs") -> str:
    """生成规则集 ID"""
    return f"{prefix}_{uuid.uuid4().hex}"


def _rule_set_version_id(prefix: str = "rsv") -> str:
    """生成规则集版本 ID"""
    return f"{prefix}_{uuid.uuid4().hex}"


def _compute_sha256(content: str) -> str:
    """计算 SHA256 哈希"""
    return hashlib.sha256(content.encode()).hexdigest()


class RuleSetService:
    """RuleSet 规则集服务"""

    def __init__(self, pool: ConnectionPool):
        """
        初始化服务
        
        Args:
            pool: PostgreSQL 连接池
        """
        self.pool = pool

    def parse_and_validate(self, content: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        解析并校验规则内容
        
        Args:
            content: YAML 或 JSON 内容
            
        Returns:
            (is_valid, message, parsed_data)
            - is_valid: 是否合法
            - message: 校验消息（成功或错误详情）
            - parsed_data: 解析后的数据（如果合法）
        """
        # 1. 尝试解析 YAML/JSON
        try:
            # 先尝试 YAML（兼容 JSON）
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            return False, f"YAML parsing error: {str(e)}", None
        except Exception as e:
            return False, f"Content parsing error: {str(e)}", None
        
        if not isinstance(data, dict):
            return False, "Content must be a dictionary/object", None
        
        # 2. 校验顶层结构
        if "rules" not in data:
            return False, "Missing required field: 'rules'", None
        
        rules = data.get("rules")
        if not isinstance(rules, list):
            return False, "'rules' must be a list/array", None
        
        if len(rules) == 0:
            return False, "'rules' cannot be empty", None
        
        # 3. 校验每条规则
        for idx, rule in enumerate(rules):
            if not isinstance(rule, dict):
                return False, f"Rule[{idx}] must be a dictionary/object", None
            
            # 必填字段：id, title, select, check
            required_fields = ["id", "title", "select", "check"]
            for field in required_fields:
                if field not in rule:
                    return False, f"Rule[{idx}] missing required field: '{field}'", None
                
                # id 和 title 必须是字符串
                if field in ["id", "title"]:
                    if not isinstance(rule[field], str) or not rule[field].strip():
                        return False, f"Rule[{idx}] '{field}' must be a non-empty string", None
            
            # 可选字段类型校验
            if "dimension" in rule and rule["dimension"] is not None:
                if not isinstance(rule["dimension"], str):
                    return False, f"Rule[{idx}] 'dimension' must be a string", None
            
            if "severity" in rule and rule["severity"] is not None:
                if not isinstance(rule["severity"], str):
                    return False, f"Rule[{idx}] 'severity' must be a string", None
                # 可选：校验 severity 枚举值
                allowed_severities = ["low", "medium", "high", "critical"]
                if rule["severity"] not in allowed_severities:
                    return False, f"Rule[{idx}] 'severity' must be one of {allowed_severities}", None
            
            if "rigid" in rule and rule["rigid"] is not None:
                if not isinstance(rule["rigid"], bool):
                    return False, f"Rule[{idx}] 'rigid' must be a boolean", None
            
            # select 和 check 可以是字符串或字典（暂不执行，只做类型校验）
            for field in ["select", "check"]:
                value = rule[field]
                if not isinstance(value, (str, dict)):
                    return False, f"Rule[{idx}] '{field}' must be a string or object", None
        
        # 4. 校验通过
        return True, f"Valid rule set with {len(rules)} rules", data

    def create_rule_set(
        self,
        namespace: str,
        scope: str,
        name: str,
        project_id: Optional[str] = None
    ) -> str:
        """
        创建规则集
        
        Args:
            namespace: 业务命名空间，如 "tender"
            scope: 作用域（"project" | "org"）
            name: 规则集名称
            project_id: 项目ID（scope=project 时必填）
            
        Returns:
            rule_set_id: 规则集ID
        """
        rule_set_id = _rule_set_id()
        
        sql = """
            INSERT INTO rule_sets (
                id, namespace, scope, project_id, name, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, now()
            )
        """
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    rule_set_id,
                    namespace,
                    scope,
                    project_id,
                    name
                ))
        
        return rule_set_id

    def create_version(
        self,
        rule_set_id: str,
        content_yaml: str,
        validate_status: str,
        validate_message: Optional[str] = None
    ) -> str:
        """
        创建规则集版本
        
        Args:
            rule_set_id: 规则集ID
            content_yaml: YAML 内容
            validate_status: 校验状态（"valid" | "invalid"）
            validate_message: 校验消息
            
        Returns:
            version_id: 版本ID
        """
        version_id = _rule_set_version_id()
        content_sha256 = _compute_sha256(content_yaml)
        
        # 获取下一个版本号
        sql_get_version = """
            SELECT COALESCE(MAX(version_no), 0) + 1 as next_version
            FROM rule_set_versions
            WHERE rule_set_id = %s
        """
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql_get_version, (rule_set_id,))
                row = cur.fetchone()
                version_no = list(row.values())[0] if row else 1
        
        sql = """
            INSERT INTO rule_set_versions (
                id, rule_set_id, version_no, content_sha256, content_yaml,
                validate_status, validate_message, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, now()
            )
        """
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    version_id,
                    rule_set_id,
                    version_no,
                    content_sha256,
                    content_yaml,
                    validate_status,
                    validate_message
                ))
        
        return version_id

    def get_rule_set(self, rule_set_id: str) -> Optional[Dict[str, Any]]:
        """
        获取规则集信息
        
        Args:
            rule_set_id: 规则集ID
            
        Returns:
            规则集信息字典或 None
        """
        sql = """
            SELECT id, namespace, scope, project_id, name, created_at
            FROM rule_sets
            WHERE id = %s
        """
        
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, (rule_set_id,))
                return cur.fetchone()

    def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """
        获取规则集版本信息
        
        Args:
            version_id: 版本ID
            
        Returns:
            版本信息字典或 None
        """
        sql = """
            SELECT id, rule_set_id, version_no, content_sha256, content_yaml,
                   validate_status, validate_message, created_at
            FROM rule_set_versions
            WHERE id = %s
        """
        
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, (version_id,))
                return cur.fetchone()

    def list_versions_by_rule_set(
        self,
        rule_set_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取规则集的所有版本
        
        Args:
            rule_set_id: 规则集ID
            limit: 最大返回数量
            
        Returns:
            版本列表
        """
        sql = """
            SELECT id, rule_set_id, version_no, content_sha256,
                   validate_status, validate_message, created_at
            FROM rule_set_versions
            WHERE rule_set_id = %s
            ORDER BY version_no DESC
            LIMIT %s
        """
        
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, (rule_set_id, limit))
                return list(cur.fetchall())

    def list_rule_sets_by_project(
        self,
        project_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取项目的所有规则集
        
        Args:
            project_id: 项目ID
            limit: 最大返回数量
            
        Returns:
            规则集列表
        """
        sql = """
            SELECT id, namespace, scope, project_id, name, created_at
            FROM rule_sets
            WHERE project_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """
        
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, (project_id, limit))
                return list(cur.fetchall())

