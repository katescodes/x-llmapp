"""
目录规则细化模块 (Rule-based Refinement)

在已生成的目录基础上，利用 tender_requirements 表数据，
对特定节点（评分标准、资格审查等）进行L3/L4细化展开。

特点：
- 纯规则驱动，无LLM调用
- 快速稳定，确定性强
- 可选启用，失败不影响基础目录
"""
import logging
from typing import Any, Dict, List, Optional, Set
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


def refine_directory_from_requirements(
    project_id: str,
    pool: Any,
    nodes: List[Dict[str, Any]],
    enable_refinement: bool = True,
) -> Dict[str, Any]:
    """
    基于招标要求对目录进行规则细化
    
    Args:
        project_id: 项目ID
        pool: 数据库连接池
        nodes: 已生成的目录节点列表
        enable_refinement: 是否启用细化（默认True，可用于回退）
    
    Returns:
        {
            "refined_nodes": [...],  # 细化后的节点列表
            "added_count": 5,  # 新增节点数
            "refined_parents": ["评分标准响应表", ...],  # 被细化的父节点
            "stats": {...}
        }
    """
    if not enable_refinement:
        logger.info(f"[Refinement] Disabled by parameter, skip refinement")
        return {
            "refined_nodes": nodes,
            "added_count": 0,
            "refined_parents": [],
            "stats": {"enabled": False}
        }
    
    logger.info(f"[Refinement] Starting rule-based refinement for project={project_id}")
    
    try:
        # 1. 查询招标要求数据
        requirements = _load_tender_requirements(pool, project_id)
        if not requirements:
            logger.info(f"[Refinement] No tender_requirements found, skip refinement")
            return {
                "refined_nodes": nodes,
                "added_count": 0,
                "refined_parents": [],
                "stats": {"no_requirements": True}
            }
        
        logger.info(f"[Refinement] Loaded {len(requirements)} requirements")
        
        # 2. 按维度分组
        requirements_by_dimension = _group_by_dimension(requirements)
        
        # 3. 识别可细化的节点
        refinable_nodes = _identify_refinable_nodes(nodes)
        if not refinable_nodes:
            logger.info(f"[Refinement] No refinable nodes found, skip refinement")
            return {
                "refined_nodes": nodes,
                "added_count": 0,
                "refined_parents": [],
                "stats": {"no_refinable_nodes": True}
            }
        
        logger.info(f"[Refinement] Found {len(refinable_nodes)} refinable nodes")
        
        # 4. 为每个可细化节点生成子节点
        all_new_nodes = []
        refined_parents = []
        existing_titles = {node["title"] for node in nodes}
        
        for parent_node in refinable_nodes:
            dimension = parent_node["matched_dimension"]
            reqs = requirements_by_dimension.get(dimension, [])
            
            if not reqs:
                continue
            
            new_child_nodes = _generate_child_nodes(
                parent_node=parent_node,
                requirements=reqs,
                existing_titles=existing_titles,
                project_id=project_id,
            )
            
            if new_child_nodes:
                all_new_nodes.extend(new_child_nodes)
                refined_parents.append(parent_node["title"])
                # 更新已存在的标题集合（避免重复）
                existing_titles.update(child["title"] for child in new_child_nodes)
                
                logger.info(
                    f"[Refinement] Added {len(new_child_nodes)} children "
                    f"to '{parent_node['title']}' (dimension={dimension})"
                )
        
        # 5. 合并并重新排序
        refined_nodes = _merge_and_reorder(nodes, all_new_nodes)
        
        logger.info(
            f"[Refinement] Done - added {len(all_new_nodes)} nodes, "
            f"total={len(refined_nodes)}, refined_parents={len(refined_parents)}"
        )
        
        return {
            "refined_nodes": refined_nodes,
            "added_count": len(all_new_nodes),
            "refined_parents": refined_parents,
            "stats": {
                "enabled": True,
                "total_requirements": len(requirements),
                "refinable_nodes": len(refinable_nodes),
                "new_nodes": len(all_new_nodes),
            }
        }
        
    except Exception as e:
        logger.error(f"[Refinement] Failed (non-fatal): {e}", exc_info=True)
        # 失败时返回原始节点，不影响基础功能
        return {
            "refined_nodes": nodes,
            "added_count": 0,
            "refined_parents": [],
            "stats": {"error": str(e)}
        }


def _load_tender_requirements(pool: Any, project_id: str) -> List[Dict[str, Any]]:
    """从数据库加载招标要求"""
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                sql = """
                    SELECT id, requirement_id, dimension, req_type, requirement_text,
                           is_hard, allow_deviation, eval_method, must_reject,
                           evidence_chunk_ids, meta_json
                    FROM tender_requirements
                    WHERE project_id = %s
                    ORDER BY dimension, requirement_id
                """
                cur.execute(sql, [project_id])
                rows = cur.fetchall()
                return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"[Refinement] Failed to load requirements: {e}")
        return []


