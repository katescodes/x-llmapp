"""
申报书目录抽取 Spec (v2)
"""
import os
from typing import Dict
from app.platform.extraction.types import ExtractionSpec
from app.works.declare.schemas.directory_v2 import DirectoryResultV2


def _load_prompt(filename: str) -> str:
    """加载 prompt 模板文件"""
    filepath = os.path.join(os.path.dirname(__file__), "..", "prompts", filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def build_directory_spec() -> ExtractionSpec:
    """构建目录抽取规格"""
    prompt = _load_prompt("directory_v2.md")
    
    queries: Dict[str, str] = {
        "structure": os.getenv("DECLARE_DIRECTORY_QUERY_STRUCTURE", "申报书目录 申报书格式 申报书组成 目录结构 章节"),
        "template": os.getenv("DECLARE_DIRECTORY_QUERY_TEMPLATE", "附件 模板 申报书模板 格式范本 一、二、三、四"),
        "requirements": os.getenv("DECLARE_DIRECTORY_QUERY_REQUIREMENTS", "必填 必须提交 需提供 材料要求"),
    }
    
    top_k_per_query = int(os.getenv("DECLARE_DIRECTORY_TOPK_PER_QUERY", "30"))
    top_k_total = int(os.getenv("DECLARE_DIRECTORY_TOPK_TOTAL", "120"))
    
    return ExtractionSpec(
        task_type="directory",
        prompt=prompt,
        queries=queries,
        topk_per_query=top_k_per_query,
        topk_total=top_k_total,
        doc_types=["declare_notice"],  # ✅ 正确的类型
        temperature=0.0,
        schema_model=DirectoryResultV2
    )

