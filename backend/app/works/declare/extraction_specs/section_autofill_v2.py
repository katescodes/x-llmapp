"""
章节自动填充 Spec (v2)
"""
import os
from typing import Dict
from app.platform.extraction.types import ExtractionSpec
from app.works.declare.schemas.section_v2 import SectionResultV2


def _load_prompt(filename: str) -> str:
    """加载 prompt 模板文件"""
    filepath = os.path.join(os.path.dirname(__file__), "..", "prompts", filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def build_section_autofill_spec(node_title: str, requirements_summary: str = "") -> ExtractionSpec:
    """
    构建章节填充规格
    
    Args:
        node_title: 章节标题
        requirements_summary: 申报要求摘要
    """
    prompt_template = _load_prompt("section_autofill_v2.md")
    # 格式化 prompt，嵌入 node_title 和 requirements_summary
    prompt = prompt_template.replace("{node_title}", node_title).replace("{requirements_summary}", requirements_summary or "（无摘要）")
    
    # 根据章节标题派生查询
    base_query = node_title
    queries: Dict[str, str] = {
        "base": f"{base_query} {os.getenv('DECLARE_SECTION_QUERY_BASE', '企业信息 技术资料 项目背景')}",
        "tech": os.getenv("DECLARE_SECTION_QUERY_TECH", "技术方案 技术指标 技术参数 研发能力"),
        "finance": os.getenv("DECLARE_SECTION_QUERY_FINANCE", "财务数据 经营状况 资产负债 收入利润"),
        "team": os.getenv("DECLARE_SECTION_QUERY_TEAM", "团队介绍 人员构成 核心成员 研发团队"),
    }
    
    top_k_per_query = int(os.getenv("DECLARE_SECTION_TOPK_PER_QUERY", "20"))
    top_k_total = int(os.getenv("DECLARE_SECTION_TOPK_TOTAL", "80"))
    
    return ExtractionSpec(
        task_type="section_autofill",
        prompt=prompt,
        queries=queries,
        topk_per_query=top_k_per_query,
        topk_total=top_k_total,
        doc_types=["declare_company", "declare_tech", "declare_other"],
        temperature=0.3,  # 稍高温度以获得更自然的内容
        schema_model=SectionResultV2
    )

