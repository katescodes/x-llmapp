"""
格式模板 Work 编排层
负责格式模板的业务编排：CRUD、分析、解析、预览、套用到目录
只做编排，底层能力调用现有 services 和 DAO
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from psycopg_pool import ConnectionPool

from app.services.dao.tender_dao import TenderDAO
from .types import (
    ApplyFormatTemplateResult,
    FormatTemplateAnalysisSummary,
    FormatTemplateCreateResult,
    FormatTemplateOut,
    FormatTemplateParseSummary,
    FormatTemplateSpecOut,
    FormatTemplateUpdateReq,
    PreviewResult,
    ProjectPreviewResult,
)

logger = logging.getLogger(__name__)


class FormatTemplatesWork:
    """
    格式模板 Work 编排层
    
    职责：
    1. 编排格式模板的 CRUD 操作
    2. 编排模板分析流程（样式解析 + Blocks提取 + 可选LLM分析）
    3. 编排模板预览生成
    4. 编排套用格式到项目目录
    
    不做：
    1. 直接操作数据库（委托给 DAO）
    2. 实现底层算法（委托给 services）
    """
    
    def __init__(
        self,
        pool: ConnectionPool,
        llm_orchestrator: Optional[Any] = None,
        storage_dir: Optional[str] = None
    ):
        """
        初始化 Work
        
        Args:
            pool: 数据库连接池
            llm_orchestrator: LLM 编排器（用于分析）
            storage_dir: 模板文件存储目录（可选，默认从环境变量读取）
        """
        self.pool = pool
        self.dao = TenderDAO(pool)
        self.llm_orchestrator = llm_orchestrator
        
        # 使用环境变量或传入的存储目录
        if storage_dir is None:
            storage_dir = os.getenv("TENDER_FORMAT_TEMPLATES_DIR", "storage/templates")
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    # ==================== CRUD 操作 ====================
    
    def list_templates(self, owner_id: Optional[str] = None) -> List[FormatTemplateOut]:
        """
        列出格式模板
        
        Args:
            owner_id: 所有者ID（可选，None表示列出所有公开模板）
            
        Returns:
            模板列表
        """
        templates = self.dao.list_format_templates(owner_id=owner_id)
        return [FormatTemplateOut(**t) for t in templates]
    
    def get_template(self, template_id: str) -> Optional[FormatTemplateOut]:
        """
        获取格式模板详情
        
        Args:
            template_id: 模板ID
            
        Returns:
            模板详情，如果不存在返回 None
        """
        template = self.dao.get_format_template(template_id)
        if not template:
            return None
        return FormatTemplateOut(**template)
    
    async def create_template(
        self,
        name: str,
        docx_bytes: bytes,
        filename: str,
        owner_id: str,
        description: Optional[str] = None,
        is_public: bool = False,
        model_id: Optional[str] = None,
    ) -> FormatTemplateCreateResult:
        """
        创建格式模板
        
        流程：
        1. 保存文件到 storage
        2. 样式解析（必须）
        3. Blocks 提取（必须）
        4. LLM 分析（可选，仅在传入 model_id 时执行）
        5. 创建数据库记录
        
        Args:
            name: 模板名称
            docx_bytes: Word 文档字节流
            filename: 原始文件名
            owner_id: 所有者ID
            description: 模板描述
            is_public: 是否公开
            model_id: LLM模型ID（可选）
            
        Returns:
            创建结果
        """
        logger.info(f"开始创建格式模板: name={name}, llm_enabled={bool(model_id)}")
        
        # 1. 保存文件
        file_id = uuid.uuid4().hex
        file_sha256 = hashlib.sha256(docx_bytes).hexdigest()
        storage_path = self.storage_dir / f"{file_id}_{filename}"
        
        with open(storage_path, "wb") as f:
            f.write(docx_bytes)
        
        logger.info(f"模板文件已保存: {storage_path}")
        
        # 2. 样式解析
        analysis_json = await self._analyze_template(
            str(storage_path),
            name,
            model_id=model_id
        )
        
        # 3. 创建数据库记录
        template = self.dao.create_format_template(
            name=name,
            description=description,
            style_config={},  # 保留字段，兼容旧版
            owner_id=owner_id,
            is_public=is_public
        )
        template_id = template["id"]
        
        # 4. 更新存储路径和分析结果
        self.dao._execute(
            """
            UPDATE format_templates
            SET template_storage_path = %s,
                template_sha256 = %s,
                analysis_json = %s,
                template_spec_analyzed_at = NOW()
            WHERE id = %s
            """,
            (str(storage_path), file_sha256, json.dumps(analysis_json), template_id)
        )
        
        logger.info(f"模板创建完成: template_id={template_id}")
        
        return FormatTemplateCreateResult(
            template_id=template_id,
            name=name,
            description=description,
            storage_path=str(storage_path),
            analysis_status="completed" if analysis_json else "failed",
            analysis_summary=self._build_analysis_summary(analysis_json, template_id, name).model_dump()
        )
    
    def update_template(
        self,
        template_id: str,
        update: FormatTemplateUpdateReq
    ) -> FormatTemplateOut:
        """
        更新格式模板元数据
        
        Args:
            template_id: 模板ID
            update: 更新请求
            
        Returns:
            更新后的模板
        """
        updated = self.dao.update_format_template_meta(
            template_id=template_id,
            name=update.name,
            description=update.description,
            is_public=update.is_public
        )
        return FormatTemplateOut(**updated)
    
    def delete_template(self, template_id: str) -> bool:
        """
        删除格式模板
        
        Args:
            template_id: 模板ID
            
        Returns:
            是否成功删除
        """
        try:
            # 获取模板信息（用于删除文件）
            template = self.dao.get_format_template(template_id)
            if template:
                # 删除文件
                storage_path = template.get("template_storage_path")
                if storage_path and os.path.exists(storage_path):
                    try:
                        os.remove(storage_path)
                        logger.info(f"已删除模板文件: {storage_path}")
                    except Exception as e:
                        logger.warning(f"删除模板文件失败: {e}")
            
            # 删除数据库记录
            self.dao.delete_format_template(template_id)
            logger.info(f"模板删除完成: template_id={template_id}")
            return True
        except Exception as e:
            logger.error(f"删除模板失败: {e}", exc_info=True)
            return False
    
    # ==================== 分析和解析 ====================
    
    async def analyze_template(
        self,
        template_id: str,
        force: bool = False,
        docx_bytes: Optional[bytes] = None,
        model_id: Optional[str] = None
    ) -> FormatTemplateOut:
        """
        分析或重新分析格式模板
        
        Args:
            template_id: 模板ID
            force: 是否强制重新分析
            docx_bytes: 新的文档字节流（如果要替换文件）
            model_id: LLM模型ID
            
        Returns:
            更新后的模板
        """
        template = self.dao.get_format_template(template_id)
        if not template:
            raise ValueError(f"模板不存在: {template_id}")
        
        storage_path = template.get("template_storage_path")
        
        # 如果提供了新文件，先替换
        if docx_bytes:
            with open(storage_path, "wb") as f:
                f.write(docx_bytes)
            
            # 更新 SHA256
            file_sha256 = hashlib.sha256(docx_bytes).hexdigest()
            self.dao._execute(
                "UPDATE format_templates SET file_sha256 = %s WHERE id = %s",
                (file_sha256, template_id)
            )
            logger.info(f"已替换模板文件: {storage_path}")
        
        # 重新分析
        analysis_json = await self._analyze_template(
            storage_path,
            template["name"],
            model_id=model_id
        )
        
        # 更新分析结果
        self.dao._execute(
            """
            UPDATE format_templates
            SET analysis_json = %s,
                template_spec_analyzed_at = NOW()
            WHERE id = %s
            """,
            (json.dumps(analysis_json), template_id)
        )
        
        logger.info(f"模板分析完成: template_id={template_id}")
        
        # 返回更新后的模板
        updated = self.dao.get_format_template(template_id)
        return FormatTemplateOut(**updated)
    
    async def parse_template(
        self,
        template_id: str,
        force: bool = False
    ) -> FormatTemplateParseSummary:
        """
        确定性解析模板（header/footer 图片 + section/variants + headingLevels）
        
        Args:
            template_id: 模板ID
            force: 是否强制重新解析
            
        Returns:
            解析摘要
        """
        template = self.dao.get_format_template(template_id)
        if not template:
            raise ValueError(f"模板不存在: {template_id}")
        
        storage_path = template.get("template_storage_path")
        if not storage_path or not os.path.exists(storage_path):
            raise ValueError(f"模板文件不存在: {storage_path}")
        
        # TODO: 实现确定性解析逻辑
        # 这里可以调用专门的解析服务
        # 暂时返回一个最小结果
        logger.info(f"解析模板: template_id={template_id}")
        
        return FormatTemplateParseSummary(
            template_id=template_id,
            sections=[],
            variants=[],
            heading_levels=[],
            header_images=[],
            footer_images=[]
        )
    
    def get_spec(self, template_id: str) -> FormatTemplateSpecOut:
        """
        获取格式模板的样式规格
        
        Args:
            template_id: 模板ID
            
        Returns:
            样式规格
        """
        template = self.dao.get_format_template(template_id)
        if not template:
            raise ValueError(f"模板不存在: {template_id}")
        
        analysis_json = template.get("analysis_json")
        if not analysis_json:
            return FormatTemplateSpecOut(style_hints={})
        
        if isinstance(analysis_json, str):
            analysis_json = json.loads(analysis_json)
        
        # 从 analysis_json 提取样式信息
        style_profile = analysis_json.get("styleProfile", {})
        role_mapping = analysis_json.get("roleMapping", {})
        
        # 构建 style_hints
        style_hints = {}
        for style_def in style_profile.get("styles", []):
            style_name = style_def.get("styleId") or style_def.get("name")
            if style_name:
                style_hints[style_name] = self._convert_style_to_hints(style_def)
        
        return FormatTemplateSpecOut(
            style_hints=style_hints,
            role_mapping=role_mapping,
            meta={"template_id": template_id}
        )
    
    def get_analysis_summary(self, template_id: str) -> FormatTemplateAnalysisSummary:
        """
        获取格式模板分析摘要
        
        Args:
            template_id: 模板ID
            
        Returns:
            分析摘要
        """
        template = self.dao.get_format_template(template_id)
        if not template:
            raise ValueError(f"模板不存在: {template_id}")
        
        analysis_json = template.get("analysis_json")
        if not analysis_json:
            return FormatTemplateAnalysisSummary(
                template_id=template_id,
                template_name=template["name"],
                confidence=0.0
            )
        
        if isinstance(analysis_json, str):
            analysis_json = json.loads(analysis_json)
        
        return self._build_analysis_summary(analysis_json, template_id, template["name"])
    
    def get_parse_summary(self, template_id: str) -> FormatTemplateParseSummary:
        """
        获取格式模板解析摘要
        
        Args:
            template_id: 模板ID
            
        Returns:
            解析摘要
        """
        template = self.dao.get_format_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        analysis_json = template.get("analysis_json", {})
        
        # 提取样式信息
        style_profile = analysis_json.get("styleProfile", {})
        role_mapping = analysis_json.get("roleMapping", {})
        blocks = analysis_json.get("blocks", [])
        
        # 构建heading_levels（从roleMapping提取）
        heading_levels = []
        for level in ["h1", "h2", "h3", "h4", "h5", "h6", "h7", "h8", "h9"]:
            style_name = role_mapping.get(level)
            if style_name:
                heading_levels.append({
                    "level": level,
                    "style": style_name,
                    "display": f"{level.upper()} → {style_name}"
                })
        
        # 构建sections（从blocks提取段落和表格信息）
        sections = []
        paragraph_count = 0
        table_count = 0
        
        for block in blocks:
            block_type = block.get("type", "")
            if block_type == "paragraph":
                paragraph_count += 1
            elif block_type == "table":
                table_count += 1
        
        if paragraph_count > 0:
            sections.append({
                "type": "paragraph",
                "count": paragraph_count,
                "label": f"{paragraph_count} 个段落"
            })
        
        if table_count > 0:
            sections.append({
                "type": "table",
                "count": table_count,
                "label": f"{table_count} 个表格"
            })
        
        # 提取样式变体（从styleProfile获取所有样式）
        variants = []
        styles = style_profile.get("styles", [])
        for style in styles[:20]:  # 限制显示前20个样式
            style_name = style.get("name", "")
            if style_name:
                variants.append({
                    "name": style_name,
                    "type": style.get("type", "paragraph"),
                    "has_numbering": style.get("hasNumbering", False)
                })
        
        # 提取模板使用说明
        template_instructions = self._extract_template_instructions(blocks)
        
        # 提取页眉页脚规格
        header_footer_spec = self._extract_header_footer_spec(blocks)
        
        # 提取域代码使用说明
        field_code_usage = self._extract_field_code_usage(blocks)
        
        # 提取封面结构
        cover_structure = self._extract_cover_structure(blocks)
        
        return FormatTemplateParseSummary(
            template_id=template_id,
            sections=sections,
            variants=variants,
            heading_levels=heading_levels,
            template_instructions=template_instructions,
            header_footer_spec=header_footer_spec,
            field_code_usage=field_code_usage,
            cover_structure=cover_structure
        )
    
    # ==================== 预览 ====================
    
    def preview(
        self,
        template_id: str,
        format: str = "pdf"
    ) -> PreviewResult:
        """
        生成格式模板预览
        
        Args:
            template_id: 模板ID
            format: 预览格式 ("pdf" | "docx")
            
        Returns:
            预览结果（文件路径）
        """
        template = self.dao.get_format_template(template_id)
        if not template:
            raise ValueError(f"模板不存在: {template_id}")
        
        storage_path = template.get("template_storage_path")
        if not storage_path or not os.path.exists(storage_path):
            raise ValueError(f"模板文件不存在: {storage_path}")
        
        # 如果请求的是 docx，直接返回原文件
        if format.lower() == "docx":
            return PreviewResult(
                file_path=storage_path,
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        
        # 如果请求的是 pdf，需要转换
        try:
            # 检查是否已有缓存的PDF
            preview_pdf_path = template.get("preview_pdf_path")
            if preview_pdf_path and os.path.exists(preview_pdf_path):
                logger.info(f"使用缓存的PDF预览: {preview_pdf_path}")
                return PreviewResult(
                    file_path=preview_pdf_path,
                    content_type="application/pdf"
                )
            
            # 生成新的PDF
            logger.info(f"生成PDF预览: {template_id}")
            output_dir = Path(self.storage_dir) / template_id
            output_dir.mkdir(parents=True, exist_ok=True)
            
            pdf_path = self._convert_docx_to_pdf(storage_path, output_dir)
            
            # 更新数据库缓存路径
            self.dao._execute(
                "UPDATE format_templates SET preview_pdf_path = %s WHERE id = %s",
                (pdf_path, template_id)
            )
            
            logger.info(f"PDF预览生成成功: {pdf_path}")
            return PreviewResult(
                file_path=pdf_path,
                content_type="application/pdf"
            )
            
        except Exception as e:
            logger.error(f"PDF转换失败，降级返回DOCX: {e}", exc_info=True)
            return PreviewResult(
                file_path=storage_path,
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
    
    # ==================== 套用到项目目录 ====================
    
    async def apply_to_project_directory(
        self,
        project_id: str,
        template_id: str,
        return_type: str = "json"
    ) -> ApplyFormatTemplateResult:
        """
        套用格式模板到项目目录
        
        流程：
        1. 记录 format_template_id 到目录节点
        2. 使用 ExportService 导出文档（自动使用模板）
        3. 返回结果（包含预览和下载链接）
        
        Args:
            project_id: 项目ID
            template_id: 模板ID
            return_type: 返回类型 ("json" | "file")
            
        Returns:
            套用结果
        """
        logger.info(f"套用格式模板: project={project_id}, template={template_id}")
        
        try:
            # 1. 更新目录节点的 format_template_id
            nodes = self._apply_template_to_directory_meta(project_id, template_id)
            
            # 2. 验证模板存在
            template = self.dao.get_format_template(template_id)
            if not template:
                return ApplyFormatTemplateResult(
                    ok=False,
                    detail="格式模板不存在"
                )
            
            template_path = template.get("template_storage_path")
            if not template_path or not os.path.exists(template_path):
                return ApplyFormatTemplateResult(
                    ok=False,
                    detail=f"模板文件不存在: {template_path}"
                )
            
            # 3. 准备输出目录（使用持久化路径）
            renders_dir = os.getenv("TENDER_RENDERS_DIR", "/app/storage/tender/renders")
            output_dir = Path(renders_dir) / project_id
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 4. 使用 ExportService 导出（会自动使用模板）
            from app.services.export.export_service import ExportService
            export_service = ExportService(self.dao)
            
            try:
                output_path = await export_service.export_project_to_docx(
                    project_id=project_id,
                    format_template_id=template_id,
                    include_toc=True,
                    prefix_numbering=False,
                    merge_semantic_summary=False,
                    output_dir=str(output_dir)
                )
                
                logger.info(f"文档导出完成: {output_path}")
                
            except Exception as export_error:
                logger.error(f"文档导出失败: {export_error}", exc_info=True)
                return ApplyFormatTemplateResult(
                    ok=False,
                    detail=f"文档导出失败: {str(export_error)}"
                )
            
            # 5. 构建下载 URL
            filename = Path(output_path).name
            project = self.dao.get_project(project_id)
            project_name = project.get("name", "投标文件") if project else "投标文件"
            
            # 构建可访问的 URL（使用新的格式预览端点）
            download_url = f"/api/apps/tender/projects/{project_id}/exports/docx/{filename}"
            
            # 预览 URL（使用格式预览端点，自动生成 PDF）
            preview_url = f"/api/apps/tender/projects/{project_id}/directory/format-preview?format=pdf&format_template_id={template_id}"
            
            return ApplyFormatTemplateResult(
                ok=True,
                nodes=nodes,
                preview_pdf_url=preview_url,
                download_docx_url=download_url,
                docx_path=output_path,
                pdf_path=None
            )
            
        except Exception as e:
            logger.error(f"套用格式失败: {e}", exc_info=True)
            return ApplyFormatTemplateResult(
                ok=False,
                detail=f"套用格式失败: {str(e)}"
            )
    
    async def preview_project_with_template(
        self,
        project_id: str,
        template_id: str,
        output_format: str = "pdf"
    ) -> ProjectPreviewResult:
        """
        生成项目套用格式后的预览文件
        
        流程：
        1. 使用 ExportService 导出 DOCX（自动使用模板）
        2. 如果需要 PDF，则转换 DOCX -> PDF
        3. 返回文件路径
        
        Args:
            project_id: 项目ID
            template_id: 模板ID
            output_format: 输出格式 ("pdf" | "docx")
            
        Returns:
            预览结果
        """
        logger.info(f"生成项目格式预览: project={project_id}, template={template_id}, format={output_format}")
        
        try:
            # 1. 验证模板存在
            template = self.dao.get_format_template(template_id)
            if not template:
                return ProjectPreviewResult(
                    ok=False,
                    error="格式模板不存在"
                )
            
            template_path = template.get("template_storage_path")
            if not template_path or not os.path.exists(template_path):
                return ProjectPreviewResult(
                    ok=False,
                    error=f"模板文件不存在: {template_path}"
                )
            
            # 2. 准备输出目录（使用持久化路径）
            renders_dir = os.getenv("TENDER_RENDERS_DIR", "/app/storage/tender/renders")
            output_dir = Path(renders_dir) / project_id / "preview"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 3. 使用 ExportService 导出 DOCX（会自动使用模板）
            from app.services.export.export_service import ExportService
            export_service = ExportService(self.dao)
            
            try:
                docx_path = await export_service.export_project_to_docx(
                    project_id=project_id,
                    format_template_id=template_id,
                    include_toc=True,
                    prefix_numbering=False,
                    merge_semantic_summary=False,
                    output_dir=str(output_dir)
                )
                
                logger.info(f"DOCX 导出完成: {docx_path}")
                
            except Exception as export_error:
                logger.error(f"DOCX 导出失败: {export_error}", exc_info=True)
                return ProjectPreviewResult(
                    ok=False,
                    error=f"文档导出失败: {str(export_error)}"
                )
            
            # 4. 如果只需要 DOCX，直接返回
            if output_format.lower() == "docx":
                return ProjectPreviewResult(
                    ok=True,
                    docx_path=docx_path
                )
            
            # 5. 转换为 PDF
            try:
                pdf_path = self._convert_docx_to_pdf(docx_path, output_dir)
                logger.info(f"PDF 转换完成: {pdf_path}")
                
                return ProjectPreviewResult(
                    ok=True,
                    docx_path=docx_path,
                    pdf_path=pdf_path
                )
                
            except Exception as pdf_error:
                logger.error(f"PDF 转换失败: {pdf_error}", exc_info=True)
                # PDF 转换失败时降级返回 DOCX
                return ProjectPreviewResult(
                    ok=True,
                    docx_path=docx_path,
                    error=f"PDF转换失败: {str(pdf_error)}，已降级返回DOCX"
                )
        
        except Exception as e:
            logger.error(f"生成格式预览失败: {e}", exc_info=True)
            return ProjectPreviewResult(
                ok=False,
                error=f"生成预览失败: {str(e)}"
            )
    
    def _convert_docx_to_pdf(self, docx_path: str, output_dir: Path) -> str:
        """
        将 DOCX 转换为 PDF
        
        使用 LibreOffice/soffice 进行转换
        
        Args:
            docx_path: DOCX 文件路径
            output_dir: 输出目录
            
        Returns:
            PDF 文件路径
        """
        import subprocess
        
        # 使用 LibreOffice 转换
        cmd = [
            "soffice",
            "--headless",
            "--nologo",
            "--nolockcheck",
            "--convert-to", "pdf",
            "--outdir", str(output_dir),
            docx_path
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                check=True
            )
            
            # 生成的 PDF 文件名
            docx_filename = Path(docx_path).stem
            pdf_path = output_dir / f"{docx_filename}.pdf"
            
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF 文件未生成: {pdf_path}")
            
            return str(pdf_path)
            
        except subprocess.TimeoutExpired:
            raise TimeoutError("PDF转换超时（60秒）")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"PDF转换失败: {e.stderr}")
        except Exception as e:
            raise RuntimeError(f"PDF转换异常: {str(e)}")
    
    # ==================== 私有辅助方法 ====================
    
    async def _analyze_template(
        self,
        docx_path: str,
        template_name: str,
        model_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        分析模板，产出 analysis_json
        
        包含三部分：
        1. styleProfile: 样式定义（从 styles.xml 解析）
        2. roleMapping: 样式角色映射（h1~h9, body 等）
        3. applyAssets: LLM 理解的保留/删除计划、插入点等（可选）
        4. blocks: 文档块（前100个）
        """
        logger.info(f"分析模板: {template_name}")
        
        # 1. 样式解析（必须）
        from app.services.template.template_style_analyzer import (
            extract_style_profile,
            infer_role_mapping,
            get_fallback_role_mapping
        )
        
        try:
            style_profile = extract_style_profile(docx_path)
            role_mapping = infer_role_mapping(style_profile)
            logger.info(f"样式解析完成: {len(style_profile.get('styles', []))} 个样式")
        except Exception as e:
            logger.error(f"样式解析失败: {e}")
            style_profile = {"styles": [], "hasNumbering": False}
            role_mapping = get_fallback_role_mapping()
        
        # 2. 提取 blocks（必须）
        from app.services.template.docx_blocks import extract_doc_blocks
        
        try:
            blocks = extract_doc_blocks(docx_path)
            logger.info(f"提取文档块: {len(blocks)} 个块")
        except Exception as e:
            logger.error(f"提取blocks失败: {e}")
            blocks = []
        
        # 3. LLM 分析（可选）
        apply_assets = None
        if model_id:
            logger.info(f"启用 LLM 分析: model_id={model_id}")
            try:
                from app.services.template.template_applyassets_llm import (
                    build_applyassets_prompt,
                    validate_applyassets
                )
                from app.services.llm_client import llm_json
                
                prompt = build_applyassets_prompt(template_name, blocks)
                llm_result = llm_json(prompt, model_id=model_id, temperature=0.0)
                apply_assets = validate_applyassets(llm_result, blocks)
                logger.info(f"LLM 分析完成: confidence={apply_assets.get('policy', {}).get('confidence', 0)}")
            except Exception as e:
                logger.warning(f"LLM 分析失败，使用默认策略: {e}", exc_info=True)
        
        if not apply_assets:
            from app.services.template.template_applyassets_llm import get_fallback_apply_assets
            apply_assets = get_fallback_apply_assets()
        
        # 4. 构建 analysis_json
        return {
            "styleProfile": style_profile,
            "roleMapping": role_mapping,
            "applyAssets": apply_assets,
            "blocks": blocks[:100]  # 只保留前100个块
        }
    
    def _apply_template_to_directory_meta(
        self,
        project_id: str,
        template_id: str
    ) -> List[Dict[str, Any]]:
        """
        更新项目目录的元数据，记录 format_template_id
        
        Args:
            project_id: 项目ID
            template_id: 模板ID
            
        Returns:
            更新后的目录节点列表
        """
        # 获取根节点
        nodes = self.dao.list_directory(project_id)
        if not nodes:
            return []
        
        root_node = None
        for node in nodes:
            if not node.get("parent_id"):
                root_node = node
                break
        
        if not root_node:
            return nodes
        
        # 更新根节点的 meta_json
        root_id = root_node["id"]
        meta_json = root_node.get("meta_json") or {}
        if isinstance(meta_json, str):
            meta_json = json.loads(meta_json)
        
        meta_json["format_template_id"] = template_id
        
        self.dao._execute(
            "UPDATE tender_directory_nodes SET meta_json = %s WHERE id = %s",
            (json.dumps(meta_json), root_id)
        )
        
        logger.info(f"已更新目录元数据: project={project_id}, template={template_id}")
        
        # 返回更新后的节点列表
        return self.dao.list_directory(project_id)
    
    def _build_analysis_summary(
        self,
        analysis_json: Dict[str, Any],
        template_id: str,
        template_name: str
    ) -> FormatTemplateAnalysisSummary:
        """构建分析摘要"""
        if not analysis_json:
            return FormatTemplateAnalysisSummary(
                template_id=template_id,
                template_name=template_name,
                confidence=0.0
            )
        
        role_mapping = analysis_json.get("roleMapping", {})
        apply_assets = analysis_json.get("applyAssets", {})
        blocks = analysis_json.get("blocks", [])
        policy = apply_assets.get("policy", {})
        
        return FormatTemplateAnalysisSummary(
            template_id=template_id,
            template_name=template_name,
            confidence=policy.get("confidence", 0.5),
            warnings=policy.get("warnings", []),
            anchors_count=len(apply_assets.get("anchors", [])),
            has_content_marker=any(
                b.get("markerFlags", {}).get("hasContentMarker")
                for b in blocks
            ),
            keep_blocks_count=len(apply_assets.get("keepPlan", {}).get("keepBlockIds", [])),
            delete_blocks_count=len(apply_assets.get("keepPlan", {}).get("deleteBlockIds", [])),
            heading_styles={k: v for k, v in role_mapping.items() if k.startswith("h")},
            body_style=role_mapping.get("body"),
            blocks_summary={
                "total": len(blocks),
                "paragraphs": sum(1 for b in blocks if b.get("type") == "paragraph"),
                "tables": sum(1 for b in blocks if b.get("type") == "table"),
            }
        )
    
    def _convert_style_to_hints(self, style_def: Dict[str, Any]) -> Dict[str, Any]:
        """将样式定义转换为前端使用的 style hints"""
        hints = {}
        
        # 字体大小
        if "fontSize" in style_def:
            hints["fontSize"] = style_def["fontSize"]
        
        # 字体样式
        if style_def.get("bold"):
            hints["bold"] = True
        if style_def.get("italic"):
            hints["italic"] = True
        if style_def.get("underline"):
            hints["underline"] = True
        
        # 颜色
        if "color" in style_def:
            hints["color"] = style_def["color"]
        
        # 对齐
        if "alignment" in style_def:
            hints["alignment"] = style_def["alignment"]
        
        # 行距
        if "lineSpacing" in style_def:
            hints["lineSpacing"] = style_def["lineSpacing"]
        
        # 缩进
        if "indentLeft" in style_def:
            hints["indentLeft"] = style_def["indentLeft"]
        if "indentRight" in style_def:
            hints["indentRight"] = style_def["indentRight"]
        if "indentFirstLine" in style_def:
            hints["indentFirstLine"] = style_def["indentFirstLine"]
        
        return hints
    
    def _extract_template_instructions(self, blocks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        提取模板使用说明
        
        识别标准：包含"使用说明"、"模板说明"、"填写说明"等关键词的块及其后续块
        """
        import re
        
        instruction_blocks = []
        instructions_text = []
        in_instruction_section = False
        
        for block in blocks:
            text = block.get("text", "").strip()
            block_id = block.get("blockId", "")
            
            # 检测说明开始
            if re.search(r'(使用说明|模板说明|填写说明|注意事项)', text, re.IGNORECASE):
                in_instruction_section = True
                instruction_blocks.append(block_id)
                instructions_text.append(text)
                continue
            
            # 在说明区段内
            if in_instruction_section:
                # 检测说明结束（遇到标题或空块）
                if block.get("styleName", "").startswith("+标题") or block.get("styleName", "") == "+标题1":
                    in_instruction_section = False
                    break
                
                if text:  # 非空块
                    instruction_blocks.append(block_id)
                    instructions_text.append(text)
        
        if not instruction_blocks:
            return None
        
        return {
            "has_instructions": True,
            "instruction_blocks": instruction_blocks,
            "instructions_text": "\n".join(instructions_text),
            "instructions_count": len(instruction_blocks)
        }
    
    def _extract_header_footer_spec(self, blocks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        提取页眉页脚规格
        
        从blocks中提取页眉页脚相关的尺寸规格
        """
        import re
        
        paper_sizes = {}
        layout_notes = []
        text_indent = None
        
        for block in blocks:
            text = block.get("text", "")
            
            # 提取页眉规格
            if "页眉" in text and ("cm" in text or "厘米" in text):
                # A4竖版
                match = re.search(r'页眉.*?A4.*?竖版.*?高度\s*([\d.]+)\s*cm.*?长度\s*([\d.]+)\s*cm', text)
                if match:
                    paper_sizes["A4_portrait"] = paper_sizes.get("A4_portrait", {})
                    paper_sizes["A4_portrait"]["header"] = {
                        "height": f"{match.group(1)}cm",
                        "width": f"{match.group(2)}cm"
                    }
                
                # A4横版
                match = re.search(r'A4.*?横版.*?高度\s*([\d.]+)\s*cm.*?长度\s*([\d.]+)\s*cm', text)
                if match:
                    paper_sizes["A4_landscape"] = paper_sizes.get("A4_landscape", {})
                    paper_sizes["A4_landscape"]["header"] = {
                        "height": f"{match.group(1)}cm",
                        "width": f"{match.group(2)}cm"
                    }
                
                # A3横版
                match = re.search(r'A3.*?横版.*?高度\s*([\d.]+)\s*cm.*?长度\s*([\d.]+)\s*cm', text)
                if match:
                    paper_sizes["A3_landscape"] = paper_sizes.get("A3_landscape", {})
                    paper_sizes["A3_landscape"]["header"] = {
                        "height": f"{match.group(1)}cm",
                        "width": f"{match.group(2)}cm"
                    }
            
            # 提取页脚规格
            if "页脚" in text and ("cm" in text or "厘米" in text):
                # A4竖版
                match = re.search(r'页脚.*?A4.*?竖版.*?高度\s*([\d.]+)\s*cm.*?长度\s*([\d.]+)\s*cm', text)
                if match:
                    paper_sizes["A4_portrait"] = paper_sizes.get("A4_portrait", {})
                    paper_sizes["A4_portrait"]["footer"] = {
                        "height": f"{match.group(1)}cm",
                        "width": f"{match.group(2)}cm"
                    }
                
                # A4横版
                match = re.search(r'A4.*?横版.*?高度\s*([\d.]+)\s*cm.*?长度\s*([\d.]+)\s*cm', text)
                if match:
                    paper_sizes["A4_landscape"] = paper_sizes.get("A4_landscape", {})
                    paper_sizes["A4_landscape"]["footer"] = {
                        "height": f"{match.group(1)}cm",
                        "width": f"{match.group(2)}cm"
                    }
                
                # A3横版
                match = re.search(r'A3.*?横版.*?高度\s*([\d.]+)\s*[cm].*?长度\s*([\d.]+)\s*cm', text)
                if match:
                    paper_sizes["A3_landscape"] = paper_sizes.get("A3_landscape", {})
                    paper_sizes["A3_landscape"]["footer"] = {
                        "height": f"{match.group(1)}cm",
                        "width": f"{match.group(2)}cm"
                    }
            
            # 提取文本缩进
            if "缩进" in text:
                match = re.search(r'缩进\s*[-]*\s*(\d+)\s*字符', text)
                if match:
                    text_indent = f"-{match.group(1)}字符" if "-" in text else f"{match.group(1)}字符"
            
            # 提取布局说明
            if "页眉" in text or "页脚" in text:
                if "异型排版" in text or "连接至前一节" in text or "图片" in text:
                    layout_notes.append(text)
        
        if not paper_sizes and not layout_notes:
            return None
        
        result = {}
        if paper_sizes:
            result["paper_sizes"] = paper_sizes
        if text_indent:
            result["text_indent"] = text_indent
        if layout_notes:
            result["layout_notes"] = layout_notes
        
        return result
    
    def _extract_field_code_usage(self, blocks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        提取域代码使用说明
        
        识别标准：包含"域"、"域代码"、"StyleRef"等关键词
        """
        import re
        
        uses_field_codes = False
        field_type = None
        auto_update = None
        plain_text_sections = []
        notes = []
        
        for block in blocks:
            text = block.get("text", "")
            
            if "域" in text or "field" in text.lower():
                uses_field_codes = True
                notes.append(text)
                
                # 提取域类型
                if "StyleRef" in text:
                    field_type = "StyleRef"
                elif "域代码" in text:
                    match = re.search(r'"([^"]+)"', text)
                    if match:
                        field_type = match.group(1)
                
                # 提取自动更新内容
                if "自动更新" in text or "自动引用" in text:
                    match = re.search(r'(段落编号|样式|标题|编号)', text)
                    if match:
                        auto_update = match.group(1)
                
                # 提取纯文字区段
                if "纯文字" in text or "纯文本" in text:
                    match = re.search(r'(首页|目录|封面)', text)
                    if match:
                        plain_text_sections.append(match.group(1))
        
        if not uses_field_codes:
            return None
        
        result = {
            "uses_field_codes": True
        }
        if field_type:
            result["field_type"] = field_type
        if auto_update:
            result["auto_update"] = auto_update
        if plain_text_sections:
            result["plain_text_sections"] = plain_text_sections
        if notes:
            result["notes"] = notes
        
        return result
    
    def _extract_cover_structure(self, blocks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        提取封面结构
        
        从前N个blocks中识别封面元素
        """
        import re
        
        cover_elements = []
        cover_blocks = []
        
        # 只检查前15个块
        for block in blocks[:15]:
            text = block.get("text", "").strip()
            block_id = block.get("blockId", "")
            
            if not text:
                continue
            
            # 识别封面元素
            if re.search(r'(正本|副本)', text):
                cover_elements.append("正本/副本标记")
                cover_blocks.append(block_id)
            elif re.search(r'(商务标|技术标)', text):
                cover_elements.append("商务标/技术标")
                cover_blocks.append(block_id)
            elif re.search(r'(项目编号|项目名称)', text):
                cover_elements.append("项目编号")
                cover_blocks.append(block_id)
            elif "投标文件" in text:
                cover_elements.append("投标文件标题")
                cover_blocks.append(block_id)
            elif re.search(r'(投标单位|投标人)', text):
                cover_elements.append("投标单位信息")
                cover_blocks.append(block_id)
            elif re.search(r'(法定代表人|负责人|授权)', text):
                cover_elements.append("法定代表人/授权")
                cover_blocks.append(block_id)
            elif "日期" in text or re.search(r'\d{4}\s*年', text):
                cover_elements.append("日期")
                cover_blocks.append(block_id)
        
        if not cover_elements:
            return None
        
        return {
            "has_cover": True,
            "cover_elements": cover_elements,
            "cover_blocks": cover_blocks,
            "cover_blocks_count": len(cover_blocks)
        }

