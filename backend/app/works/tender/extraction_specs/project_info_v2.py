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
            # ✅ 扩展base查询：增加招标文件常用术语（招标控制价、最高限价等）
            "base": "招标公告 项目名称 项目编号 预算金额 招标控制价 最高限价 控制价 采购人 招标人 业主 代理机构 投标截止时间 投标文件递交截止时间 开标时间 开标当日 开标地点 联系人 电话 工期 质量标准",
            # ✅ 大幅扩展technical查询：增加各类技术参数关键词
            "technical": "技术要求 技术规范 技术标准 技术参数 技术指标 设备参数 性能指标 性能要求 功能要求 功能参数 规格 型号 参数表 技术清单 不低于 大于等于 小于等于 额定 标称 CPU 内存 硬盘 显卡 处理器 操作系统 功率 电压 电流 频率 转速 流量 压力 温度 湿度 尺寸 重量 厚度 直径 长度 宽度 高度 容量 精度 防护等级 IP等级 材质 品牌",
            "business": "商务条款 合同条款 付款方式 交付期 工期 质保 验收 违约责任 发票",
            "scoring": "评分标准 评标办法 评审办法 评分细则 分值 权重 加分项 否决项 资格审查",
        }
    
    # 可配置参数
    # ✅ 增加检索数量，确保技术参数文档能被召回
    top_k_per_query = int(os.getenv("V2_RETRIEVAL_TOPK_PER_QUERY", "50"))  # 从30增加到50
    top_k_total = int(os.getenv("V2_RETRIEVAL_TOPK_TOTAL", "200"))  # 从120增加到200
    
    return ExtractionSpec(
        prompt=prompt,
        queries=queries,
        topk_per_query=top_k_per_query,
        topk_total=top_k_total,
        doc_types=["tender"],
        temperature=0.0,  # 保证可复现
    )

