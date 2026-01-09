"""
范本切片 LLM 服务
使用 LLM 识别招标文件中的各种格式范本边界
"""
from __future__ import annotations
import json
import logging
from typing import List, Dict, Any

from app.services.llm_client import llm_json
from app.works.tender.snippet.doc_blocks import get_block_text_snippet

logger = logging.getLogger(__name__)

# 标准范本类型定义
NORM_KEYS = {
    "bid_letter": "投标函",
    "power_of_attorney": "授权委托书",
    "bid_opening_form": "开标一览表",
    "price_list": "货物报价一览表",
    "biz_deviation": "商务偏离表",
    "tech_deviation": "技术偏离表",
    "tech_plan": "技术方案提纲",
    "legal_representative_cert": "法定代表人身份证明",
    "license_list": "资质证书清单",
    "material_list": "重要资料清单",
    "qualification_statement": "资格声明函",
    "undertaking": "承诺书",
    "similar_project": "类似项目业绩表",
    "personnel_resume": "项目人员简历表"
}


def build_snippet_detect_prompt(blocks: List[Dict[str, Any]]) -> str:
    """
    构建范本检测 LLM prompt
    
    Args:
        blocks: 文档 blocks（已定位到格式章节）
        
    Returns:
        LLM prompt
    """
    # 准备 blocks 摘要（给 LLM）
    blocks_summary = []
    for block in blocks:
        summary = {
            "blockId": block["blockId"],
            "type": block["type"],
            "textSnippet": get_block_text_snippet(block, max_length=200)
        }
        
        # 如果是表格，补充行数信息
        if block["type"] == "table":
            summary["rowCount"] = len(block.get("rows", []))
        
        blocks_summary.append(summary)
    
    # 构建 prompt
    prompt = f"""你是"招标文件格式范本识别专家"。

我会给你一个招标文件的 blocks 列表（按文档顺序）。
你的任务：识别其中所有的**格式范文/格式模板**（投标函、法人授权书、开标一览表等），并确定每个范文的边界（起始和结束 blockId）。

**什么是格式范文？**
- 招标文件中提供的**空白模板**，供投标人填写使用
- 通常包含"格式"、"附件"、"模板"等字样
- 例如："投标函（格式）"、"附件1：法人授权书"、"开标一览表"

**重要规则：**
1. **优先识别下列标准范文**（最常见，绝对不能遗漏）：
   - 投标函/投标书
   - 法人授权书/授权委托书/法定代表人身份证明
   - 开标一览表/报价一览表/投标报价表
   - 商务偏离表/技术偏离表
   - 资格声明函/承诺书

2. 只输出范围（startBlockId/endBlockId），不要改写内容
3. 不要生成表格内容，表格会由代码自动提取
4. 一个范文通常包括：标题段落 + 说明段落 + 内容段落/表格
5. **范文标题通常较短**（<50字），且包含"格式"、"附件"、"模板"、"表"等词

标准范本类型（norm_key）：
- bid_letter: 投标函
- power_of_attorney: 授权委托书
- bid_opening_form: 开标一览表
- price_list: 货物报价一览表/报价明细表
- biz_deviation: 商务偏离表/商务条款响应表
- tech_deviation: 技术偏离表/技术条款响应表
- tech_plan: 技术方案提纲
- legal_representative_cert: 法定代表人身份证明
- license_list: 资质证书清单
- material_list: 重要资料清单
- qualification_statement: 资格声明函
- undertaking: 承诺书/廉洁承诺书
- similar_project: 类似项目业绩表
- personnel_resume: 项目人员简历表

**输出格式（严格 JSON）：**
```json
[
  {{
    "norm_key": "bid_letter",
    "title": "投标函",
    "startBlockId": "b120",
    "endBlockId": "b168",
    "suggestOutlineTitles": ["投标函", "投标函及附件"],
    "confidence": 0.9
  }},
  {{
    "norm_key": "power_of_attorney",
    "title": "授权委托书（格式）",
    "startBlockId": "b169",
    "endBlockId": "b200",
    "suggestOutlineTitles": ["授权委托书", "授权书"],
    "confidence": 0.85
  }}
]
```

**字段说明：**
- norm_key: 从上面标准类型中选择，如果不在列表中用 "other"
- title: 范本原始标题（从文档中提取）
- startBlockId: 范本起始块 ID（包含标题段落）
- endBlockId: 范本结束块 ID（包含最后一个段落/表格）
  ⚠️ **重要**：如果范文只有一个block（如单个表格），startBlockId和endBlockId可以相同
- suggestOutlineTitles: 建议匹配的目录节点标题（数组，用于自动填充）
- confidence: 识别置信度（0.0-1.0）

**边界识别技巧：**
- 范文通常从标题开始（如"附件1：投标函"）
- 到下一个范文标题之前结束，或到说明文字结束
- 如果范文是单个表格，startBlockId = endBlockId = 表格的blockId
- 如果范文包含多个段落/表格，endBlockId是最后一个block的ID

**文档 blocks：**
{json.dumps(blocks_summary, ensure_ascii=False, indent=2)}

请分析并输出 JSON 数组。
"""
    
    return prompt


