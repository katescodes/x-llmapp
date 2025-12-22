"""
文档导出服务
提供基于模板的 Word 文档导出功能
"""
from __future__ import annotations

import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.services.dao.tender_dao import TenderDAO
from app.services.export.tree_builder import (
    DirNode,
    build_tree,
    fill_numbering_if_missing,
    merge_semantic_summaries,
)
from app.services.export.docx_template_loader import (
    PageVariant,
    extract_section_prototypes,
)
from app.services.export.docx_exporter import (
    render_directory_tree_to_docx,
    render_simple_outline_to_docx,
    build_project_context_string,
)
from app.services.export.style_map import (
    get_style_config_from_template,
    load_heading_style_map,
    load_normal_style,
)
from app.services.export.summary_backfill import (
    backfill_directory_meta_summary,
    get_backfill_statistics,
)

logger = logging.getLogger(__name__)


class ExportService:
    """文档导出服务"""
    
    def __init__(self, dao: TenderDAO):
        """
        初始化导出服务
        
        Args:
            dao: TenderDAO 实例
        """
        self.dao = dao
    
    async def export_project_to_docx(
        self,
        project_id: str,
        *,
        format_template_id: Optional[str] = None,
        include_toc: bool = True,
        prefix_numbering: bool = False,
        merge_semantic_summary: bool = False,
        output_dir: Optional[str] = None,
        auto_generate_content: bool = False,
        auto_write_cfg: Optional[Any] = None,
        project_context: str = "",
        model_id: Optional[str] = None,
    ) -> str:
        """
        导出项目为 Word 文档
        
        Args:
            project_id: 项目 ID
            format_template_id: 格式模板 ID（可选，优先从目录节点 meta_json 获取）
            include_toc: 是否包含目录
            prefix_numbering: 是否在标题前添加编号
            merge_semantic_summary: 是否合并语义目录的 summary
            output_dir: 输出目录（可选，默认使用临时目录）
            auto_generate_content: 是否自动生成内容（当 summary 为空时）
            auto_write_cfg: 自动写作配置
            project_context: 项目上下文信息（用于自动生成内容）
            model_id: LLM模型ID（用于自动生成内容）
            
        Returns:
            输出文件路径
        """
        logger.info(f"开始导出项目: project_id={project_id}, template={format_template_id}")
        
        # 1. 加载目录树
        rows = self.dao.list_directory(project_id)
        if not rows:
            raise ValueError(f"项目 {project_id} 没有目录数据")
        
        roots = build_tree(rows)
        fill_numbering_if_missing(roots)
        
        logger.info(f"已加载目录树: {len(rows)} 个节点, {len(roots)} 个根节点")
        
        # 2. 确定 format_template_id（优先从根节点 meta_json 获取）
        if not format_template_id:
            format_template_id = self._find_format_template_id(roots)
        
        # 3. 如果启用了自动生成但未提供 project_context，则自动构建
        if auto_generate_content and not project_context:
            try:
                project = self.dao.get_project(project_id)
                if project:
                    project_context = build_project_context_string(project)
                    logger.info(f"自动构建项目上下文: {len(project_context)} 字符")
            except Exception as e:
                logger.warning(f"构建项目上下文失败: {e}")
                project_context = ""
        
        # 4. 回填语义目录的 summary（写数据库，然后重新加载）
        if merge_semantic_summary:
            backfill_stats = self._backfill_semantic_summaries(project_id)
            logger.info(f"Summary 回填统计: {backfill_stats}")
            
            # 重新加载目录树（已包含回填的 summary）
            rows = self.dao.list_directory(project_id)
            roots = build_tree(rows)
            fill_numbering_if_missing(roots)
        
        # 5. 准备输出路径
        if not output_dir:
            output_dir = tempfile.gettempdir()
        
        output_path = os.path.join(
            output_dir,
            f"project_{project_id}_{uuid.uuid4().hex[:8]}.docx"
        )
        
        # 6. 渲染文档
        if format_template_id:
            # 使用模板母版
            await self._export_with_template(
                roots=roots,
                format_template_id=format_template_id,
                output_path=output_path,
                include_toc=include_toc,
                prefix_numbering=prefix_numbering,
                project_id=project_id,
                auto_generate_content=auto_generate_content,
                auto_write_cfg=auto_write_cfg,
                project_context=project_context,
                model_id=model_id,
            )
        else:
            # 简单导出（不使用模板）
            logger.warning("未找到格式模板，使用简单导出")
            render_simple_outline_to_docx(
                output_path=output_path,
                roots=roots,
                include_toc=include_toc,
                prefix_numbering_in_text=prefix_numbering,
            )
        
        logger.info(f"导出完成: {output_path}")
        return output_path
    
    def _find_format_template_id(self, roots: List[DirNode]) -> Optional[str]:
        """从根节点的 meta_json 中查找 format_template_id"""
        for root in roots:
            meta = root.meta_json or {}
            template_id = meta.get("format_template_id")
            if template_id:
                logger.info(f"从根节点获取 format_template_id: {template_id}")
                return template_id
        return None
    
    def _backfill_semantic_summaries(
        self,
        project_id: str,
        min_title_similarity: float = 0.86
    ) -> Dict[str, Any]:
        """
        回填语义目录的 summary 到项目目录节点（写数据库）
        
        Args:
            project_id: 项目 ID
            min_title_similarity: title 相似度阈值
            
        Returns:
            回填统计信息
        """
        try:
            # 1. 获取目录节点
            directory_rows = self.dao.list_directory(project_id)
            if not directory_rows:
                return {"error": "目录为空"}
            
            # 2. 获取最新的语义目录节点
            semantic_rows = self.dao.get_latest_semantic_outline_nodes(project_id)
            if not semantic_rows:
                return {"error": "语义目录为空"}
            
            logger.info(
                f"开始回填 summary: directory={len(directory_rows)}, "
                f"semantic={len(semantic_rows)}"
            )
            
            # 3. 计算需要更新的节点
            updates = backfill_directory_meta_summary(
                directory_rows=directory_rows,
                semantic_rows=semantic_rows,
                min_title_similarity=min_title_similarity,
                force_overwrite=False,
            )
            
            if not updates:
                logger.info("没有需要回填的节点")
                return {"total_updated": 0, "message": "所有节点已有 summary"}
            
            # 4. 批量更新数据库
            count = self.dao.batch_update_node_meta_json(updates)
            
            # 5. 统计
            stats = get_backfill_statistics(updates)
            stats["database_updated"] = count
            
            logger.info(f"回填完成: {stats}")
            
            return stats
        
        except Exception as e:
            logger.error(f"回填 summary 失败: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def _export_with_template(
        self,
        roots: List[DirNode],
        format_template_id: str,
        output_path: str,
        include_toc: bool,
        prefix_numbering: bool,
        project_id: str,
        auto_generate_content: bool = False,
        auto_write_cfg: Optional[Any] = None,
        project_context: str = "",
        model_id: Optional[str] = None,
    ) -> None:
        """使用模板母版导出"""
        # 1. 加载模板信息
        template_info = self.dao.get_format_template(format_template_id)
        if not template_info:
            raise ValueError(f"格式模板不存在: {format_template_id}")
        
        # 2. 获取模板文件路径
        template_path = template_info.get("template_storage_path")
        if not template_path or not os.path.exists(template_path):
            raise FileNotFoundError(
                f"模板文件不存在: {template_path} (template_id={format_template_id})"
            )
        
        logger.info(f"使用模板: {template_path}")
        
        # 3. 提取 section 原型（用于横版/A3 等布局）
        try:
            section_prototypes = extract_section_prototypes(template_path)
            logger.info(f"提取到 {len(section_prototypes)} 个 section 原型")
        except Exception as e:
            logger.warning(f"提取 section 原型失败: {e}，使用空字典")
            section_prototypes = {}
        
        # 4. 准备样式配置
        heading_style_map, normal_style_name = self._get_style_config(template_info)
        
        # 5. 提取 applyAssets（LLM 分析的保留/删除计划）
        apply_assets = None
        analysis_json = template_info.get("analysis_json")
        if analysis_json and isinstance(analysis_json, dict):
            apply_assets = analysis_json.get("applyAssets")
            if apply_assets:
                logger.info(f"从 analysis_json 提取 applyAssets: "
                           f"anchors={len(apply_assets.get('anchors', []))}, "
                           f"keep={len(apply_assets.get('keepPlan', {}).get('keepBlockIds', []))}, "
                           f"delete={len(apply_assets.get('keepPlan', {}).get('deleteBlockIds', []))}")
        
        # 6. 准备节正文插入回调
        def insert_body(node: DirNode, doc):
            """插入节正文内容"""
            self._insert_section_body(project_id, node, doc)
        
        # 7. 渲染文档
        await render_directory_tree_to_docx(
            template_path=template_path,
            output_path=output_path,
            roots=roots,
            section_prototypes=section_prototypes,
            include_toc=include_toc,
            prefix_numbering_in_text=prefix_numbering,
            heading_style_map=heading_style_map,
            normal_style_name=normal_style_name,
            apply_assets=apply_assets,  # 新增：传递 LLM 分析结果
            insert_section_body=insert_body,
            auto_generate_content=auto_generate_content,
            auto_write_cfg=auto_write_cfg,
            project_context=project_context,
            model_id=model_id,
        )
    
    def _get_style_config(
        self,
        template_info: Dict[str, Any]
    ) -> Tuple[Optional[Dict[int, str]], Optional[str]]:
        """
        从模板信息中提取样式配置
        
        优先级：
        1. style_config_json / style_config (旧字段，手动配置)
        2. analysis_json.roleMapping (新字段，自动分析)
        
        Args:
            template_info: 模板信息字典
            
        Returns:
            元组 (heading_style_map, normal_style_name)
        """
        try:
            # 方案1：优先从 style_config_json 读取（旧方案，兼容性）
            style_config = get_style_config_from_template(template_info)
            
            if style_config:
                # 加载标题样式映射
                heading_style_map = load_heading_style_map(style_config)
                
                # 加载正文样式
                normal_style = load_normal_style(style_config)
                
                if heading_style_map or normal_style:
                    logger.info(
                        f"从 style_config 加载样式: heading_map={heading_style_map}, "
                        f"normal_style={normal_style}"
                    )
                    return heading_style_map, normal_style
            
            # 方案2：从 analysis_json.roleMapping 读取（新方案）
            analysis_json = template_info.get("analysis_json")
            if analysis_json:
                role_mapping = analysis_json.get("roleMapping", {})
                if role_mapping:
                    # 转换格式：{"h1": "+标题1", "h2": "+标题2"} → {1: "+标题1", 2: "+标题2"}
                    heading_style_map = {}
                    for key, style_name in role_mapping.items():
                        if isinstance(key, str) and key.startswith("h") and len(key) == 2:
                            try:
                                level = int(key[1])
                                if isinstance(style_name, str) and style_name.strip():
                                    heading_style_map[level] = style_name.strip()
                            except (ValueError, IndexError):
                                pass
                    
                    # 提取正文样式
                    normal_style = role_mapping.get("body")
                    if isinstance(normal_style, str):
                        normal_style = normal_style.strip() if normal_style.strip() else None
                    else:
                        normal_style = None
                    
                    if heading_style_map or normal_style:
                        logger.info(
                            f"从 analysis_json.roleMapping 加载样式: "
                            f"heading_map={heading_style_map}, normal_style={normal_style}"
                        )
                        return heading_style_map, normal_style
            
            logger.info("模板未配置样式映射，使用默认样式")
            return None, None
        
        except Exception as e:
            logger.warning(f"解析样式配置失败: {e}", exc_info=True)
            return None, None
    
    def _insert_section_body(self, project_id: str, node: DirNode, doc) -> None:
        """
        插入节正文内容
        
        优先级：
        1. 用户编辑内容（content_html）
        2. 范本挂载（fragment_id）
        3. 占位文本（summary）
        """
        try:
            # 查询章节正文
            body = self.dao.get_section_body(project_id, node.id)
            if not body:
                return
            
            source = body.get("source")
            
            # 1. 用户编辑内容优先
            if source == "USER" and body.get("content_html"):
                from app.services.export.html_to_docx import HtmlToDocxInserter
                HtmlToDocxInserter.insert(doc, body["content_html"])
                return
            
            # 2. 范本挂载
            if source == "TEMPLATE_SAMPLE" and body.get("fragment_id"):
                fragment = self.dao.get_fragment_by_id(body["fragment_id"])
                if fragment:
                    source_file_key = fragment.get("source_file_key")
                    start_idx = fragment.get("start_body_index")
                    end_idx = fragment.get("end_body_index")
                    
                    if source_file_key and start_idx is not None and end_idx is not None:
                        from app.services.export.docx_copier import DocxBodyElementCopier
                        DocxBodyElementCopier.copy_range(
                            source_file_key,
                            start_idx,
                            end_idx,
                            doc
                        )
                        return
            
            # 3. 如果以上都没有，且节点有 summary，已经在 render_directory_tree_to_docx 中处理了
            
        except Exception as e:
            logger.error(f"插入节正文失败: node_id={node.id}, error={e}", exc_info=True)
            doc.add_paragraph(f"[正文内容加载失败: {str(e)}]")

