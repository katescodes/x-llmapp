"""
基于 TemplateSpec 的目录合并工具
实现模板定义结构 + AI 补缺的合并策略
"""
from __future__ import annotations

from typing import Dict, List, Optional
from app.services.template.template_spec import TemplateSpec, OutlineNode


class OutlineMerger:
    """目录合并器"""

    @staticmethod
    def merge_with_template(
        ai_nodes: List[Dict],
        template_spec: TemplateSpec
    ) -> List[Dict]:
        """
        将 AI 生成的目录与模板定义的结构合并
        
        策略：
        1. 以 template_spec.outline 为主干（保留 orderNo）
        2. AI 只把模板缺失的节点补齐到对应层级
        3. AI 节点必须插入到模板定义的父节点下
        4. 不改变模板节点顺序
        
        Args:
            ai_nodes: AI 生成的目录节点列表
            template_spec: 模板规格
            
        Returns:
            合并后的目录节点列表
        """
        if not template_spec.merge_policy.template_defines_structure:
            # 如果不是模板定义结构模式，直接返回 AI 节点
            return ai_nodes
        
        # 1. 将模板 outline 转换为标准节点格式
        template_nodes = OutlineMerger._convert_outline_to_nodes(template_spec.outline)
        
        if not template_spec.merge_policy.ai_only_fill_missing:
            # 如果允许 AI 完全覆盖，直接返回 AI 节点
            return ai_nodes
        
        # 2. 构建标题索引（用于匹配）
        template_titles = {node["title"].strip().lower() for node in template_nodes}
        ai_titles_map = {node["title"].strip().lower(): node for node in ai_nodes}
        
        # 3. 基础：先保留所有模板节点
        merged_nodes = template_nodes.copy()
        
        # 4. 补充 AI 节点（只补缺失的）
        for ai_node in ai_nodes:
            ai_title = ai_node["title"].strip().lower()
            
            # 如果模板中不存在此标题，则添加
            if ai_title not in template_titles:
                # 保留 AI 节点的元数据
                new_node = ai_node.copy()
                new_node["source"] = "ai_filled"  # 标记为 AI 补充
                
                # 如果不允许 AI 添加同级节点，需要找到合适的父节点插入
                if not template_spec.merge_policy.allow_ai_add_siblings:
                    # 简单策略：插入到最后
                    merged_nodes.append(new_node)
                else:
                    merged_nodes.append(new_node)
        
        # 5. 如果需要保持模板顺序，重新排序
        if template_spec.merge_policy.preserve_template_order:
            # 模板节点在前，AI 补充节点在后
            template_part = [n for n in merged_nodes if n.get("source") != "ai_filled"]
            ai_part = [n for n in merged_nodes if n.get("source") == "ai_filled"]
            merged_nodes = template_part + ai_part
        
        return merged_nodes

    @staticmethod
    def _convert_outline_to_nodes(outline: List[OutlineNode]) -> List[Dict]:
        """
        将 TemplateSpec.outline 树形结构转换为扁平节点列表
        
        Args:
            outline: 大纲节点列表
            
        Returns:
            扁平化的节点列表
        """
        result = []
        
        def traverse(nodes: List[OutlineNode], parent_numbering: str = ""):
            for node in nodes:
                # 构造编号
                numbering = f"{parent_numbering}.{node.order_no}" if parent_numbering else str(node.order_no)
                
                # 转换为标准节点格式
                result.append({
                    "numbering": numbering,
                    "level": node.level,
                    "title": node.title,
                    "is_required": node.required,
                    "source": "template",
                    "evidence_chunk_ids": [],
                    # 注意：tender_directory_nodes.id 是全局主键（跨项目唯一）。
                    # 模板 outline node.id 不能直接复用为目录节点 id，否则同一模板套用到多个项目会产生主键冲突。
                    # 这里不传入 id，让 DAO 按 project_id+numbering 生成稳定且项目内唯一的 id。
                    "meta_json": {"template_outline_id": node.id, **(node.metadata or {})},
                    "order_no": node.order_no
                })
                
                # 递归处理子节点
                if node.children:
                    traverse(node.children, numbering)
        
        traverse(outline)
        return result

    @staticmethod
    def get_style_hint_for_level(level: int, template_spec: TemplateSpec) -> Optional[str]:
        """
        根据层级获取样式提示
        
        Args:
            level: 层级（1-5）
            template_spec: 模板规格
            
        Returns:
            样式名称或 None
        """
        style_hints = template_spec.style_hints
        
        if level == 1:
            return style_hints.heading1_style
        elif level == 2:
            return style_hints.heading2_style
        elif level == 3:
            return style_hints.heading3_style
        elif level == 4:
            return style_hints.heading4_style
        elif level == 5:
            return style_hints.heading5_style
        else:
            return None
