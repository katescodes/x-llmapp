"""
申报要求抽取 Spec (v2)
"""
import os
from typing import Dict
from app.platform.extraction.types import ExtractionSpec
from app.works.declare.schemas.requirements_v2 import RequirementsResultV2


def _load_prompt(filename: str) -> str:
    """加载 prompt 模板文件"""
    filepath = os.path.join(os.path.dirname(__file__), "..", "prompts", filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def build_requirements_spec() -> ExtractionSpec:
    """构建申报要求抽取规格"""
    prompt = _load_prompt("requirements_v2.md")
    
    queries: Dict[str, str] = {
        "base": os.getenv("DECLARE_REQUIREMENTS_QUERY_BASE", "申报通知 申报条件 申报要求 申报范围"),
        "eligibility": os.getenv("DECLARE_REQUIREMENTS_QUERY_ELIGIBILITY", "资格条件 申报资格 基本条件 专项条件"),
        "materials": os.getenv("DECLARE_REQUIREMENTS_QUERY_MATERIALS", "材料清单 申报材料 提交材料 附件清单"),
        "deadlines": os.getenv("DECLARE_REQUIREMENTS_QUERY_DEADLINES", "时间节点 截止时间 申报时间 填报时间"),
        "contact": os.getenv("DECLARE_REQUIREMENTS_QUERY_CONTACT", "咨询方式 联系方式 咨询电话 联系地址"),
    }
    
    top_k_per_query = int(os.getenv("DECLARE_REQUIREMENTS_TOPK_PER_QUERY", "30"))
    top_k_total = int(os.getenv("DECLARE_REQUIREMENTS_TOPK_TOTAL", "120"))
    
    return ExtractionSpec(
        task_type="requirements",
        prompt=prompt,
        queries=queries,
        topk_per_query=top_k_per_query,
        topk_total=top_k_total,
        doc_types=["declare_notice"],
        temperature=0.0,
        schema_model=RequirementsResultV2
    )