def _group_by_dimension(requirements: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """按维度分组"""
    grouped = {}
    for req in requirements:
        dimension = req.get("dimension", "other")
        if dimension not in grouped:
            grouped[dimension] = []
        grouped[dimension].append(req)
    return grouped


def _identify_refinable_nodes(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    识别可细化的节点（基于关键词匹配）
    
    匹配规则：
    - "评分标准"、"评分办法"、"评分细则" → scoring
    - "资格审查"、"资格证明"、"资格条件" → qualification
    - "商务条款"、"商务响应"、"商务要求" → business
    - "技术要求"、"技术规格"、"技术参数" → technical
    """
    refinable = []
    
    # 关键词映射到维度
    keyword_map = {
        "scoring": ["评分标准", "评分办法", "评分细则", "评分表", "评分项"],
        "qualification": ["资格审查", "资格证明", "资格条件", "资格要求"],
        "business": ["商务条款", "商务响应", "商务要求", "商务部分"],
        "technical": ["技术要求", "技术规格", "技术参数", "技术指标"],
    }
    
    for node in nodes:
        title = node.get("title", "")
        
        # 只细化L2和L3节点（避免过深）
        if node.get("level") not in [2, 3]:
            continue
        
        # 匹配关键词
        for dimension, keywords in keyword_map.items():
            if any(kw in title for kw in keywords):
                refinable.append({
                    **node,
                    "matched_dimension": dimension
                })
                break
    
    return refinable


def _generate_child_nodes(
    parent_node: Dict[str, Any],
    requirements: List[Dict[str, Any]],
    existing_titles: Set[str],
    project_id: str,
) -> List[Dict[str, Any]]:
    """为父节点生成子节点"""
    child_nodes = []
    child_level = parent_node["level"] + 1
    
    # 限制最大层级（避免过深）
    if child_level > 4:
        logger.debug(f"[Refinement] Skip refinement for '{parent_node['title']}' (level too deep)")
        return []
    
    base_order_no = parent_node.get("order_no", 0) + 1
    
    for idx, req in enumerate(requirements):
        # 构建节点标题
        req_text = req.get("requirement_text", "")
        if not req_text:
            continue
        
        # 提取分值（如果是评分项）
        score = _extract_score(req)
        if score and parent_node["matched_dimension"] == "scoring":
            # 格式：技术方案（20分）
            title = f"{_truncate_text(req_text, 30)}（{score}分）"
        else:
            # 格式：营业执照副本
            title = _truncate_text(req_text, 40)
        
        # 去重：检查是否已存在相似标题
        if _is_duplicate_title(title, existing_titles):
            logger.debug(f"[Refinement] Skip duplicate title: {title}")
            continue
        
        # 构建子节点
        child_nodes.append({
            "title": title,
            "level": child_level,
            "order_no": base_order_no + idx,
            "parent_ref": parent_node["title"],
            "required": req.get("is_hard", True),
            "volume": parent_node.get("volume", ""),
            "notes": req_text if len(req_text) > 40 else "",  # 完整文本放在notes
            "evidence_chunk_ids": req.get("evidence_chunk_ids", []),
            "source": "refinement_rule",
            "meta": {
                "requirement_id": req.get("requirement_id"),
                "dimension": req.get("dimension"),
                "req_type": req.get("req_type"),
                "score": score,
            }
        })
    
    return child_nodes


def _extract_score(req: Dict[str, Any]) -> Optional[float]:
    """尝试从requirement_text或meta_json中提取分值"""
    import re
    
    # 1. 从 meta_json 提取
    meta = req.get("meta_json", {})
    if isinstance(meta, dict):
        score = meta.get("score") or meta.get("max_score")
        if score:
            try:
                return float(score)
            except:
                pass
    
    # 2. 从 requirement_text 正则提取
    text = req.get("requirement_text", "")
    patterns = [
        r'(\d+(?:\.\d+)?)\s*分',
        r'满分\s*(\d+(?:\.\d+)?)',
        r'\((\d+(?:\.\d+)?)\s*分\)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return float(match.group(1))
            except:
                pass
    
    return None


def _truncate_text(text: str, max_len: int) -> str:
    """截断文本，保留完整语义"""
    if len(text) <= max_len:
        return text
    
    # 尝试在标点符号处截断
    punctuations = ['。', '，', '；', '：', '、']
    for i in range(max_len - 1, max(0, max_len - 10), -1):
        if text[i] in punctuations:
            return text[:i]
    
    # 没有标点，直接截断
    return text[:max_len - 3] + "..."


def _is_duplicate_title(title: str, existing_titles: Set[str], threshold: float = 0.85) -> bool:
    """检查标题是否重复（基于相似度）"""
    for existing in existing_titles:
        similarity = SequenceMatcher(None, title, existing).ratio()
        if similarity > threshold:
            return True
    return False


def _merge_and_reorder(
    original_nodes: List[Dict[str, Any]],
    new_nodes: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    合并原始节点和新节点，并重新排序
    
    策略：
    1. 将新节点插入到对应父节点的后面
    2. 按 (level, order_no) 排序
    3. 重新分配 order_no（保证连续）
    """
    # 1. 构建父节点索引
    parent_map = {}
    for i, node in enumerate(original_nodes):
        parent_map[node["title"]] = i
    
    # 2. 插入新节点
    merged = original_nodes.copy()
    for new_node in new_nodes:
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
    
    # 3. 排序（按 level, order_no）
    merged.sort(key=lambda n: (n.get("level", 99), n.get("order_no", 0)))
    
    # 4. 重新分配 order_no
    for i, node in enumerate(merged):
        node["order_no"] = i + 1
    
    return merged

