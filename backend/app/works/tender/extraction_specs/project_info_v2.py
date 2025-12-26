"""
项目信息抽取规格 (v2)
"""
import os
from pathlib import Path
from typing import Dict, Optional

from app.platform.extraction.types import ExtractionSpec


def _load_prompt(filename: str) -> str:
    """加载prompt文件（fallback机制）"""
    prompt_dir = Path(__file__).parent.parent / "prompts"
    prompt_file = prompt_dir / filename
    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read().strip()


async def build_project_info_spec_async(pool=None) -> ExtractionSpec:
    """
    构建项目信息抽取规格（异步版本，支持数据库加载）
    
    ⚠️ V3 版本：九大类招标信息抽取
    
    优先从数据库加载最新的prompt，如果数据库中没有则使用文件fallback
    
    Args:
        pool: 数据库连接池（可选）
    
    Returns:
        ExtractionSpec: 包含 queries、prompt、topk 等配置
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # 尝试从数据库加载prompt（优先使用 V3 模块）
    prompt = None
    if pool:
        try:
            from app.services.prompt_loader import PromptLoaderService
            loader = PromptLoaderService(pool)
            # 优先尝试加载 V3 模块
            prompt = await loader.get_active_prompt("project_info_v3")
            if prompt:
                logger.info(f"✅ [Prompt] Loaded from DATABASE for project_info_v3, length={len(prompt)}")
                print(f"✅ [Prompt] Loaded from DATABASE for project_info_v3, length={len(prompt)}")
            else:
                # Fallback 到旧模块名（向后兼容）
                prompt = await loader.get_active_prompt("project_info")
                if prompt:
                    logger.info(f"✅ [Prompt] Loaded from DATABASE for project_info (legacy), length={len(prompt)}")
                    print(f"✅ [Prompt] Loaded from DATABASE for project_info (legacy), length={len(prompt)}")
        except Exception as e:
            logger.warning(f"⚠️ [Prompt] Failed to load from database: {e}")
            print(f"⚠️ [Prompt] Failed to load from database: {e}")
    
    # Fallback：从文件加载（V3版本）
    if not prompt:
        prompt = _load_prompt("project_info_v3.md")
        logger.info(f"📁 [Prompt] Using FALLBACK (file) for project_info_v3, length={len(prompt)}")
        print(f"📁 [Prompt] Using FALLBACK (file) for project_info_v3, length={len(prompt)}")
    
    # 六个查询，覆盖六大类维度（可通过环境变量覆盖）
    queries_env = os.getenv("V3_PROJECT_INFO_QUERIES_JSON")
    if queries_env:
        import json
        queries = json.loads(queries_env)
    else:
        queries: Dict[str, str] = {
            # 1. 项目概览（合并：基本信息 + 范围 + 进度 + 保证金）
            "project_overview": "招标公告 项目名称 项目编号 采购人 招标人 业主 代理机构 联系人 电话 项目地点 资金来源 采购方式 预算金额 招标控制价 最高限价 控制价 项目范围 采购内容 采购清单 标段 包段 分包 标段划分 标段预算 标段编号 投标截止时间 投标文件递交截止时间 开标时间 开标当日 开标地点 递交方式 递交地点 线上投标 线下投标 工期 交付期 实施周期 里程碑 投标保证金 保证金 保函 银行保函 履约保证金 履约担保 质量保证金 保证金金额 保证金形式 保证金递交 保证金退还 保证金没收",
            
            # 2. 投标人资格
            "bidder_qualification": "投标人资格 资格要求 资质要求 资质证书 营业执照 业绩要求 项目经验 类似项目 人员要求 项目经理 技术负责人 财务要求 资产负债率 投标限制 禁止投标 资格审查 资格证明文件",
            
            # 3. 评审与评分（扩展查询词以提升召回）
            "evaluation_and_scoring": "评分标准 评审办法 评分细则 评分表 评标办法 评审标准 综合评分法 最低评标价法 性价比法 评标方法 商务评审 技术评审 价格评审 资信评审 服务评审 售后服务评审 企业资质评分 项目业绩评分 技术方案评分 价格分计算 满分 分值 得分 计分 扣分 加分 权重 评分权重 加分项 扣分项 否决项 废标条件 资格审查 评审专家 评标委员会 评分细项 评分子项 评分标准表 评审打分 综合打分 评标基准价",
            
            # 4. 商务条款
            "business_terms": "商务条款 合同条款 付款方式 付款比例 付款节点 交付期 交货期 服务期 履约周期 质保期 质量保证期 验收方式 验收标准 违约责任 违约金 发票 税费 合同签订 合同管理 价格构成 报价范围 保密要求 知识产权",
            
            # 5. 技术要求
            "technical_requirements": "技术要求 技术规范 技术标准 技术参数 技术指标 设备参数 性能指标 性能要求 功能要求 功能参数 规格 型号 参数表 技术清单 不低于 大于等于 小于等于 额定 标称 CPU 内存 硬盘 显卡 处理器 操作系统 功率 电压 电流 频率 转速 流量 压力 温度 湿度 尺寸 重量 厚度 直径 长度 宽度 高度 容量 精度 防护等级 IP等级 材质 品牌 质量标准 国家标准 行业标准 GB ISO 工艺要求 安装要求 调试要求 测试要求 验收标准 备品备件 专用工具 技术培训",
            
            # 6. 文件编制
            "document_preparation": "投标文件 文件编制 文件结构 文件组成 正本 副本 装订要求 封面要求 页码要求 格式要求 必填表单 投标函 报价表 法定代表人授权书 资格证明文件清单 技术文件 商务文件 签字盖章 密封要求",
        }
    
    # 可配置参数
    # ⚠️ 六大类需要适当的检索范围
    top_k_per_query = int(os.getenv("V3_RETRIEVAL_TOPK_PER_QUERY", "40"))  # 每个查询40条（增加以覆盖合并的内容）
    top_k_total = int(os.getenv("V3_RETRIEVAL_TOPK_TOTAL", "150"))  # 总共150条（6类 × 平均25条）
    
    return ExtractionSpec(
        prompt=prompt,
        queries=queries,
        topk_per_query=top_k_per_query,
        topk_total=top_k_total,
        doc_types=["tender"],
        temperature=0.0,
    )


def build_project_info_spec() -> ExtractionSpec:
    """
    构建项目信息抽取规格（同步版本，使用文件）
    
    ⚠️ V3 版本：六大类招标信息抽取
    
    向后兼容，直接从文件加载
    
    Returns:
        ExtractionSpec: 包含 queries、prompt、topk 等配置
    """
    # 加载 prompt（V3版本）
    prompt = _load_prompt("project_info_v3.md")
    
    # 九个查询，覆盖九大类维度
    queries_env = os.getenv("V3_PROJECT_INFO_QUERIES_JSON")
    if queries_env:
        import json
        queries = json.loads(queries_env)
    else:
        queries: Dict[str, str] = {
            # 1. 项目概览
            "project_overview": "招标公告 项目名称 项目编号 采购人 招标人 业主 代理机构 联系人 电话 项目地点 资金来源 采购方式 预算金额 招标控制价 最高限价 控制价",
            
            # 2. 范围与标段
            "scope_and_lots": "项目范围 采购内容 采购清单 标段 包段 分包 标段划分 标段预算 标段编号",
            
            # 3. 进度与递交
            "schedule_and_submission": "投标截止时间 投标文件递交截止时间 开标时间 开标当日 开标地点 递交方式 递交地点 线上投标 线下投标 工期 交付期 实施周期 里程碑",
            
            # 4. 投标人资格
            "bidder_qualification": "投标人资格 资格要求 资质要求 资质证书 营业执照 业绩要求 项目经验 类似项目 人员要求 项目经理 技术负责人 财务要求 资产负债率 投标限制 禁止投标 资格审查 资格证明文件",
            
            # 5. 评审与评分（扩展查询词以提升召回）
            "evaluation_and_scoring": "评分标准 评审办法 评分细则 评分表 评标办法 评审标准 综合评分法 最低评标价法 性价比法 评标方法 商务评审 技术评审 价格评审 资信评审 服务评审 售后服务评审 企业资质评分 项目业绩评分 技术方案评分 价格分计算 满分 分值 得分 计分 扣分 加分 权重 评分权重 加分项 扣分项 否决项 废标条件 资格审查 评审专家 评标委员会 评分细项 评分子项 评分标准表 评审打分 综合打分 评标基准价",
            
            # 6. 商务条款
            "business_terms": "商务条款 合同条款 付款方式 付款比例 付款节点 交付期 交货期 服务期 履约周期 质保期 质量保证期 验收方式 验收标准 违约责任 违约金 发票 税费 合同签订 合同管理 价格构成 报价范围 保密要求 知识产权",
            
            # 7. 技术要求
            "technical_requirements": "技术要求 技术规范 技术标准 技术参数 技术指标 设备参数 性能指标 性能要求 功能要求 功能参数 规格 型号 参数表 技术清单 不低于 大于等于 小于等于 额定 标称 CPU 内存 硬盘 显卡 处理器 操作系统 功率 电压 电流 频率 转速 流量 压力 温度 湿度 尺寸 重量 厚度 直径 长度 宽度 高度 容量 精度 防护等级 IP等级 材质 品牌 质量标准 国家标准 行业标准 GB ISO 工艺要求 安装要求 调试要求 测试要求 验收标准 备品备件 专用工具 技术培训",
            
            # 8. 文件编制
            "document_preparation": "投标文件 文件编制 文件结构 文件组成 正本 副本 装订要求 封面要求 页码要求 格式要求 必填表单 投标函 报价表 法定代表人授权书 资格证明文件清单 技术文件 商务文件 签字盖章 密封要求",
            
            # 9. 保证金与担保
            "bid_security": "投标保证金 保证金 保函 银行保函 履约保证金 履约担保 质量保证金 保证金金额 保证金形式 保证金递交 保证金退还 保证金没收",
        }
    
    # 可配置参数
    # ⚠️ 九大类需要更大的检索范围
    top_k_per_query = int(os.getenv("V3_RETRIEVAL_TOPK_PER_QUERY", "30"))  # 每个查询30条
    top_k_total = int(os.getenv("V3_RETRIEVAL_TOPK_TOTAL", "150"))  # 总共150条（9类 × 平均17条）
    
    return ExtractionSpec(
        prompt=prompt,
        queries=queries,
        topk_per_query=top_k_per_query,
        topk_total=top_k_total,
        doc_types=["tender"],
        temperature=0.0,
    )
