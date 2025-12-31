"""
目录括号解析模块 (LLM-based Bracket Parser)

使用LLM解析招标要求中的括号说明，判断是否应该拆分为独立子节点。

特点：
- LLM语义理解，准确识别列表型 vs 描述型括号
- 批量处理，减少API调用次数
- 可选启用，失败不影响基础目录
"""
import logging
import json
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


async def parse_brackets_with_llm(
    nodes: List[Dict[str, Any]],
    llm: Any,
    model_id: Optional[str] = None,
    enable_parsing: bool = True,
) -> Dict[str, Any]:
    """
    使用LLM解析目录节点中的括号内容，生成L4子节点
    
    Args:
        nodes: 已细化的目录节点列表
        llm: LLM调用器
        model_id: 模型ID
        enable_parsing: 是否启用括号解析（默认True）
    
    Returns:
        {
            "enhanced_nodes": [...],  # 增强后的节点列表
            "added_count": 5,  # 新增L4节点数
            "parsed_parents": ["实施组织方案", ...],  # 被解析的父节点
            "stats": {...}
        }
    """
    if not enable_parsing:
        logger.info("[BracketParser] Disabled by parameter, skip parsing")
        return {
            "enhanced_nodes": nodes,
            "added_count": 0,
            "parsed_parents": [],
            "stats": {"enabled": False}
        }
    
    logger.info(f"[BracketParser] Starting LLM-based bracket parsing for {len(nodes)} nodes")
    
    try:
        # 1. 识别包含括号的L3节点
        bracket_candidates = _identify_bracket_nodes(nodes)
        
        if not bracket_candidates:
            logger.info("[BracketParser] No nodes with brackets found")
            return {
                "enhanced_nodes": nodes,
                "added_count": 0,
                "parsed_parents": [],
                "stats": {"no_bracket_nodes": True}
            }
        
        logger.info(f"[BracketParser] Found {len(bracket_candidates)} nodes with brackets")
        
        # 2. 批量调用LLM解析括号内容
        parse_results = await _batch_parse_brackets(bracket_candidates, llm, model_id)
        
        # 3. 为需要拆分的节点生成L4子节点
        new_l4_nodes = []
        parsed_parents = []
        
        for result in parse_results:
            if result["should_split"] and result["sub_items"]:
                parent_node = result["parent_node"]
                sub_items = result["sub_items"]
                
                l4_nodes = _generate_l4_nodes(
                    parent_node=parent_node,
                    sub_items=sub_items,
                )
                
                new_l4_nodes.extend(l4_nodes)
                parsed_parents.append(parent_node["title"])
                
                logger.info(
                    f"[BracketParser] Generated {len(l4_nodes)} L4 nodes "
                    f"for '{parent_node['title']}'"
                )
        
        # 4. 合并并重新排序
        enhanced_nodes = _merge_and_reorder_with_l4(nodes, new_l4_nodes)
        
        logger.info(
            f"[BracketParser] Done - added {len(new_l4_nodes)} L4 nodes, "
            f"total={len(enhanced_nodes)}, parsed_parents={len(parsed_parents)}"
        )
        
        return {
            "enhanced_nodes": enhanced_nodes,
            "added_count": len(new_l4_nodes),
            "parsed_parents": parsed_parents,
            "stats": {
                "enabled": True,
                "bracket_candidates": len(bracket_candidates),
                "parsed_count": len(parse_results),
                "split_count": len([r for r in parse_results if r["should_split"]]),
                "new_l4_nodes": len(new_l4_nodes),
            }
        }
        
    except Exception as e:
        logger.error(f"[BracketParser] Failed (non-fatal): {e}", exc_info=True)
        # 失败时返回原始节点，不影响基础功能
        return {
            "enhanced_nodes": nodes,
            "added_count": 0,
            "parsed_parents": [],
            "stats": {"error": str(e)}
        }


