"""
Rules Evaluator - 规则审核引擎
支持确定性规则执行，生成 review findings
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import yaml


class RulesEvaluator:
    """规则评估器"""

    def __init__(self):
        """初始化规则评估器"""
        pass

    def evaluate(
        self,
        rule_set_version: Dict[str, Any],
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        执行规则评估
        
        Args:
            rule_set_version: 规则集版本（包含 content_yaml）
            context: 执行上下文，包含：
                - tender_chunks: 招标文件 chunks
                - bid_chunks: 投标文件 chunks
                - project_info: 项目信息（可选）
                
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
                - evidence_chunk_ids: 证据 chunk IDs
        """
        findings = []
        
        # 解析规则内容
        try:
            content_yaml = rule_set_version.get("content_yaml", "")
            rules_data = yaml.safe_load(content_yaml)
            rules = rules_data.get("rules", [])
        except Exception as e:
            # 解析失败，返回空结果
            print(f"[WARN] Failed to parse rules: {e}")
            return findings
        
        # 执行每条规则
        for rule in rules:
            try:
                finding = self._evaluate_rule(rule, context)
                if finding:
                    findings.append(finding)
            except Exception as e:
                # 单条规则失败不影响其他规则
                print(f"[WARN] Rule {rule.get('id', 'unknown')} evaluation failed: {e}")
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
                    "evidence_chunk_ids": []
                })
        
        return findings

    def _evaluate_rule(
        self,
        rule: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        执行单条规则
        
        Args:
            rule: 规则定义
            context: 执行上下文
            
        Returns:
            finding 或 None（规则不适用）
        """
        rule_id = rule.get("id", "unknown")
        title = rule.get("title", "")
        dimension = rule.get("dimension", "其他")
        severity = rule.get("severity", "medium")
        rigid = rule.get("rigid", False)
        select = rule.get("select", "")
        check = rule.get("check", "")
        
        # 识别规则类型并执行
        if isinstance(check, str):
            # A. exists 规则：必须存在某关键词
            if "must contain" in check or "contains" in check:
                return self._evaluate_exists_rule(
                    rule_id, title, dimension, rigid, select, check, context
                )
            
            # B. missing_field 规则：字段缺失检测
            elif "field" in check and "missing" in check:
                return self._evaluate_missing_field_rule(
                    rule_id, title, dimension, rigid, select, check, context
                )
            
            # C. date_compare 规则：时间先后
            elif "date" in check or "<=" in check or ">=" in check:
                return self._evaluate_date_compare_rule(
                    rule_id, title, dimension, rigid, select, check, context
                )
        
        # 未识别的规则类型，跳过
        return None

    def _evaluate_exists_rule(
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
        执行 exists 规则：检查是否存在某关键词/段落
        
        例如：
        select: "chunks where category='tender'"
        check: "bid_chunks must contain('营业执照', '有效期')"
        """
        # 提取要检查的关键词
        keywords = self._extract_keywords_from_check(check)
        
        # 确定检查的目标（tender 或 bid）
        if "bid" in check.lower():
            target_chunks = context.get("bid_chunks", [])
            target_name = "投标文件"
        else:
            target_chunks = context.get("tender_chunks", [])
            target_name = "招标文件"
        
        # 检查是否存在关键词
        matched_chunks = []
        for chunk in target_chunks:
            content = chunk.get("content", "")
            if any(kw in content for kw in keywords):
                matched_chunks.append(chunk)
        
        # 判断结果
        if matched_chunks:
            result = "pass"
            response_text = f"{target_name}中找到相关内容"
            remark = f"检测到关键词：{', '.join(keywords[:3])}"
        else:
            result = "fail" if rigid else "risk"
            response_text = f"{target_name}中未找到相关内容"
            remark = f"缺少关键词：{', '.join(keywords)}"
        
        evidence_chunk_ids = [c.get("chunk_id", "") for c in matched_chunks[:5]]
        
        return {
            "rule_id": rule_id,
            "source": "rule",
            "dimension": dimension,
            "requirement_text": title,
            "response_text": response_text,
            "result": result,
            "rigid": rigid,
            "remark": remark,
            "evidence_chunk_ids": evidence_chunk_ids
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
        check: "project_info.field('建设单位') must not be empty"
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
            "evidence_chunk_ids": []
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
        # 简化实现：从 project_info 或 chunks 中提取日期并比较
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
            "evidence_chunk_ids": []
        }

    def _extract_keywords_from_check(self, check: str) -> List[str]:
        """从 check 表达式中提取关键词"""
        # 简单正则提取引号内的内容
        pattern = r"['\"]([^'\"]+)['\"]"
        keywords = re.findall(pattern, check)
        return keywords if keywords else []

    def _extract_field_name_from_check(self, check: str) -> str:
        """从 check 表达式中提取字段名"""
        # 提取 field('xxx') 中的 xxx
        pattern = r"field\(['\"]([^'\"]+)['\"]\)"
        match = re.search(pattern, check)
        return match.group(1) if match else "未知字段"

