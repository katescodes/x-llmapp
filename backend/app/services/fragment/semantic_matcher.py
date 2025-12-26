"""
从目录标题到PDF内容的语义搜索匹配器
不再预先识别所有范本，而是按需搜索

✅ 方案A：混合策略（关键词 + LLM语义判断）
✅ 方案C：上下文增强搜索（表格前后段落）
"""
from typing import List, Dict, Any, Optional, Tuple
from rapidfuzz import fuzz
import logging

logger = logging.getLogger(__name__)


def extract_table_context(
    pdf_items: List[Dict[str, Any]],
    table_index: int,
    context_before: int = 3,
    context_after: int = 1
) -> str:
    """
    ✅ 方案C：提取表格的上下文（前后段落）
    
    Args:
        pdf_items: PDF items列表
        table_index: 表格在items中的索引
        context_before: 前面取几个段落（默认3）
        context_after: 后面取几个段落（默认1）
    
    Returns:
        上下文文本字符串
    """
    context_texts = []
    
    # 提取表格前的段落
    for i in range(max(0, table_index - context_before), table_index):
        item = pdf_items[i]
        if item.get("type") == "paragraph":
            text = (item.get("text") or "").strip()
            if text:
                context_texts.append(text)
    
    # 提取表格本身的内容
    table = pdf_items[table_index]
    if table.get("type") == "table":
        table_data = table.get("tableData", [])
        table_text = " ".join([" ".join(row) for row in table_data[:5]])
        context_texts.append(f"[表格内容] {table_text}")
    
    # 提取表格后的段落
    for i in range(table_index + 1, min(len(pdf_items), table_index + 1 + context_after)):
        item = pdf_items[i]
        if item.get("type") == "paragraph":
            text = (item.get("text") or "").strip()
            if text:
                context_texts.append(text)
    
    return " ".join(context_texts)
    """
    根据目录标题推断关键词
    """
    title_lower = title.lower()
    
    # 定义标题到关键词的映射
    keyword_map = {
        "开标一览表": ["总投标价", "投标报价", "大写", "小写", "项目名称", "供货期", "项目编号"],
        "投标函": ["投标函", "我方承诺", "法定代表人", "签字", "盖章", "投标人"],
        "货物报价一览表": ["序号", "标的名称", "品牌", "规格型号", "单价", "总价", "合价", "制造商"],
        "报价一览表": ["序号", "标的名称", "品牌", "规格型号", "单价", "总价", "合价"],
        "商务要求": ["商务要求", "合同条款", "响应内容", "偏离", "正偏离", "负偏离"],
        "技术要求": ["技术要求", "技术", "响应内容", "偏离", "技术参数", "规格"],
        "技术方案": ["技术方案", "实施方案", "服务方案", "质量控制", "进度控制", "施工方案"],
        "法定代表人": ["法定代表人", "身份证明", "授权", "委托书", "代理人", "授权委托"],
        "授权委托书": ["授权委托书", "法定代表人", "授权", "委托", "代理人"],
        "资质证书": ["资质证书", "营业执照", "许可证", "认证", "证书", "资格"],
        "业绩": ["业绩", "项目名称", "合同", "甲方", "合同金额", "完成时间"],
    }
    
    # 精确匹配
    for key, keywords in keyword_map.items():
        if key in title:
            return keywords
    
    # 模糊匹配
    for key, keywords in keyword_map.items():
        if fuzz.partial_ratio(key, title) >= 80:
            return keywords
    
    # 默认：使用标题本身的关键词
    return [title]


def get_keywords_for_title(title: str) -> List[str]:
    """
    根据目录标题推断关键词
    """
    title_lower = title.lower()
    
    # 定义标题到关键词的映射
    keyword_map = {
        "开标一览表": ["总投标价", "投标报价", "大写", "小写", "项目名称", "供货期", "项目编号"],
        "投标函": ["投标函", "我方承诺", "法定代表人", "签字", "盖章", "投标人"],
        "货物报价一览表": ["序号", "标的名称", "品牌", "规格型号", "单价", "总价", "合价", "制造商"],
        "报价一览表": ["序号", "标的名称", "品牌", "规格型号", "单价", "总价", "合价"],
        "商务要求": ["商务要求", "合同条款", "响应内容", "偏离", "正偏离", "负偏离"],
        "技术要求": ["技术要求", "技术", "响应内容", "偏离", "技术参数", "规格"],
        "技术方案": ["技术方案", "实施方案", "服务方案", "质量控制", "进度控制", "施工方案"],
        "法定代表人": ["法定代表人", "身份证明", "授权", "委托书", "代理人", "授权委托"],
        "授权委托书": ["授权委托书", "法定代表人", "授权", "委托", "代理人"],
        "资质证书": ["资质证书", "营业执照", "许可证", "认证", "证书", "资格"],
        "业绩": ["业绩", "项目名称", "合同", "甲方", "合同金额", "完成时间"],
    }
    
    # 精确匹配
    for key, keywords in keyword_map.items():
        if key in title:
            return keywords
    
    # 模糊匹配
    for key, keywords in keyword_map.items():
        if fuzz.partial_ratio(key, title) >= 80:
            return keywords
    
    # 默认：使用标题本身的关键词
    return [title]


