"""
项目信息抽取规格 (v2)
"""
import os
from pathlib import Path
from typing import Dict

from app.platform.extraction.types import ExtractionSpec


def _load_prompt(filename: str) -> str:
    """加载prompt文件"""
    prompt_dir = Path(__file__).parent.parent / "prompts"
    prompt_file = prompt_dir / filename
    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read().strip()


def build_project_info_spec() -> ExtractionSpec:
    """
    构建项目信息抽取规格
    
    Returns:
        ExtractionSpec: 包含 queries、prompt、topk 等配置
    """
    # 加载 prompt
    prompt = _load_prompt("project_info_v2.md")
    
    # 四个查询，覆盖不同维度（可通过环境变量覆盖）
    queries_env = os.getenv("V2_PROJECT_INFO_QUERIES_JSON")
    if queries_env:
        import json
        queries = json.loads(queries_env)
    else:
        queries: Dict[str, str] = {
            "base": "招标公告 项目名称 项目编号 预算金额 采购人 代理机构 投标截止 开标 时间 地点 联系人 电话",
            "technical": "技术要求 技术规范 技术参数 设备参数 性能指标 功能要求 规格 型号 参数表",
            "business": "商务条款 合同条款 付款方式 交付期 工期 质保 验收 违约责任 发票",
            "scoring": "评分标准 评标办法 评审办法 评分细则 分值 权重 加分项 否决项 资格审查",
        }
    
    # 可配置参数
    top_k_per_query = int(os.getenv("V2_RETRIEVAL_TOPK_PER_QUERY", "30"))
    top_k_total = int(os.getenv("V2_RETRIEVAL_TOPK_TOTAL", "120"))
    
    return ExtractionSpec(
        prompt=prompt,
        queries=queries,
        topk_per_query=top_k_per_query,
        topk_total=top_k_total,
        doc_types=["tender"],
        temperature=0.0,  # 保证可复现
    )

