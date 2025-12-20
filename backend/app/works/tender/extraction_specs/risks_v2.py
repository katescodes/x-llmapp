"""
风险抽取规格 (v2)
"""
from pathlib import Path

from app.platform.extraction.types import ExtractionSpec


def _load_prompt(filename: str) -> str:
    """加载prompt文件"""
    prompt_dir = Path(__file__).parent.parent / "prompts"
    prompt_file = prompt_dir / filename
    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read().strip()


def build_risks_spec() -> ExtractionSpec:
    """
    构建风险抽取规格
    
    Returns:
        ExtractionSpec: 包含 query、prompt、topk 等配置
    """
    prompt = _load_prompt("risks_v2.md")
    
    return ExtractionSpec(
        task_type="extract_risks",
        prompt=prompt,
        queries="招标要求 技术规范 资质条件 合规要求 风险条款",
        topk_per_query=20,
        topk_total=20,
        doc_types=["tender"],
        temperature=0.0,
    )