def detect_snippets(
    blocks: List[Dict[str, Any]],
    model_id: str = "gpt-oss-120b"
) -> List[Dict[str, Any]]:
    """
    使用 LLM 检测格式范本
    
    Args:
        blocks: 文档 blocks（通常是格式章节的 blocks）
        model_id: LLM 模型 ID
        
    Returns:
        检测到的范本列表
    """
    if not blocks:
        logger.warning("blocks 为空，返回空列表")
        return []
    
    logger.info(f"开始 LLM 检测范本，blocks 数量: {len(blocks)}, model: {model_id}")
    
    try:
        # 1. 构建 prompt
        prompt = build_snippet_detect_prompt(blocks)
        
        # 2. 调用 LLM
        result = llm_json(
            prompt=prompt,
            model_id=model_id,
            temperature=0.0,
            max_tokens=4000
        )
        
        # 3. 验证结果
        if not isinstance(result, list):
            logger.error(f"LLM 返回格式错误，不是数组: {type(result)}")
            return []
        
        # 4. 验证每个范本
        valid_snippets = []
        for item in result:
            if not isinstance(item, dict):
                logger.warning(f"跳过无效范本（不是字典）: {item}")
                continue
            
            # 必需字段
            required_fields = ["norm_key", "title", "startBlockId", "endBlockId"]
            if not all(field in item for field in required_fields):
                logger.warning(f"跳过无效范本（缺少必需字段）: {item}")
                continue
            
            # 补充默认值
            item.setdefault("suggestOutlineTitles", [])
            item.setdefault("confidence", 0.5)
            
            valid_snippets.append(item)
        
        logger.info(f"LLM 检测完成: {len(valid_snippets)} 个有效范本")
        return valid_snippets
    
    except Exception as e:
        logger.error(f"LLM 检测失败: {e}", exc_info=True)
        return []


def validate_snippet_bounds(
    snippet: Dict[str, Any],
    blocks: List[Dict[str, Any]]
) -> bool:
    """
    验证范本边界是否有效
    
    Args:
        snippet: 范本字典
        blocks: 文档 blocks
        
    Returns:
        边界是否有效
    """
    start_id = snippet.get("startBlockId")
    end_id = snippet.get("endBlockId")
    
    if not start_id or not end_id:
        return False
    
    # 查找索引
    block_ids = [b["blockId"] for b in blocks]
    
    try:
        start_idx = block_ids.index(start_id)
        end_idx = block_ids.index(end_id)
        
        # ✅ 允许单个block的范文（很多范文就是一个表格）
        if end_idx < start_idx:
            logger.warning(f"范本边界无效: end < start ({start_id} -> {end_id})")
            return False
        
        # 范围不应该太大（>500 blocks 可能有问题）
        if end_idx - start_idx > 500:
            logger.warning(f"范本范围过大: {end_idx - start_idx} blocks")
            return False
        
        return True
    
    except ValueError as e:
        logger.warning(f"范本边界 blockId 未找到: {e}")
        return False


def slice_blocks(
    blocks: List[Dict[str, Any]],
    start_block_id: str,
    end_block_id: str
) -> List[Dict[str, Any]]:
    """
    根据边界切片 blocks
    
    Args:
        blocks: 完整 blocks
        start_block_id: 起始 blockId
        end_block_id: 结束 blockId
        
    Returns:
        切片后的 blocks
    """
    block_ids = [b["blockId"] for b in blocks]
    
    try:
        start_idx = block_ids.index(start_block_id)
        end_idx = block_ids.index(end_block_id)
        
        # 包含结束块
        return blocks[start_idx:end_idx + 1]
    
    except ValueError as e:
        logger.error(f"切片失败: {e}")
        return []

