"""
招标要求后处理器
从招标要求生成投标响应提取指南，用于需求驱动的投标响应提取
"""
import logging
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)


def generate_bid_response_extraction_guide(
    requirements: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    从招标要求生成投标响应提取指南
    
    核心思想：只提取招标文件中要求的内容，避免过度提取
    
    Args:
        requirements: 招标要求列表
    
    Returns:
        {
            "must_extract_norm_keys": ["total_price_cny", "duration_days", ...],  # 必须提取的标准化字段
            "optional_norm_keys": ["warranty_months", ...],                        # 可选提取的标准化字段
            "dimension_focus": {                                                   # 各维度的提取重点
                "qualification": {
                    "required": true,
                    "focus_keywords": ["营业执照", "资质证书", ...],
                    "expected_count": 5
                },
                "price": {
                    "required": true,
                    "focus_keywords": ["投标报价", "总价", ...],
                    "expected_count": 3
                },
                ...
            },
            "extraction_instructions": [                                           # 提取指令（给LLM的具体指导）
                "必须提取投标报价，包含total_price_cny字段",
                "必须提取工期承诺，包含duration_days字段",
                ...
            ],
            "avoid_extraction": [                                                  # 避免提取的内容（防止过度细化）
                "公司注册地址（除非招标文件明确要求）",
                "注册资本（除非招标文件明确要求）",
                ...
            ],
            "statistics": {                                                        # 统计信息
                "total_requirements": 45,
                "by_dimension": {"qualification": 10, "technical": 15, ...},
                "hard_requirements": 8,
                "scoring_requirements": 12,
            }
        }
    """
    logger.info(f"开始生成投标响应提取指南，requirements数量={len(requirements)}")
    
    # 1. 统计信息
    dimension_stats = {}
    norm_keys_required = set()
    norm_keys_optional = set()
    hard_requirements = []
    scoring_requirements = []
    
    for req in requirements:
        dimension = req.get("dimension", "other")
        is_hard = req.get("is_hard", False)
        req_type = req.get("req_type", "")
        requirement_text = req.get("requirement_text", "")
        value_schema = req.get("value_schema_json", {}) or {}
        
        # 统计维度
        dimension_stats[dimension] = dimension_stats.get(dimension, 0) + 1
        
        # 收集硬性要求
        if is_hard:
            hard_requirements.append(req)
        
        # 收集评分要求
        if req_type == "scoring" or "评分" in requirement_text or "得分" in requirement_text:
            scoring_requirements.append(req)
        
        # 提取norm_key（从value_schema中）
        if isinstance(value_schema, dict):
            norm_key = value_schema.get("norm_key")
            if norm_key:
                if is_hard:
                    norm_keys_required.add(norm_key)
                else:
                    norm_keys_optional.add(norm_key)
    
    # 2. 生成维度聚焦策略
    dimension_focus = _generate_dimension_focus(requirements, dimension_stats)
    
    # 3. 生成提取指令
    extraction_instructions = _generate_extraction_instructions(
        requirements, 
        norm_keys_required, 
        norm_keys_optional
    )
    
    # 4. 生成避免提取清单
    avoid_extraction = _generate_avoid_list(requirements, dimension_stats)
    
    # 5. 组装指南
    guide = {
        "must_extract_norm_keys": sorted(list(norm_keys_required)),
        "optional_norm_keys": sorted(list(norm_keys_optional)),
        "dimension_focus": dimension_focus,
        "extraction_instructions": extraction_instructions,
        "avoid_extraction": avoid_extraction,
        "statistics": {
            "total_requirements": len(requirements),
            "by_dimension": dimension_stats,
            "hard_requirements": len(hard_requirements),
            "scoring_requirements": len(scoring_requirements),
        }
    }
    
    logger.info(
        f"生成提取指南完成: "
        f"must_extract={len(norm_keys_required)}, "
        f"optional={len(norm_keys_optional)}, "
        f"dimensions={len(dimension_stats)}"
    )
    
    return guide


def _generate_dimension_focus(
    requirements: List[Dict[str, Any]], 
    dimension_stats: Dict[str, int]
) -> Dict[str, Dict[str, Any]]:
    """生成各维度的提取重点"""
    dimension_focus = {}
    
    # 按维度分组
    by_dimension = {}
    for req in requirements:
        dimension = req.get("dimension", "other")
        if dimension not in by_dimension:
            by_dimension[dimension] = []
        by_dimension[dimension].append(req)
    
    # 为每个维度生成聚焦策略
    for dimension, reqs in by_dimension.items():
        # 提取关键词
        keywords = set()
        for req in reqs:
            text = req.get("requirement_text", "")
            # 简单关键词提取（可以后续优化）
            for word in ["营业执照", "资质证书", "业绩", "投标报价", "总价", "工期", "质保期", 
                        "授权书", "保证金", "付款", "交付", "验收", "技术参数", "规格", "性能"]:
                if word in text:
                    keywords.add(word)
        
        # 判断是否必需
        has_hard = any(req.get("is_hard", False) for req in reqs)
        
        dimension_focus[dimension] = {
            "required": has_hard,
            "focus_keywords": sorted(list(keywords))[:10],  # 最多10个关键词
            "expected_count": len(reqs),  # 期望提取数量
            "hard_count": sum(1 for req in reqs if req.get("is_hard", False)),
        }
    
    return dimension_focus


def _generate_extraction_instructions(
    requirements: List[Dict[str, Any]], 
    norm_keys_required: Set[str],
    norm_keys_optional: Set[str]
) -> List[str]:
    """生成提取指令（给LLM的具体指导）"""
    instructions = []
    
    # 1. 必须提取的norm_key指令
    norm_key_descriptions = {
        "total_price_cny": "投标报价（总价），单位：人民币元",
        "duration_days": "工期承诺，单位：天",
        "warranty_months": "质保期承诺，单位：月",
        "bid_security_amount_cny": "投标保证金金额，单位：人民币元",
        "company_name": "公司名称",
        "credit_code": "统一社会信用代码",
        "legal_representative": "法定代表人",
        "doc_business_license_present": "营业执照是否提供",
        "doc_authorization_present": "授权委托书是否提供",
        "doc_qualification_present": "资质证书是否提供",
        "doc_security_receipt_present": "保证金回执是否提供",
    }
    
    for norm_key in norm_keys_required:
        desc = norm_key_descriptions.get(norm_key, norm_key)
        instructions.append(f"✅ 必须提取：{desc}（normalized_fields_json中必须包含 {norm_key}）")
    
    for norm_key in norm_keys_optional:
        desc = norm_key_descriptions.get(norm_key, norm_key)
        instructions.append(f"🔹 可选提取：{desc}（如有相关内容，normalized_fields_json中包含 {norm_key}）")
    
    # 2. 基于requirements的具体指令
    for req in requirements:
        if req.get("is_hard", False):
            dimension = req.get("dimension", "")
            text = req.get("requirement_text", "")
            # 简化文本（取前50字）
            text_short = text[:50] + "..." if len(text) > 50 else text
            instructions.append(f"✅ 硬性要求 ({dimension}): {text_short}")
    
    # 限制指令数量（最多20条）
    return instructions[:20]


def _generate_avoid_list(
    requirements: List[Dict[str, Any]], 
    dimension_stats: Dict[str, int]
) -> List[str]:
    """
    生成避免提取清单（防止过度提取）
    
    核心原则：如果招标文件没有要求，就不要提取
    """
    avoid_list = []
    
    # 1. 通用避免项（除非招标文件明确要求）
    avoid_list.append("❌ 不要提取公司注册地址、总部地址（除非招标文件明确要求地域限制）")
    avoid_list.append("❌ 不要提取公司注册资本、实收资本（除非招标文件明确要求最低注册资本）")
    avoid_list.append("❌ 不要提取公司成立日期、成立时间（除非招标文件明确要求成立年限）")
    avoid_list.append("❌ 不要提取公司简介、发展历程、荣誉奖项（除非招标文件明确要求）")
    avoid_list.append("❌ 不要提取股东信息、组织架构（除非招标文件明确要求）")
    
    # 2. 粒度控制（避免混合或过度拆分）
    avoid_list.append("❌ 不要将同一证件（如营业执照）的不同字段混合成一条响应")
    avoid_list.append("   正确做法：如果招标文件只要求'营业执照'，提取'营业执照'即可，不要加上地址、注册资本等")
    avoid_list.append("❌ 不要将同一个价格在不同位置出现多次提取为多条响应")
    avoid_list.append("❌ 不要将业绩案例的每个细节拆分成多条（可简化为'提供X个案例'）")
    
    # 3. 基于requirements判断是否需要避免某些维度
    if "qualification" not in dimension_stats:
        avoid_list.append("⚠️ 招标文件未要求资格证明，不要过度提取资格类信息")
    
    if "technical" not in dimension_stats:
        avoid_list.append("⚠️ 招标文件未要求技术参数，不要过度提取技术规格信息")
    
    if "business" not in dimension_stats or dimension_stats.get("business", 0) < 3:
        avoid_list.append("⚠️ 招标文件对商务条款要求较少，不要过度提取培训、售后等细节")
    
    # 4. 文本长度控制
    avoid_list.append("⚠️ 响应文本长度：简单证件4-20字，数值10-30字，方案80-150字，超过200字需要简化")
    
    # 5. 目标数量控制
    total_reqs = len(requirements)
    target_min = int(total_reqs * 0.8)
    target_max = int(total_reqs * 1.2)
    avoid_list.append(f"⚠️ 目标响应数：{target_min}-{target_max}条（基于{total_reqs}条招标要求）")
    avoid_list.append("⚠️ 宁可少而精，不要多而杂（覆盖核心要求即可）")
    
    return avoid_list


def generate_dynamic_prompt_supplement(guide: Dict[str, Any], requirements: List[Dict[str, Any]] = None) -> str:
    """
    基于提取指南生成动态prompt补充内容
    
    这个内容将附加到原有的bid_response提取prompt中
    
    Args:
        guide: 提取指南（generate_bid_response_extraction_guide的输出）
        requirements: 招标要求列表（用于生成具体要求清单）
    
    Returns:
        prompt补充内容（markdown格式）
    """
    instructions = guide.get("extraction_instructions", [])
    avoid_list = guide.get("avoid_extraction", [])
    must_keys = guide.get("must_extract_norm_keys", [])
    optional_keys = guide.get("optional_norm_keys", [])
    dimension_focus = guide.get("dimension_focus", {})
    stats = guide.get("statistics", {})
    
    supplement = """
---
## 📊 **招标要求统计**
"""
    
    # 添加统计信息
    total_reqs = stats.get("total_requirements", 0)
    hard_reqs = stats.get("hard_requirements", 0)
    scoring_reqs = stats.get("scoring_requirements", 0)
    by_dimension = stats.get("by_dimension", {})
    
    supplement += f"- 招标要求总数：**{total_reqs}条**\n"
    supplement += f"- 硬性要求（must）：{hard_reqs}条\n"
    supplement += f"- 评分要求（scoring）：{scoring_reqs}条\n"
    supplement += f"- 维度分布：{', '.join([f'{k}({v})' for k, v in sorted(by_dimension.items())])}\n"
    
    # 目标响应数
    target_min = int(total_reqs * 0.8)
    target_max = int(total_reqs * 1.2)
    supplement += f"\n⚠️ **目标响应数：{target_min}-{target_max}条**（覆盖率80%-120%）\n"
    
    # 添加招标要求列表（核心！）
    if requirements:
        supplement += "\n---\n## 📝 **招标要求清单（请逐条提取响应）**\n\n"
        supplement += "**⚠️ 重要：请针对以下每条招标要求，在投标文档中寻找对应的响应内容。**\n\n"
        
        # 按维度分组展示
        by_dimension = {}
        for req in requirements:
            dimension = req.get("dimension", "other")
            if dimension not in by_dimension:
                by_dimension[dimension] = []
            by_dimension[dimension].append(req)
        
        dim_name_map = {
            "qualification": "资格条件",
            "technical": "技术参数",
            "business": "商务条款",
            "price": "价格",
            "doc_structure": "文档结构",
            "schedule_quality": "工期质量",
            "other": "其他"
        }
        
        for dimension, reqs in sorted(by_dimension.items()):
            dim_cn = dim_name_map.get(dimension, dimension)
            supplement += f"\n### 📂 {dim_cn} ({dimension})\n\n"
            
            for i, req in enumerate(reqs[:20], 1):  # 每个维度最多显示20条
                req_id = req.get("requirement_id", "")
                req_text = req.get("requirement_text", "")
                is_hard = req.get("is_hard", False)
                value_schema = req.get("value_schema_json", {}) or {}
                norm_key = value_schema.get("norm_key") if isinstance(value_schema, dict) else None
                
                # 截断过长文本
                if len(req_text) > 150:
                    req_text = req_text[:150] + "..."
                
                # 标记硬性要求
                hard_mark = "▲" if is_hard else ""
                
                supplement += f"{i}. {hard_mark}**{req_text}**\n"
                if norm_key:
                    supplement += f"   - norm_key: `{norm_key}`\n"
                supplement += f"   - requirement_id: `{req_id}`\n"
            
            if len(reqs) > 20:
                supplement += f"   ... 等共{len(reqs)}条要求\n"
    
    supplement += "\n---\n## 📋 **提取指南（基于招标要求）**\n\n"
    
    # 添加维度聚焦信息
    if dimension_focus:
        supplement += "### 📂 **各维度提取重点**\n\n"
        for dim, info in sorted(dimension_focus.items()):
            if dim == "out_of_scope":
                continue
            expected = info.get("expected_count", 0)
            hard_count = info.get("hard_count", 0)
            keywords = info.get("focus_keywords", [])
            
            dim_name_map = {
                "qualification": "资格条件",
                "technical": "技术参数",
                "business": "商务条款",
                "price": "价格",
                "doc_structure": "文档结构",
                "schedule_quality": "工期质量"
            }
            dim_cn = dim_name_map.get(dim, dim)
            
            supplement += f"- **{dim_cn}**：预期{expected}条响应"
            if hard_count > 0:
                supplement += f"（含{hard_count}条硬性要求）"
            if keywords:
                supplement += f"，关键词：{', '.join(keywords[:5])}"
            supplement += "\n"
    
    supplement += "\n### ✅ **必须提取的内容**\n\n"
    
    # 添加必须提取的指令
    must_instructions = [inst for inst in instructions if "✅" in inst or "必须" in inst]
    for i, instruction in enumerate(must_instructions[:10], 1):  # 最多10条
        clean_inst = instruction.replace('✅', '').strip()
        supplement += f"{i}. {clean_inst}\n"
    
    if not must_instructions:
        supplement += "（根据招标要求动态生成）\n"
    
    # 可选提取
    optional_instructions = [inst for inst in instructions if "🔹" in inst or "可选" in inst]
    if optional_instructions:
        supplement += "\n### 🔹 **可选提取的内容**\n\n"
        for i, instruction in enumerate(optional_instructions[:8], 1):  # 最多8条
            clean_inst = instruction.replace('🔹', '').strip()
            supplement += f"{i}. {clean_inst}\n"
    
    # 避免提取（重要！）
    supplement += "\n### ❌ **严格禁止/避免提取的内容**\n\n"
    for i, avoid_item in enumerate(avoid_list[:12], 1):  # 最多12条
        supplement += f"{avoid_item}\n"
    
    # Norm Keys
    supplement += "\n### 🔑 **允许的norm_key清单**\n\n"
    supplement += "**必须包含的norm_key**（硬性要求）：\n"
    if must_keys:
        for key in must_keys[:8]:
            supplement += f"  - `{key}`\n"
    else:
        supplement += "  - （无硬性要求的norm_key）\n"
    
    if optional_keys:
        supplement += "\n**可选的norm_key**（评分要求）：\n"
        for key in optional_keys[:8]:
            supplement += f"  - `{key}`\n"
    
    # 最终检查提醒
    supplement += "\n### 🎯 **提取完成后自检清单**\n\n"
    supplement += f"1. ✅ 响应数量是否在{target_min}-{target_max}条之间？\n"
    supplement += "2. ✅ 每条响应是否都对应了一个招标要求？\n"
    supplement += "3. ✅ 是否避免了提取招标文件未要求的信息（如注册资本、地址等）？\n"
    supplement += "4. ✅ 每条响应是否都有_norm_key字段（即使为null）？\n"
    supplement += "5. ✅ 维度分类是否正确（业绩案例在qualification，培训在business）？\n"
    supplement += "6. ✅ 文本长度是否适中（没有超过200字的长文本）？\n"
    supplement += "7. ✅ 每条响应是否都有evidence_segment_ids？\n"
    
    return supplement