async def llm_verify_match(
    node_title: str,
    table_item: Dict[str, Any],
    table_context: str,
    llm_client,
    model: str = "gpt-4o-mini"  # ✅ 修正参数名
) -> Dict[str, Any]:
    """
    ✅ 方案A：使用LLM验证内容是否匹配目录标题（支持table和paragraph）
    
    Args:
        node_title: 目录节点标题
        table_item: 内容item（table或paragraph）
        table_context: 内容上下文（包含前后段落）
        llm_client: LLM客户端
        model: 模型名称
    
    Returns:
        {
            "is_match": bool,
            "confidence": float,
            "reason": str
        }
    """
    if not llm_client:
        # 如果没有LLM客户端，返回默认结果
        return {"is_match": True, "confidence": 0.7, "reason": "No LLM verification"}
    
    # 根据item类型调整Prompt描述
    item_type = table_item.get("type", "table")
    if item_type == "paragraph":
        content_desc = "文本段落"
        type_check = "文本内容是否符合该类型文档的特征（如正文、声明等）"
    else:
        content_desc = "表格"
        type_check = "表格内容是否包含该类型文档的典型字段"
    
    # 构建Prompt
    prompt = f"""任务：判断该{content_desc}是否为"{node_title}"

{content_desc}上下文（包含前后内容）：
{table_context[:1000]}

问题：这个{content_desc}是"{node_title}"吗？

请根据以下标准判断：
1. {type_check}
2. 前后的内容是否提到相关标题
3. 内容的完整性和实质性（避免只是标题行或目录项）

输出JSON格式：
{{
  "is_match": true/false,
  "confidence": 0.0-1.0,
  "reason": "判断理由（50字以内）"
}}
"""
    
    try:
        # 使用duck typing调用LLM（兼容chat或chat_completion方法）
        response = None
        if hasattr(llm_client, 'chat_completion'):
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                temperature=0.1,
                max_tokens=200,
            )
        elif hasattr(llm_client, 'chat'):
            # SimpleLLMOrchestrator使用chat方法（同步）
            import asyncio
            try:
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: llm_client.chat(
                        messages=[{"role": "user", "content": prompt}],
                        model_id=model,
                        temperature=0.1,
                        max_tokens=200,
                    )
                )
            except RuntimeError as e:
                # LLM配置问题（如模型不可用），降级到关键词匹配
                logger.warning(f"[llm_verify_match] LLM call failed: {e}, using keyword-only matching")
                return {"is_match": True, "confidence": 0.5, "reason": "LLM不可用，使用关键词"}
        else:
            logger.warning(f"[llm_verify_match] LLM client has no chat_completion or chat method")
            return {"is_match": True, "confidence": 0.5, "reason": "LLM客户端不支持"}
        
        # 解析LLM响应
        import json
        import re
        
        # 提取content
        if isinstance(response, dict):
            content = response.get("content", "")
            if not content and "choices" in response:
                # OpenAI格式
                choices = response.get("choices", [])
                if choices and isinstance(choices[0], dict):
                    message = choices[0].get("message", {})
                    content = message.get("content", "")
        elif isinstance(response, str):
            content = response
        else:
            content = str(response)
        
        if not content:
            logger.warning(f"[llm_verify_match] Empty response from LLM")
            return {"is_match": True, "confidence": 0.5, "reason": "LLM返回为空"}
        
        # 尝试提取JSON
        json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return {
                "is_match": bool(result.get("is_match", False)),
                "confidence": float(result.get("confidence", 0.5)),
                "reason": str(result.get("reason", "LLM判断"))
            }
        
        # 如果无法解析JSON，返回保守结果
        logger.warning(f"[llm_verify_match] Failed to parse JSON from LLM response: {content[:100]}")
        return {"is_match": False, "confidence": 0.3, "reason": "LLM响应解析失败"}
        
    except Exception as e:
        logger.warning(f"[llm_verify_match] Error: {e}, falling back to keyword-only matching")
        # LLM调用失败，返回中性结果（允许关键词得分起作用）
        return {"is_match": True, "confidence": 0.5, "reason": "LLM验证失败，使用关键词"}


