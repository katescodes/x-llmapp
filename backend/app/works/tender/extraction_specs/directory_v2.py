"""
目录生成抽取规格 V2
"""
import os
from pathlib import Path
from typing import Dict

from app.platform.extraction.types import ExtractionSpec


def _load_prompt(filename: str) -> str:
    """加载 prompt 模板"""
    prompt_dir = Path(__file__).parent.parent / "prompts"
    prompt_file = prompt_dir / filename
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    return prompt_file.read_text(encoding="utf-8")


def build_directory_spec() -> ExtractionSpec:
    """
    构建目录生成抽取规格
    
    Returns:
        ExtractionSpec: 目录生成配置
    """
    # 加载 Prompt 模板
    prompt = _load_prompt("directory_v2.md")
    
    # 三个查询维度
    queries: Dict[str, str] = {
        "directory": "投标文件目录 投标文件组成 投标文件格式 目录结构 编制要求 章节 顺序",
        "forms": "格式范本 表格 模板 投标函 法定代表人 身份证明 授权委托书 附件",
        "requirements": "必填 必须提交 需提供 否则废标 否决项 资格审查 文件要求",
    }
    
    # 检索参数（可通过环境变量覆盖）
    topk_per_query = int(os.getenv("V2_RETRIEVAL_TOPK_PER_QUERY", "30"))
    topk_total = int(os.getenv("V2_RETRIEVAL_TOPK_TOTAL", "120"))
    
    # Schema model（用于严格校验）
    from app.works.tender.schemas.directory_v2 import DirectoryResultV2
    
    return ExtractionSpec(
        task_type="generate_directory",
        prompt=prompt,
        queries=queries,
        topk_per_query=topk_per_query,
        topk_total=topk_total,
        doc_types=["tender"],
        temperature=0.0,  # 确定性输出
        schema_model=DirectoryResultV2,  # 严格 schema 校验
    )

