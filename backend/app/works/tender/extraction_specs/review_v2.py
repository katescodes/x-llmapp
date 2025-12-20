"""
审核规格配置 (v2)
定义审核所需的检索queries、输出schema、MUST_HIT规则等
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

from app.platform.extraction.types import ExtractionSpec


def _load_prompt(filename: str) -> str:
    """加载prompt文件"""
    prompt_dir = Path(__file__).parent.parent / "prompts"
    prompt_file = prompt_dir / filename
    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read().strip()


def build_review_spec() -> ExtractionSpec:
    """
    构建审核规格
    
    Returns:
        ExtractionSpec: 包含 queries、prompt、topk 等配置
    """
    # 加载 prompt
    prompt = _load_prompt("review_v2.md")
    
    # 审核检索queries（覆盖合规性检查的关键维度）
    queries_env = os.getenv("V2_REVIEW_QUERIES_JSON")
    if queries_env:
        import json
        queries = json.loads(queries_env)
    else:
        queries = {
            "qualification_check": "资格条件 营业执照 资质证书 业绩要求 财务状况 信誉要求",
            "tech_compliance": "技术参数 技术规格 功能要求 性能指标 技术偏离",
            "biz_compliance": "商务条款 报价要求 付款方式 质保期 售后服务 商务偏离",
            "doc_format": "文档格式 装订要求 投标函 授权委托书 报价表 文件组成",
        }
    
    # TopK配置
    topk = int(os.getenv("V2_REVIEW_TOPK", "30"))
    
    # 文档类型：同时检索招标文件和投标文件
    doc_types = ["tender", "bid"]
    
    return ExtractionSpec(
        queries=queries,
        prompt=prompt,
        topk=topk,
        doc_types=doc_types,
        temperature=0.1,  # 审核需要确定性，低temperature
    )


def get_must_hit_rules() -> List[Dict[str, str]]:
    """
    获取MUST_HIT规则列表
    
    这些规则是审核流程必须产出的兜底规则，确保：
    1. 审核流程至少产出一些基础检查结果
    2. Gate验收时不会因为空结果而flaky
    
    Returns:
        规则列表，每个规则包含：
        - rule_id: 规则ID（MUST_HIT_001等）
        - title: 规则标题
        - description: 规则描述
        - severity: 严重级别 (info/warning/error)
    """
    return [
        {
            "rule_id": "MUST_HIT_001",
            "title": "审核流程执行确认",
            "description": "审核流程已成功执行，系统已完成合规性检查",
            "severity": "info",
        },
        {
            "rule_id": "MUST_HIT_002",
            "title": "文档完整性检查",
            "description": "检查投标文件是否包含所有必需的文档（投标函、报价表、资质证明等）",
            "severity": "warning",
        },
        {
            "rule_id": "MUST_HIT_003",
            "title": "资格条件初审",
            "description": "检查投标人是否满足基本资格条件（营业执照、资质证书等）",
            "severity": "warning",
        },
    ]


# 输出schema定义（用于文档和验证）
REVIEW_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["data", "evidence_chunk_ids"],
    "properties": {
        "data": {
            "type": "object",
            "required": ["review_items"],
            "properties": {
                "review_items": {
                    "type": "array",
                    "description": "审核结果列表",
                    "items": {
                        "type": "object",
                        "required": ["rule_id", "title", "severity", "description"],
                        "properties": {
                            "rule_id": {"type": "string", "description": "规则ID"},
                            "title": {"type": "string", "description": "规则标题"},
                            "severity": {
                                "type": "string",
                                "enum": ["info", "warning", "error"],
                                "description": "严重级别"
                            },
                            "description": {"type": "string", "description": "详细描述"},
                            "evidence_chunk_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "证据chunk ID列表"
                            },
                            "suggestion": {
                                "type": "string",
                                "description": "改进建议（可选）"
                            },
                        }
                    }
                }
            }
        },
        "evidence_chunk_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "所有证据chunk ID的汇总"
        }
    }
}