async def search_best_match_in_pdf_async(
    node_title: str,
    pdf_items: List[Dict[str, Any]],
    llm_client=None,
    min_confidence: float = 0.4,  # ✅ 降低阈值到0.4
    use_llm: bool = True,
    top_k: int = 3,  # ✅ 关键词筛选保留top-3候选
) -> Optional[Dict[str, Any]]:
    """
    ✅ 方案A+C：从PDF items中搜索与目录标题最匹配的表格
    
    策略：
    1. 关键词快速筛选（获取top-k候选）
    2. 提取上下文（表格前后段落）
    3. LLM语义验证（精确判断）
    
    Args:
        node_title: 目录节点标题
        pdf_items: PDF解析后的items列表
        llm_client: LLM客户端（可选）
        min_confidence: 最低置信度阈值（默认0.4）
        use_llm: 是否使用LLM验证（默认True）
        top_k: 关键词筛选保留的候选数量（默认3）
    
    Returns:
        {
            "item_index": int,
            "item": Dict,
            "confidence": float,
            "match_reason": str,
            "llm_verified": bool,
        }
    """
    keywords = get_keywords_for_title(node_title)
    
    # ✅ 新增：根据标题判断期望的内容类型
    # 纯文本型：投标函、承诺书、声明等
    text_type_indicators = ["函", "声明", "承诺", "说明", "简介", "概述", "方案", "计划"]
    prefer_text = any(indicator in node_title for indicator in text_type_indicators)
    
    # Step 1: 关键词快速筛选，获取top-k候选（支持table和paragraph）
    candidates = []
    
    for idx, item in enumerate(pdf_items):
        item_type = item.get("type")
        
        # ✅ 支持table和paragraph两种类型
        if item_type == "table":
            table_data = item.get("tableData", [])
            if not table_data or len(table_data) < 2:
                continue
            
            # 提取表格内容文本
            content_text = "\n".join([
                " ".join(row) for row in table_data
            ])
            
            # ✅ 对于文本型节点，跳过表格（除非表格内容非常丰富）
            if prefer_text and len(content_text.strip()) < 100:
                continue
            
            # 跳过内容过少的表格（可能只是标题行）
            if len(content_text.strip()) < 10:
                continue
                
        elif item_type == "paragraph":
            text = item.get("text", "")
            if not text or len(text.strip()) < 20:  # 段落至少20字符
                continue
            content_text = text
            
            # ✅ 对于文本型节点（如"投标函"），优先选择长段落
            if prefer_text and len(content_text.strip()) < 50:
                continue  # 投标函通常是长文本，跳过短段落
        else:
            continue
        
        # ✅ 方案C：提取上下文
        if item_type == "table":
            context_text = extract_table_context(pdf_items, idx, context_before=3, context_after=1)
        else:
            # 段落自身就是内容，上下文权重较低
            context_text = content_text + "\n" + extract_table_context(pdf_items, idx, context_before=1, context_after=1)
        
        # 计算关键词匹配度（在上下文中搜索）
        match_count = sum(1 for kw in keywords if kw in context_text)
        match_ratio = match_count / len(keywords) if keywords else 0.0
        
        # 标题相似度（在上下文中搜索）
        title_similarity = 0.0
        for text_chunk in context_text.split():
            sim = fuzz.partial_ratio(node_title, text_chunk)
            if sim > title_similarity:
                title_similarity = sim
        
        # 初步得分
        initial_score = match_ratio * 0.7 + (title_similarity / 100.0) * 0.3
        
        # ✅ 内容类型匹配度加成（强化）
        type_bonus = 0.0
        if prefer_text and item_type == "paragraph":
            # 文本型节点匹配到paragraph，大幅加分
            type_bonus = 0.25  # 提高到25%
            # 如果段落长度合适（投标函通常200-2000字），再加分
            if 100 <= len(content_text) <= 3000:
                type_bonus += 0.10  # 额外10%
        elif not prefer_text and item_type == "table":
            type_bonus = 0.05  # 表格类型节点匹配到table，加5%
        elif prefer_text and item_type == "table":
            # 文本型节点匹配到table，扣分（除非关键词匹配度非常高）
            if match_ratio < 0.7:
                type_bonus = -0.20  # 扣20%
        
        initial_score += type_bonus
        
        # ✅ 内容长度合理性（针对投标函等文本型内容）
        content_length_score = 0.0
        if prefer_text and item_type == "paragraph":
            text_len = len(content_text)
            if text_len > 200:  # 投标函通常是长文本
                content_length_score = min(0.15, text_len / 2000.0)  # 最多15%
        
        initial_score += content_length_score
        
        if initial_score >= 0.2:  # 低阈值，让更多候选进入LLM验证
            candidates.append({
                "item_index": idx,
                "item": item,
                "item_type": item_type,
                "context": context_text,
                "content_text": content_text,
                "initial_score": initial_score,
                "matched_keywords": match_count,
                "total_keywords": len(keywords),
                "title_similarity": title_similarity,
                "type_bonus": type_bonus,
                "content_length": len(content_text),
            })
    
    # 按初步得分排序，取top-k
    candidates.sort(key=lambda x: x["initial_score"], reverse=True)
    candidates = candidates[:top_k]
    
    if not candidates:
        return None
    
    # Step 2: LLM精确验证
    best_match = None
    best_final_score = 0.0
    
    for candidate in candidates:
        if use_llm and llm_client:
            # ✅ 方案A：LLM语义验证
            llm_result = await llm_verify_match(
                node_title,
                candidate["item"],
                candidate["context"],
                llm_client
            )
            
            # 综合得分：关键词50% + LLM判断50%
            final_score = (
                candidate["initial_score"] * 0.5 + 
                (llm_result["confidence"] if llm_result["is_match"] else 0.0) * 0.5
            )
            
            match_reason = (
                f"类型:{candidate['item_type']}, "
                f"长度:{candidate.get('content_length', 0)}字符, "
                f"关键词{candidate['matched_keywords']}/{candidate['total_keywords']} "
                f"({candidate['initial_score']:.0%}), "
                f"标题相似度{candidate['title_similarity']:.0f}%, "
                f"LLM验证: {llm_result['reason']} (置信度{llm_result['confidence']:.2f})"
            )
            
            llm_verified = True
        else:
            # 不使用LLM，仅用关键词得分
            final_score = candidate["initial_score"]
            match_reason = (
                f"类型:{candidate['item_type']}, "
                f"长度:{candidate.get('content_length', 0)}字符, "
                f"关键词{candidate['matched_keywords']}/{candidate['total_keywords']} "
                f"({candidate['initial_score']:.0%}), "
                f"标题相似度{candidate['title_similarity']:.0f}%"
            )
            llm_verified = False
        
        if final_score > best_final_score and final_score >= min_confidence:
            best_final_score = final_score
            best_match = {
                "item_index": candidate["item_index"],
                "item": candidate["item"],
                "confidence": final_score,
                "match_reason": match_reason,
                "matched_keywords": candidate["matched_keywords"],
                "total_keywords": candidate["total_keywords"],
                "llm_verified": llm_verified,
            }
    
    return best_match


