"""
格式范本识别与匹配模块 (Template Matcher)

混合策略：
1. 阶段1：文档分片时，轻量级规则识别潜在范本（meta标记）
2. 阶段2：目录生成后，LLM精确匹配范本到节点
3. 阶段3：自动填充节点正文，用户可复核

特点：
- 规则 + LLM混合，平衡速度与准确性
- 只对潜在范本调用LLM，减少成本
- 自动填充，用户可审核/修改
"""
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import json

logger = logging.getLogger(__name__)


# ==================== 阶段1：轻量级规则识别 ====================

def identify_potential_template(
    chunk_text: str,
    chunk_meta: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    文档分片时的轻量级识别：判断chunk是否可能是格式范本
    
    识别规则：
    1. 标题/内容包含"格式"、"范本"、"模板"等关键词
    2. 内容中有大量下划线、空白框、填写说明
    3. 不是合同条款、不是评分标准原文
    
    Args:
        chunk_text: 分片文本内容
        chunk_meta: 分片元数据（可能包含标题）
    
    Returns:
        如果是潜在范本，返回 {is_potential_template: true, template_hints: [...]}
        否则返回 None
    """
    # 范本关键词
    template_keywords = [
        "格式", "范本", "模板", "样表", "样式", "参考格式",
        "标准格式", "填写说明", "附表", "附件表"
    ]
    
    # 排除关键词（不是范本）
    exclude_keywords = [
        "合同条款", "合同格式条款", "评分标准", "评分办法",
        "技术规范", "验收标准", "违约责任"
    ]
    
    # 检查标题
    title = chunk_meta.get("title", "") or chunk_meta.get("heading", "")
    
    # 1. 排除明显不是范本的
    if any(kw in title or kw in chunk_text[:300] for kw in exclude_keywords):
        return None
    
    # 2. 检查是否包含范本关键词
    has_template_keyword = any(
        kw in title or kw in chunk_text[:200] 
        for kw in template_keywords
    )
    
    # 2b. 检查是否有典型范本标题（即使没有"格式"等关键词）
    template_titles = ["授权委托书", "声明书", "报价表", "明细表", "偏离表", "自评表", "投标函"]
    has_template_title = any(t in chunk_text[:300] for t in template_titles)
    
    # 如果既没有范本关键词，也没有典型范本标题，直接返回
    if not has_template_keyword and not has_template_title:
        return None
    
    # 3. 检查内容特征（范本通常有大量下划线/空白）
    underline_count = chunk_text.count("____") + chunk_text.count("＿＿")
    bracket_count = len(re.findall(r'\[\s*\]|（\s*）', chunk_text))
    
    # 范本特征分数
    template_score = 0
    hints = []
    
    if has_template_keyword:
        template_score += 30
        hints.append("包含范本关键词")
    
    if underline_count > 5:
        template_score += 20
        hints.append(f"含{underline_count}处填写下划线")
    
    if bracket_count > 3:
        template_score += 15
        hints.append(f"含{bracket_count}处空白框")
    
    # 检查是否有"致："、"兹授权"等范本起始词
    template_starters = ["致：", "兹授权", "本人", "我单位", "投标人名称"]
    if any(starter in chunk_text[:100] for starter in template_starters):
        template_score += 25
        hints.append("含范本起始标识")
    
    # 检查是否有表格结构标识
    if "┌" in chunk_text or "├" in chunk_text or re.search(r'\|\s*\|', chunk_text):
        template_score += 10
        hints.append("含表格结构")
    
    # 检查"格式"关键词出现频率（高频出现通常是格式范本章节）
    format_count = chunk_text.count("格式")
    if format_count >= 3:
        template_score += 15
        hints.append(f"\"格式\"高频出现({format_count}次)")
    
    # 检查是否有"填写"、"签字"、"盖章"等范本特征词
    fill_keywords = ["填写", "签字", "盖章", "（签章）", "（盖章）", "年 月 日", "年月日"]
    fill_keyword_count = sum(1 for kw in fill_keywords if kw in chunk_text)
    if fill_keyword_count >= 3:
        template_score += 15
        hints.append(f"含{fill_keyword_count}个填写特征词")
    
    # 检查是否有"授权委托书"、"磋商声明"等典型范本标题（已在上面检查过）
    if has_template_title:
        template_score += 45  # 大幅提高分数，因为标题是最强特征（单独就能通过阈值）
        hints.append("含典型范本标题")
    
    # 判断阈值：40分以上认为是潜在范本
    if template_score >= 40:
        return {
            "is_potential_template": True,
            "template_score": template_score,
            "template_hints": hints,
        }
    
    return None


# ==================== 阶段2：LLM精确匹配 ====================

async def match_templates_to_nodes(
    nodes: List[Dict[str, Any]],
    project_id: str,
    pool: Any,
    llm: Any,
    model_id: Optional[str] = None,
    enable_matching: bool = True,
) -> Dict[str, Any]:
    """
    目录生成后，使用LLM精确匹配格式范本到节点
    
    流程：
    1. 从数据库查询标记为potential_template的chunks
    2. 遍历L2/L3节点，为每个节点寻找匹配的范本
    3. 批量调用LLM判断匹配关系
    4. 返回匹配结果
    
    Args:
        nodes: 目录节点列表
        project_id: 项目ID
        pool: 数据库连接池
        llm: LLM调用器
        model_id: 模型ID
        enable_matching: 是否启用匹配（默认True）
    
    Returns:
        {
            "matches": [
                {
                    "node_title": "投标函及投标函附录",
                    "node_id": "xxx",
                    "template_chunk_id": "chunk_123",
                    "template_text": "...",
                    "confidence": 0.95
                },
                ...
            ],
            "stats": {...}
        }
    """
    if not enable_matching:
        logger.info("[TemplateMatcher] Matching disabled")
        return {"matches": [], "stats": {"enabled": False}}
    
    logger.info(f"[TemplateMatcher] Starting template matching for project={project_id}")
    
    try:
        # 1. 查询潜在范本chunks
        template_chunks = await _load_potential_templates(pool, project_id)
        
        if not template_chunks:
            logger.info("[TemplateMatcher] No potential template chunks found")
            return {"matches": [], "stats": {"no_templates": True}}
        
        logger.info(f"[TemplateMatcher] Found {len(template_chunks)} potential template chunks")
        
        # 2. 筛选需要匹配的节点（L2/L3）
        target_nodes = [
            node for node in nodes 
            if node.get("level") in [2, 3] and not node.get("notes")  # 没有正文的节点
        ]
        
        if not target_nodes:
            logger.info("[TemplateMatcher] No target nodes to match")
            return {"matches": [], "stats": {"no_target_nodes": True}}
        
        logger.info(f"[TemplateMatcher] {len(target_nodes)} nodes need template matching")
        
        # 3. 批量调用LLM匹配
        matches = await _batch_match_with_llm(
            target_nodes=target_nodes,
            template_chunks=template_chunks,
            llm=llm,
            model_id=model_id,
        )
        
        logger.info(
            f"[TemplateMatcher] Matching complete - "
            f"{len(matches)} matches found (confidence ≥ 0.9)"
        )
        
        return {
            "matches": matches,
            "stats": {
                "enabled": True,
                "template_chunks_count": len(template_chunks),
                "target_nodes_count": len(target_nodes),
                "matches_count": len(matches),
            }
        }
        
    except Exception as e:
        logger.error(f"[TemplateMatcher] Matching failed: {e}", exc_info=True)
        return {"matches": [], "stats": {"error": str(e)}}


async def _load_potential_templates(pool: Any, project_id: str) -> List[Dict[str, Any]]:
    """从数据库加载标记为potential_template的chunks"""
    try:
        # 1. 获取项目的招标文档doc_version_id
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # 查找招标文档
                cur.execute("""
                    SELECT dv.id
                    FROM tender_project_documents tpd
                    JOIN documents d ON d.id = tpd.kb_doc_id
                    JOIN document_versions dv ON dv.document_id = d.id
                    WHERE tpd.project_id = %s AND tpd.doc_role = 'tender'
                    ORDER BY dv.created_at DESC
                    LIMIT 1
                """, [project_id])
                
                doc_version_row = cur.fetchone()
                if not doc_version_row:
                    logger.warning(f"[TemplateMatcher] No tender document found for project={project_id}")
                    return []
                
                doc_version_id = doc_version_row[0]
                
                # 2. 查询标记为potential_template的chunks
                cur.execute("""
                    SELECT id, content_text, meta_json
                    FROM doc_segments
                    WHERE doc_version_id = %s
                    AND meta_json->>'is_potential_template' = 'true'
                    ORDER BY (meta_json->>'template_score')::int DESC
                    LIMIT 30
                """, [doc_version_id])
                
                rows = cur.fetchall()
                
                templates = []
                for row in rows:
                    templates.append({
                        "chunk_id": row[0],
                        "text": row[1],
                        "meta": row[2] or {},
                    })
                
                return templates
                
    except Exception as e:
        logger.error(f"[TemplateMatcher] Failed to load templates: {e}")
        return []


async def _batch_match_with_llm(
    target_nodes: List[Dict[str, Any]],
    template_chunks: List[Dict[str, Any]],
    llm: Any,
    model_id: Optional[str],
) -> List[Dict[str, Any]]:
    """
    批量调用LLM匹配节点与范本
    
    策略：每批处理5个节点，避免单次Token过多
    """
    matches = []
    batch_size = 5
    
    for i in range(0, len(target_nodes), batch_size):
        batch = target_nodes[i:i + batch_size]
        logger.info(f"[TemplateMatcher] Processing batch {i//batch_size + 1} ({len(batch)} nodes)")
        
        batch_matches = await _match_batch(batch, template_chunks, llm, model_id)
        matches.extend(batch_matches)
    
    return matches


async def _match_batch(
    nodes_batch: List[Dict[str, Any]],
    template_chunks: List[Dict[str, Any]],
    llm: Any,
    model_id: Optional[str],
) -> List[Dict[str, Any]]:
    """单批次LLM匹配"""
    
    # 构建Prompt
    prompt = _build_match_prompt(nodes_batch, template_chunks)
    
    try:
        messages = [{"role": "user", "content": prompt}]
        
        llm_response = await llm.achat(
            messages=messages,
            model_id=model_id,
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=2000,
        )
        
        llm_output = llm_response.get("choices", [{}])[0].get("message", {}).get("content")
        if not llm_output:
            logger.warning("[TemplateMatcher] LLM returned empty content")
            return []
        
        result_data = json.loads(llm_output)
        raw_matches = result_data.get("matches", [])
        
        # 处理结果，关联回原始数据
        matches = []
        for match in raw_matches:
            if match.get("confidence", 0) < 0.9:  # 置信度阈值（提高到90%）
                continue
            
            node_idx = match.get("node_index", 0) - 1
            template_idx = match.get("template_index", 0) - 1
            
            if 0 <= node_idx < len(nodes_batch) and 0 <= template_idx < len(template_chunks):
                node = nodes_batch[node_idx]
                template = template_chunks[template_idx]
                
                matches.append({
                    "node_title": node.get("title"),
                    "node_level": node.get("level"),
                    "node_order_no": node.get("order_no"),
                    "template_chunk_id": template["chunk_id"],
                    "template_text": template["text"],
                    "template_hints": template["meta"].get("template_hints", []),
                    "confidence": match.get("confidence"),
                    "reason": match.get("reason", ""),
                })
        
        return matches
        
    except Exception as e:
        logger.error(f"[TemplateMatcher] LLM matching failed: {e}", exc_info=True)
        return []


def _build_match_prompt(
    nodes_batch: List[Dict[str, Any]],
    template_chunks: List[Dict[str, Any]],
) -> str:
    """构建LLM匹配Prompt"""
    
    # 节点描述
    nodes_desc = []
    for idx, node in enumerate(nodes_batch, 1):
        nodes_desc.append(f"""
节点{idx}：
  标题：{node.get('title', '')}
  层级：L{node.get('level', 0)}
  所属卷册：{node.get('volume', '')}
""")
    
    # 范本描述（只显示前100字）
    templates_desc = []
    for idx, template in enumerate(template_chunks[:10], 1):  # 最多10个候选
        text_preview = template['text'][:150].replace('\n', ' ')
        hints = template['meta'].get('template_hints', [])
        templates_desc.append(f"""
范本{idx}：
  内容预览：{text_preview}...
  识别特征：{', '.join(hints) if hints else '无'}
""")
    
    prompt = f"""你是招投标文件分析专家。请为以下{len(nodes_batch)}个目录节点匹配合适的格式范本。

【目录节点】
{"".join(nodes_desc)}

【候选格式范本】（共{len(template_chunks)}个，仅显示前10个）
{"".join(templates_desc)}

匹配规则：
1. ✅ 应该匹配：节点标题与范本内容高度相关
   - 例如：节点"投标函及投标函附录" ↔ 范本"致：××× 我单位..."
   - 例如：节点"授权委托书" ↔ 范本"兹授权 xxx 为我单位合法代理人..."

2. ❌ 不应匹配：语义不相关、范本类型不对
   - 例如：节点"技术方案" ✗ 范本"投标函格式"

3. 置信度判断：
   - 0.9-1.0：标题完全匹配，内容高度相关
   - 0.7-0.9：标题相似，内容基本符合
   - < 0.7：不确定，不应匹配

返回JSON格式：
{{
  "matches": [
    {{
      "node_index": 1,
      "template_index": 2,
      "confidence": 0.95,
      "reason": "节点'投标函及投标函附录'与范本2的投标函格式完全匹配"
    }},
    // ... 其他匹配
  ]
}}

注意：
- 一个节点最多匹配1个范本
- 只返回confidence >= 0.9的匹配（高置信度）
- 如果没有合适的匹配，matches可以为空数组
"""
    
    return prompt


# ==================== 阶段3：自动填充节点正文 ====================

async def auto_fill_template_bodies(
    matches: List[Dict[str, Any]],
    project_id: str,
    pool: Any,
) -> Dict[str, Any]:
    """
    根据匹配结果，自动填充节点正文
    
    Args:
        matches: 匹配结果列表
        project_id: 项目ID
        pool: 数据库连接池
    
    Returns:
        {
            "filled_count": 5,
            "filled_nodes": ["投标函", "授权书", ...],
            "errors": []
        }
    """
    logger.info(f"[TemplateMatcher] Auto-filling {len(matches)} matched templates")
    
    filled_count = 0
    filled_nodes = []
    errors = []
    
    try:
        # 获取目录version_id
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id FROM tender_directory_versions
                    WHERE project_id = %s AND is_active = TRUE
                    ORDER BY created_at DESC
                    LIMIT 1
                """, [project_id])
                
                version_row = cur.fetchone()
                if not version_row:
                    logger.warning(f"[TemplateMatcher] No active directory version for project={project_id}")
                    return {"filled_count": 0, "filled_nodes": [], "errors": ["无活跃目录版本"]}
                
                version_id = version_row[0]
        
        # 批量填充
        with pool.connection() as conn:
            with conn.cursor() as cur:
                for match in matches:
                    try:
                        node_title = match["node_title"]
                        template_text = match["template_text"]
                        chunk_id = match["template_chunk_id"]
                        
                        # 更新节点的body_content和source_chunk_ids
                        cur.execute("""
                            UPDATE tender_directory_nodes
                            SET 
                                body_content = %s,
                                source_chunk_ids = source_chunk_ids || %s::text,
                                updated_at = NOW()
                            WHERE version_id = %s 
                            AND title = %s
                            AND project_id = %s
                        """, [
                            template_text,
                            chunk_id,
                            version_id,
                            node_title,
                            project_id
                        ])
                        
                        if cur.rowcount > 0:
                            filled_count += 1
                            filled_nodes.append(node_title)
                            logger.info(f"[TemplateMatcher] Filled template for '{node_title}'")
                        
                    except Exception as e:
                        error_msg = f"填充'{match['node_title']}'失败: {str(e)}"
                        errors.append(error_msg)
                        logger.error(f"[TemplateMatcher] {error_msg}")
                
                conn.commit()
        
        logger.info(
            f"[TemplateMatcher] Auto-fill complete - "
            f"{filled_count}/{len(matches)} nodes filled"
        )
        
        return {
            "filled_count": filled_count,
            "filled_nodes": filled_nodes,
            "errors": errors,
        }
        
    except Exception as e:
        logger.error(f"[TemplateMatcher] Auto-fill failed: {e}", exc_info=True)
        return {
            "filled_count": 0,
            "filled_nodes": [],
            "errors": [str(e)],
        }