def _identify_bracket_nodes(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    识别包含括号的L3节点（候选解析节点）
    
    条件：
    - level == 3（只处理L3节点，避免过深）
    - title 或 notes 中包含括号
    - 括号内容长度 > 10个字符（过滤简单说明）
    """
    candidates = []
    
    # 括号模式
    bracket_pattern = re.compile(r'[（(]([^)）]{10,})[)）]')
    
    for node in nodes:
        # 只处理L3节点
        if node.get("level") != 3:
            continue
        
        # 从notes或title中查找括号
        text_to_check = node.get("notes", "") or node.get("title", "")
        
        if not text_to_check:
            continue
        
        # 检查是否包含有效括号
        match = bracket_pattern.search(text_to_check)
        if match:
            bracket_content = match.group(1)
            
            # 二次过滤：排除纯数字、日期、联系方式等
            if _is_meaningful_bracket(bracket_content):
                candidates.append({
                    **node,
                    "bracket_content": bracket_content,
                    "original_text": text_to_check,
                })
    
    return candidates


def _is_meaningful_bracket(content: str) -> bool:
    """判断括号内容是否有意义（不是纯数字、日期、联系方式等）"""
    # 排除纯数字
    if content.replace('.', '').replace('%', '').replace('万', '').replace('元', '').strip().isdigit():
        return False
    
    # 排除日期格式
    if re.match(r'^\d{4}[-年]\d{1,2}[-月]\d{1,2}', content):
        return False
    
    # 排除电话号码
    if re.match(r'^\d{11}$|^\d{3,4}-\d{7,8}', content):
        return False
    
    # 排除简单引用
    if content.strip() in ['详见附件', '见附件', '另行通知', '待定']:
        return False
    
    return True


async def _batch_parse_brackets(
    candidates: List[Dict[str, Any]],
    llm: Any,
    model_id: Optional[str],
) -> List[Dict[str, Any]]:
    """
    批量调用LLM解析括号内容
    
    策略：每次最多处理10个节点，减少单次Token消耗
    """
    results = []
    batch_size = 10
    
    for i in range(0, len(candidates), batch_size):
        batch = candidates[i:i + batch_size]
        logger.info(f"[BracketParser] Processing batch {i//batch_size + 1} ({len(batch)} nodes)")
        
        batch_result = await _parse_bracket_batch(batch, llm, model_id)
        results.extend(batch_result)
    
    return results


async def _parse_bracket_batch(
    batch: List[Dict[str, Any]],
    llm: Any,
    model_id: Optional[str],
) -> List[Dict[str, Any]]:
    """
    单批次LLM解析
    """
    # 构建批量Prompt
    prompt = _build_batch_parse_prompt(batch)
    
    # 调用LLM
    try:
        messages = [{"role": "user", "content": prompt}]
        
        llm_response = await llm.achat(
            messages=messages,
            model_id=model_id,
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=3000,
        )
        
        # 解析响应
        llm_output = llm_response.get("choices", [{}])[0].get("message", {}).get("content")
        if not llm_output:
            logger.warning("[BracketParser] LLM returned empty content")
            return []
        
        result_data = json.loads(llm_output)
        analyses = result_data.get("analyses", [])
        
        # 关联回原始节点
        results = []
        for idx, analysis in enumerate(analyses):
            if idx < len(batch):
                results.append({
                    "parent_node": batch[idx],
                    "should_split": analysis.get("should_split", False),
                    "reason": analysis.get("reason", ""),
                    "sub_items": analysis.get("sub_items", []),
                })
        
        return results
        
    except Exception as e:
        logger.error(f"[BracketParser] LLM call failed: {e}", exc_info=True)
        # 失败时返回空结果（不拆分）
        return [{
            "parent_node": node,
            "should_split": False,
            "reason": f"LLM解析失败: {str(e)}",
            "sub_items": []
        } for node in batch]


def _build_batch_parse_prompt(batch: List[Dict[str, Any]]) -> str:
    """构建批量解析的Prompt"""
    
    # 准备待分析的节点列表
    nodes_desc = []
    for idx, node in enumerate(batch, 1):
        nodes_desc.append(f"""
节点{idx}：
标题：{node.get('title', '')}
完整文本：{node.get('original_text', '')}
括号内容：{node.get('bracket_content', '')}
""")
    
    prompt = f"""你是一个招投标文件目录结构分析专家。请分析以下{len(batch)}个目录节点的括号内容，判断是否应该拆分为独立的子目录。

{"".join(nodes_desc)}

判断标准：
1. ✅ 应该拆分：括号内是明确的并列项列表（用、，及等分隔），且每项都是独立的文档/内容
   - 例如："实施组织方案（含组织架构图、人员配置表、岗位职责说明）"
   - 例如："技术方案（包括系统设计文档、接口规范、部署手册）"

2. ❌ 不应拆分：括号内是约束条件、描述性说明、引用、时间说明
   - 例如："项目经验（近3年内至少2个类似项目）" - 这是条件
   - 例如："工期（90天，自合同签订之日起）" - 这是说明
   - 例如："详细方案（详见附件3）" - 这是引用
   - 例如："总价（含税）" - 这是补充说明

3. 拆分规则：
   - 提取出所有并列项，去掉"包含"、"包括"、"如"、"等"等连接词
   - 每个子项应该是名词性短语，能独立成为一个文档标题
   - 如果只有1个子项，不拆分

返回JSON格式：
{{
  "analyses": [
    {{
      "node_index": 1,
      "should_split": true,
      "reason": "括号内包含3个独立的文档项",
      "sub_items": ["组织架构图", "人员配置表", "岗位职责说明"]
    }},
    {{
      "node_index": 2,
      "should_split": false,
      "reason": "括号内是时间约束说明，不是列表"
    }}
    // ... 其他节点
  ]
}}

请严格按照JSON格式输出，确保analyses数组有{len(batch)}个元素，按节点顺序对应。
"""
    
    return prompt


def _generate_l4_nodes(
    parent_node: Dict[str, Any],
    sub_items: List[str],
) -> List[Dict[str, Any]]:
    """
    为父节点生成L4子节点
    """
    l4_nodes = []
    parent_level = parent_node.get("level", 3)
    parent_title = parent_node.get("title", "")
    base_order_no = parent_node.get("order_no", 0) + 1
    
    for idx, sub_item in enumerate(sub_items):
        # 清理子项文本
        clean_title = _clean_sub_item_text(sub_item)
        
        if not clean_title or len(clean_title) < 2:
            continue
        
        l4_nodes.append({
            "title": clean_title,
            "level": parent_level + 1,  # L4
            "order_no": base_order_no + idx,
            "parent_ref": parent_title,
            "required": parent_node.get("required", True),
            "volume": parent_node.get("volume", ""),
            "notes": f"从括号说明中提取：{sub_item}",
            "evidence_chunk_ids": parent_node.get("evidence_chunk_ids", []),
            "source": "bracket_parser_llm",
            "meta": {
                "parent_requirement_id": parent_node.get("meta", {}).get("requirement_id"),
                "extracted_from": "bracket_content",
                "original_text": sub_item,
            }
        })
    
    return l4_nodes


def _clean_sub_item_text(text: str) -> str:
    """清理子项文本，去除多余的标点和空格"""
    # 去除常见的前缀词
    prefixes = ['含', '包含', '包括', '如', '等', '及', '和', '、']
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):]
    
    # 去除尾部的"等"、"等内容"
    text = re.sub(r'等(内容|材料|文件)?$', '', text)
    
    # 去除多余空格和标点
    text = text.strip('、，,；;。. \t\n')
    
    return text


def _merge_and_reorder_with_l4(
    original_nodes: List[Dict[str, Any]],
    new_l4_nodes: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    合并原始节点和新的L4节点，并重新排序
    
    策略：
    1. 将L4节点插入到对应父节点的后面
    2. 按 (level, order_no) 排序
    3. 重新分配 order_no
    """
    if not new_l4_nodes:
        return original_nodes
    
    # 构建父节点索引
    parent_map = {}
    for i, node in enumerate(original_nodes):
        parent_map[node["title"]] = i
    
    # 插入新节点
    merged = original_nodes.copy()
    
    for new_node in new_l4_nodes:
        parent_title = new_node.get("parent_ref")
        
        if parent_title and parent_title in parent_map:
            # 找到插入位置（父节点后面）
            insert_pos = parent_map[parent_title] + 1
            
            # 跳过已有的同级节点
            while insert_pos < len(merged) and merged[insert_pos].get("parent_ref") == parent_title:
                insert_pos += 1
            
            merged.insert(insert_pos, new_node)
            
            # 更新后续节点的索引
            for title in list(parent_map.keys()):
                if parent_map[title] >= insert_pos:
                    parent_map[title] += 1
            parent_map[new_node["title"]] = insert_pos
        else:
            # 父节点不存在，追加到末尾
            merged.append(new_node)
    
    # 排序
    merged.sort(key=lambda n: (n.get("level", 99), n.get("order_no", 0)))
    
    # 重新分配 order_no
    for i, node in enumerate(merged):
        node["order_no"] = i + 1
    
    return merged