def search_best_match_in_pdf(
    node_title: str,
    pdf_items: List[Dict[str, Any]],
    min_confidence: float = 0.4
) -> Optional[Dict[str, Any]]:
    """
    同步版本（不使用LLM）
    """
    import asyncio
    return asyncio.run(search_best_match_in_pdf_async(
        node_title, pdf_items, None, min_confidence, use_llm=False
    ))


async def batch_search_for_directory_async(
    directory_nodes: List[Dict[str, Any]],
    pdf_items: List[Dict[str, Any]],
    llm_client=None,
    min_confidence: float = 0.4,
    use_llm: bool = True,
) -> Dict[str, Dict[str, Any]]:
    """
    批量为目录节点搜索PDF内容（异步版本，支持LLM）
    
    Args:
        directory_nodes: 目录节点列表
        pdf_items: PDF items
        llm_client: LLM客户端
        min_confidence: 最低置信度
        use_llm: 是否使用LLM验证
    
    Returns:
        {node_id: match_result, ...}
    """
    results = {}
    
    for node in directory_nodes:
        node_id = node.get("id")
        node_title = node.get("title", "")
        
        if not node_id or not node_title:
            continue
        
        logger.info(f"[batch_search] Searching for '{node_title}'...")
        
        match = await search_best_match_in_pdf_async(
            node_title, pdf_items, llm_client, min_confidence, use_llm
        )
        
        if match:
            results[node_id] = match
            logger.info(
                f"[batch_search] ✅ '{node_title}' -> Page{match['item'].get('pageNo')} "
                f"(confidence={match['confidence']:.2f}, llm={match['llm_verified']})"
            )
        else:
            logger.info(f"[batch_search] ❌ '{node_title}' -> No match")
    
    return results


def batch_search_for_directory(
    directory_nodes: List[Dict[str, Any]],
    pdf_items: List[Dict[str, Any]],
    min_confidence: float = 0.4
) -> Dict[str, Dict[str, Any]]:
    """
    批量搜索（同步版本，不使用LLM）
    """
    import asyncio
    return asyncio.run(batch_search_for_directory_async(
        directory_nodes, pdf_items, None, min_confidence, use_llm=False
    ))


