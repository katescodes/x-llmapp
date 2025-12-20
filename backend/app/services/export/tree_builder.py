"""
目录树构建器
从扁平的数据库记录构建树形结构，并自动生成 numbering
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DirNode:
    """目录节点"""
    id: str
    parent_id: Optional[str]
    order_no: int
    level: int
    numbering: Optional[str]
    title: str
    is_required: bool
    source: str
    meta_json: Dict[str, Any]
    evidence_chunk_ids: List[str] = field(default_factory=list)
    children: List["DirNode"] = field(default_factory=list)
    
    # 可选：用于存储语义目录的 summary（从 semantic_outline_nodes 回填）
    summary: Optional[str] = None


def build_tree(rows: List[Dict[str, Any]]) -> List[DirNode]:
    """
    从扁平的数据库记录构建树形结构
    
    Args:
        rows: 从 tender_directory_nodes 查询的记录列表
        
    Returns:
        根节点列表
    """
    nodes: Dict[str, DirNode] = {}
    
    # 1. 创建所有节点
    for r in rows:
        meta = r.get("meta_json") or {}
        if isinstance(meta, str):
            import json
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        
        evidence = r.get("evidence_chunk_ids") or []
        if isinstance(evidence, str):
            import json
            try:
                evidence = json.loads(evidence)
            except Exception:
                evidence = []
        
        nodes[r["id"]] = DirNode(
            id=r["id"],
            parent_id=r.get("parent_id"),
            order_no=int(r.get("order_no") or 0),
            level=int(r.get("level") or 1),
            numbering=r.get("numbering"),
            title=r["title"],
            is_required=bool(r.get("is_required", True)),
            source=r.get("source", "tender"),
            meta_json=meta,
            evidence_chunk_ids=evidence if isinstance(evidence, list) else [],
        )
    
    # 2. 构建父子关系
    roots: List[DirNode] = []
    for n in nodes.values():
        if n.parent_id and n.parent_id in nodes:
            nodes[n.parent_id].children.append(n)
        else:
            roots.append(n)
    
    # 3. 递归排序
    def sort_rec(node: DirNode):
        node.children.sort(key=lambda c: (c.order_no, c.title))
        for ch in node.children:
            sort_rec(ch)
    
    roots.sort(key=lambda c: (c.order_no, c.title))
    for r in roots:
        sort_rec(r)
    
    return roots


def fill_numbering_if_missing(roots: List[DirNode]) -> None:
    """
    如果节点的 numbering 缺失，自动生成（基于树形结构）
    
    Args:
        roots: 根节点列表（会原地修改）
    """
    def dfs(node: DirNode, prefix: List[int]):
        # numbering 缺失则用 sibling 序号生成
        if not node.numbering or node.numbering.strip() == "":
            node.numbering = ".".join(map(str, prefix))
        
        # 递归处理子节点
        for idx, ch in enumerate(node.children, start=1):
            dfs(ch, prefix + [idx])
    
    # 处理所有根节点
    for idx, r in enumerate(roots, start=1):
        dfs(r, [idx])


def flatten_tree(roots: List[DirNode]) -> List[DirNode]:
    """
    将树形结构扁平化为列表（DFS 顺序）
    
    Args:
        roots: 根节点列表
        
    Returns:
        扁平化的节点列表
    """
    result: List[DirNode] = []
    
    def dfs(node: DirNode):
        result.append(node)
        for ch in node.children:
            dfs(ch)
    
    for r in roots:
        dfs(r)
    
    return result


def merge_semantic_summaries(
    dir_roots: List[DirNode],
    semantic_nodes: List[Dict[str, Any]],
) -> None:
    """
    将语义目录的 summary 回填到目录树节点
    
    策略：按 title 匹配（忽略大小写和空格）
    
    Args:
        dir_roots: 目录树根节点列表（会原地修改）
        semantic_nodes: 语义目录节点列表
    """
    # 构建 title -> summary 映射
    summary_map: Dict[str, str] = {}
    for sn in semantic_nodes:
        title = (sn.get("title") or "").strip().lower()
        summary = sn.get("summary") or ""
        if title and summary:
            summary_map[title] = summary
    
    # DFS 回填
    def dfs(node: DirNode):
        title_key = node.title.strip().lower()
        if title_key in summary_map and not node.summary:
            node.summary = summary_map[title_key]
        for ch in node.children:
            dfs(ch)
    
    for r in dir_roots:
        dfs(r)

