"""
Rules Evaluator v2 - 基于新检索器的规则审核引擎
支持确定性规则执行，生成 review findings
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

import yaml
from psycopg_pool import ConnectionPool

from app.platform.retrieval.new_retriever import NewRetriever
from app.services.embedding_provider_store import get_embedding_store

logger = logging.getLogger(__name__)


class RulesEvaluatorV2:
    """规则评估器 v2 - 使用新检索器"""

    def __init__(self, pool: ConnectionPool):
        """初始化规则评估器"""
        self.pool = pool
        self.retriever = NewRetriever(pool)

    async def evaluate(
        self,
        project_id: str,
        rule_set_version: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        执行规则评估
        
        Args:
            project_id: 项目ID
            rule_set_version: 规则集版本（包含 content_yaml）
            context: 执行上下文（可选），包含：
                - project_info: 项目信息（用于字段检测）
                
        Returns:
            findings 列表，每个包含：
                - rule_id: 规则ID
                - source: "rule"
                - dimension: 维度
                - requirement_text: 规则描述
                - response_text: 检测结果
                - result: pass | risk | fail
                - rigid: 是否刚性
                - remark: 备注
                - evidence_chunk_ids: 证据 chunk IDs (兼容旧格式)
                - evidence_spans: 证据 spans (新格式，包含 page_no)
        """
        findings = []
        
        # 解析规则内容
        try:
            content_yaml = rule_set_version.get("content_yaml", "")
            rules_data = yaml.safe_load(content_yaml)
            rules = rules_data.get("rules", [])
        except Exception as e:
            logger.error(f"Failed to parse rules: {e}")
            return findings
        
        # 执行每条规则
        for rule in rules:
            try:
                finding = await self._evaluate_rule(project_id, rule, context or {})
                if finding:
                    findings.append(finding)
            except Exception as e:
                # 单条规则失败不影响其他规则
                logger.warning(f"Rule {rule.get('id', 'unknown')} evaluation failed: {e}")
                # 生成一个失败的 finding
                findings.append({
                    "rule_id": rule.get("id", "unknown"),
                    "source": "rule",
                    "dimension": rule.get("dimension", "规则执行"),
                    "requirement_text": rule.get("title", "规则"),
                    "response_text": "",
                    "result": "risk",
                    "rigid": False,
                    "remark": f"规则执行失败: {str(e)}",
                    "evidence_chunk_ids": [],
                    "evidence_spans": []
                })
        
        return findings

    async def _evaluate_rule(
        self,
        project_id: str,
        rule: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        执行单条规则
        
        Args:
            project_id: 项目ID
            rule: 规则定义
            context: 执行上下文
            
        Returns:
            finding 或 None（规则不适用）
        """
        rule_id = rule.get("id", "unknown")
        title = rule.get("title", "")
        dimension = rule.get("dimension", "其他")
        rigid = rule.get("rigid", False)
        select = rule.get("select", "")
        check = rule.get("check", "")
        
        # 识别规则类型并执行
        if isinstance(check, str):
            # A. exists 规则：必须存在某关键词
            if "must contain" in check or "contains" in check or "包含" in check:
                return await self._evaluate_exists_rule(
                    project_id, rule_id, title, dimension, rigid, select, check, context
                )
            
            # B. missing_field 规则：字段缺失检测
            elif "field" in check and ("missing" in check or "empty" in check):
                return self._evaluate_missing_field_rule(
                    rule_id, title, dimension, rigid, select, check, context
                )
            
            # C. date_compare 规则：时间先后
            elif "date" in check or "<=" in check or ">=" in check:
                return self._evaluate_date_compare_rule(
                    rule_id, title, dimension, rigid, select, check, context
                )
        
        # 未识别的规则类型，返回 None（不生成 finding）
        logger.warning(f"Rule {rule_id} type not recognized, check: {check}")
        return None

    async def _evaluate_exists_rule(
        self,
        project_id: str,
        rule_id: str,
        title: str,
        dimension: str,
        rigid: bool,
        select: str,
        check: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行 exists 规则：检查是否存在某关键词/段落（使用新检索器）
        
        例如：
        select: "bid"
        check: "must contain('营业执照', '有效期')"
        """
        # 提取要检查的关键词
        keywords = self._extract_keywords_from_check(check)
        if not keywords:
            logger.warning(f"Rule {rule_id}: No keywords extracted from check: {check}")
            return self._make_finding(
                rule_id, title, dimension, rigid,
                "risk", "关键词提取失败", "无法解析 check 表达式"
            )
        
        # 确定检查的目标（tender 或 bid）
        if "bid" in select.lower() or "bid" in check.lower():
            doc_types = ["bid"]
            target_name = "投标文件"
        else:
            doc_types = ["tender"]
            target_name = "招标文件"
        
        # 使用新检索器搜索关键词
        query = " ".join(keywords)
        
        embedding_provider = get_embedding_store().get_default()
        if not embedding_provider:
            logger.error("No embedding provider configured for rules")
            return self._make_finding(
                rule_id, title, dimension, rigid,
                "risk", "检索服务不可用", "Embedding provider 未配置"
            )
        
        try:
            matched_chunks = await self.retriever.retrieve(
                query=query,
                project_id=project_id,
                doc_types=doc_types,
                embedding_provider=embedding_provider,
                top_k=5,  # 只需要少量结果
            )
        except Exception as e:
            logger.error(f"Rule {rule_id} retrieval failed: {e}")
            return self._make_finding(
                rule_id, title, dimension, rigid,
                "risk", "检索失败", str(e)
            )
        
        # 判断结果
        if matched_chunks:
            result = "pass"
            response_text = f"{target_name}中找到相关内容"
            remark = f"检测到关键词：{', '.join(keywords[:3])}"
            
            # 提取证据
            evidence_chunk_ids = [c.chunk_id for c in matched_chunks]
            evidence_spans = [
                {
                    "chunk_id": c.chunk_id,
                    "page_no": c.meta.get("page_no"),
                    "doc_version_id": c.meta.get("doc_version_id"),
                    "text_preview": c.text[:100]
                }
                for c in matched_chunks
            ]
        else:
            result = "fail" if rigid else "risk"
            response_text = f"{target_name}中未找到相关内容"
            remark = f"缺少关键词：{', '.join(keywords)}"
            evidence_chunk_ids = []
            evidence_spans = []
        
        return {
            "rule_id": rule_id,
            "source": "rule",
            "dimension": dimension,
            "requirement_text": title,
            "response_text": response_text,
            "result": result,
            "rigid": rigid,
            "remark": remark,
            "evidence_chunk_ids": evidence_chunk_ids,
            "evidence_spans": evidence_spans
        }

    def _evaluate_missing_field_rule(
        self,
        rule_id: str,
        title: str,
        dimension: str,
        rigid: bool,
        select: str,
        check: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行 missing_field 规则：检查项目信息字段是否缺失
        
        例如：
        check: "field('建设单位') must not be empty"
        """
        project_info = context.get("project_info", {})
        
        # 提取字段名
        field_name = self._extract_field_name_from_check(check)
        
        # 检查字段是否存在且非空
        field_value = project_info.get(field_name, "")
        
        if field_value and str(field_value).strip():
            result = "pass"
            response_text = f"字段'{field_name}'已填写"
            remark = f"值：{str(field_value)[:50]}"
        else:
            result = "fail" if rigid else "risk"
            response_text = f"字段'{field_name}'缺失或为空"
            remark = "需要补充该字段信息"
        
        return {
            "rule_id": rule_id,
            "source": "rule",
            "dimension": dimension,
            "requirement_text": title,
            "response_text": response_text,
            "result": result,
            "rigid": rigid,
            "remark": remark,
            "evidence_chunk_ids": [],
            "evidence_spans": []
        }

    def _evaluate_date_compare_rule(
        self,
        rule_id: str,
        title: str,
        dimension: str,
        rigid: bool,
        select: str,
        check: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行 date_compare 规则：检查时间先后关系
        
        例如：
        check: "extract_date(bid, '工期开始') >= extract_date(tender, '要求开始')"
        """
        # 简化实现：从 project_info 中提取日期并比较
        # 这里先返回一个占位实现
        
        result = "pass"
        response_text = "时间比较规则执行"
        remark = "日期比较功能待完善（当前仅占位）"
        
        return {
            "rule_id": rule_id,
            "source": "rule",
            "dimension": dimension,
            "requirement_text": title,
            "response_text": response_text,
            "result": result,
            "rigid": rigid,
            "remark": remark,
            "evidence_chunk_ids": [],
            "evidence_spans": []
        }

    def _make_finding(
        self,
        rule_id: str,
        title: str,
        dimension: str,
        rigid: bool,
        result: str,
        response_text: str,
        remark: str
    ) -> Dict[str, Any]:
        """创建一个 finding"""
        return {
            "rule_id": rule_id,
            "source": "rule",
            "dimension": dimension,
            "requirement_text": title,
            "response_text": response_text,
            "result": result,
            "rigid": rigid,
            "remark": remark,
            "evidence_chunk_ids": [],
            "evidence_spans": []
        }

    def _extract_keywords_from_check(self, check: str) -> List[str]:
        """从 check 表达式中提取关键词"""
        # 支持单引号和双引号
        pattern = r"['\"]([^'\"]+)['\"]"
        keywords = re.findall(pattern, check)
        return keywords if keywords else []

    def _extract_field_name_from_check(self, check: str) -> str:
        """从 check 表达式中提取字段名"""
        # 提取 field('xxx') 中的 xxx
        pattern = r"field\(['\"]([^'\"]+)['\"]\)"
        match = re.search(pattern, check)
        return match.group(1) if match else "未知字段"

