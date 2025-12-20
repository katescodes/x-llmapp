"""
模板分析器（总入口）
整合 docx_structure + template_style_analyzer + template_applyassets_llm
一次性产出完整的模板分析结果
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .docx_structure import extract_doc_blocks, get_blocks_summary
from .template_style_analyzer import extract_style_profile, infer_role_mapping
from .template_applyassets_llm import (
    build_apply_assets_with_llm,
    validate_apply_assets,
)

logger = logging.getLogger(__name__)


def analyze_template(
    docx_path: str,
    template_name: str,
    model_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    分析模板，产出完整的 analysis_json
    
    包含三部分：
    1. applyAssets: LLM 理解的保留/删除计划、插入点等
    2. styleProfile: 样式定义（从 styles.xml 解析）
    3. roleMapping: 样式角色映射（h1~h9, body 等）
    
    Args:
        docx_path: 模板文件路径
        template_name: 模板名称
        model_id: LLM 模型 ID（可选）
        
    Returns:
        analysis_json 字典
    """
    logger.info(f"开始分析模板: {template_name} ({docx_path})")
    
    try:
        # 1. 提取文档结构（blocks）
        logger.info("步骤 1/4: 提取文档结构")
        blocks = extract_doc_blocks(docx_path)
        blocks_summary = get_blocks_summary(blocks)
        
        logger.info(f"文档结构: {blocks_summary}")
        
        # 2. 提取样式配置
        logger.info("步骤 2/4: 提取样式配置")
        style_profile = extract_style_profile(docx_path)
        
        logger.info(f"样式数量: {len(style_profile.get('styles', []))}")
        
        # 3. 推断角色映射
        logger.info("步骤 3/4: 推断角色映射")
        role_mapping = infer_role_mapping(style_profile)
        
        logger.info(f"角色映射: {list(role_mapping.keys())}")
        
        # 4. LLM 生成 applyAssets
        logger.info("步骤 4/4: LLM 分析应用资产")
        apply_assets = build_apply_assets_with_llm(
            template_name=template_name,
            blocks=blocks,
            model_id=model_id
        )
        
        # 5. 验证和修正
        apply_assets = validate_apply_assets(apply_assets, blocks)
        
        logger.info(f"LLM 分析完成: "
                   f"anchors={len(apply_assets.get('anchors', []))}, "
                   f"keep={len(apply_assets.get('keepPlan', {}).get('keepBlockIds', []))}, "
                   f"delete={len(apply_assets.get('keepPlan', {}).get('deleteBlockIds', []))}, "
                   f"confidence={apply_assets.get('policy', {}).get('confidence', 0)}")
        
        # 6. 组装完整结果
        analysis = {
            "applyAssets": apply_assets,
            "styleProfile": style_profile,
            "roleMapping": role_mapping,
            "meta": {
                "templateName": template_name,
                "docxPath": docx_path,
                "blocksSummary": blocks_summary,
            }
        }
        
        logger.info("模板分析完成")
        
        return analysis
    
    except Exception as e:
        logger.error(f"模板分析失败: {e}", exc_info=True)
        
        # 返回最小可用结果
        return {
            "applyAssets": {
                "anchors": [],
                "keepPlan": {
                    "keepBlockIds": [],
                    "deleteBlockIds": [],
                    "notes": "分析失败"
                },
                "policy": {
                    "strategy": "copy_template_and_prune_then_insert",
                    "confidence": 0.0,
                    "warnings": [f"模板分析失败: {str(e)}"]
                }
            },
            "styleProfile": {
                "styles": [],
                "numbering": {}
            },
            "roleMapping": {
                f"h{i}": f"Heading {i}" for i in range(1, 10)
            },
            "meta": {
                "templateName": template_name,
                "error": str(e)
            }
        }


def get_analysis_summary(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    获取分析结果摘要（用于前端展示）
    
    Returns:
        摘要字典，包含关键信息
    """
    apply_assets = analysis.get("applyAssets", {})
    role_mapping = analysis.get("roleMapping", {})
    meta = analysis.get("meta", {})
    
    policy = apply_assets.get("policy", {})
    keep_plan = apply_assets.get("keepPlan", {})
    anchors = apply_assets.get("anchors", [])
    
    return {
        "templateName": meta.get("templateName"),
        "confidence": policy.get("confidence", 0),
        "warnings": policy.get("warnings", []),
        "anchorsCount": len(anchors),
        "hasContentMarker": any(a.get("type") == "marker" for a in anchors),
        "keepBlocksCount": len(keep_plan.get("keepBlockIds", [])),
        "deleteBlocksCount": len(keep_plan.get("deleteBlockIds", [])),
        "headingStyles": {
            k: v for k, v in role_mapping.items()
            if k.startswith("h")
        },
        "bodyStyle": role_mapping.get("body"),
        "blocksSummary": meta.get("blocksSummary", {}),
    }

