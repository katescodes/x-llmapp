"""
申报书服务（核心业务逻辑）
"""
import logging
import os
from typing import Any, Dict, List, Optional

from psycopg_pool import ConnectionPool

from app.platform.utils.async_runner import run_async
from app.platform.extraction.exceptions import ExtractionParseError, ExtractionSchemaError
from app.services.dao.declare_dao import DeclareDAO
from app.works.declare.extract_v2_service import DeclareExtractV2Service

logger = logging.getLogger(__name__)


class DeclareService:
    """申报书服务"""
    
    def __init__(self, dao: DeclareDAO, llm_orchestrator: Any, jobs_service: Any = None):
        self.dao = dao
        self.llm = llm_orchestrator
        self.jobs_service = jobs_service
    
    def import_assets(
        self,
        project_id: str,
        kind: str,
        files: List[Any],  # UploadFile objects
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        导入资产文件
        
        Args:
            project_id: 项目ID
            kind: 资产类型 (notice|user_doc|image|company|tech|other)
            files: 上传文件列表
            user_id: 用户ID
        
        Returns:
            创建的资产列表
        """
        import uuid
        from app.platform.ingest.v2_service import IngestV2Service
        from app.services.db.postgres import _get_pool
        
        pool = _get_pool()
        ingest_service = IngestV2Service(pool)
        
        # 获取项目关联的 KB
        project = self.dao.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")
        
        kb_id = project.get("kb_id")
        if not kb_id:
            raise ValueError(f"Project has no KB: {project_id}")
        
        # doc_type 映射到知识库分类
        from app.utils.doc_type_mapper import map_doc_type_to_kb_category
        
        doc_type_map = {
            "notice": "declare_notice",
            "user_doc": "declare_user_doc",  # 新增
            "image": "declare_image",         # 新增
            "company": "declare_company",
            "tech": "declare_tech",
            "other": "declare_other",
        }
        doc_type = doc_type_map.get(kind, "declare_other")
        kb_category = map_doc_type_to_kb_category(doc_type)
        
        assets = []
        
        # 特殊处理：检查是否有图片说明Excel
        image_descriptions = {}
        if kind == "image":
            for file in files:
                if file.filename.endswith(('.xlsx', '.xls')):
                    # 解析Excel获取图片说明
                    file_bytes = file.file.read()
                    file.file.seek(0)  # 重置文件指针
                    image_descriptions = self._parse_image_description_excel(file_bytes)
                    logger.info(f"[DeclareService] Parsed image descriptions from {file.filename}: {len(image_descriptions)} images")
                    break
        
        for file in files:
            # 读取文件内容
            file_bytes = file.file.read()
            
            # 保存文件
            storage_dir = os.getenv("DECLARE_STORAGE_DIR", "./data/declare/files")
            os.makedirs(storage_dir, exist_ok=True)
            file_path = os.path.join(storage_dir, f"{project_id}_{kind}_{file.filename}")
            
            with open(file_path, "wb") as f:
                f.write(file_bytes)
            
            # 判断资产类型
            asset_type = self._determine_asset_type(file.filename, kind)
            
            # 如果是图片说明Excel，只存储不入库向量
            if asset_type == "image_description":
                asset = self.dao.create_asset(
                    project_id=project_id,
                    kind=kind,
                    asset_type=asset_type,
                    filename=file.filename,
                    storage_path=file_path,
                    file_size=os.path.getsize(file_path),
                    mime_type=file.content_type,
                    document_id=None,
                    doc_version_id=None,
                    meta_json={"type": "image_description"},
                )
                assets.append(asset)
                continue
            
            # 图片文件：存储 + 关联说明
            if asset_type == "image":
                description = image_descriptions.get(file.filename, "")
                asset = self.dao.create_asset(
                    project_id=project_id,
                    kind=kind,
                    asset_type=asset_type,
                    filename=file.filename,
                    storage_path=file_path,
                    file_size=os.path.getsize(file_path),
                    mime_type=file.content_type,
                    document_id=None,
                    doc_version_id=None,
                    meta_json={
                        "description": description,
                        "description_source": "excel" if description else "none",
                    },
                )
                assets.append(asset)
                
                # 如果有说明，将说明文字入库向量（用于检索）
                if description:
                    temp_asset_id = f"temp_{uuid.uuid4().hex}"
                    text_content = f"图片：{file.filename}\n说明：{description}".encode('utf-8')
                    ingest_result = run_async(ingest_service.ingest_asset_v2(
                        project_id=project_id,
                        asset_id=temp_asset_id,
                        file_bytes=text_content,
                        filename=f"{file.filename}_description.txt",
                        doc_type=kb_category,
                        owner_id=user_id,
                        storage_path=None,
                    ))
                    # 更新asset的doc_version_id
                    self.dao.update_asset_meta(
                        asset["asset_id"],
                        {
                            **asset["meta_json"],
                            "doc_version_id": ingest_result.doc_version_id,
                            "segment_count": ingest_result.segment_count,
                        }
                    )
                    logger.info(f"[DeclareService] Indexed image description: {file.filename} -> {ingest_result.segment_count} segments")
                
                continue
            
            # 文档文件：正常入库
            # 生成临时 asset_id
            temp_asset_id = f"temp_{uuid.uuid4().hex}"
            
            # 调用 IngestV2 入库
            ingest_result = run_async(ingest_service.ingest_asset_v2(
                project_id=project_id,
                asset_id=temp_asset_id,
                file_bytes=file_bytes,
                filename=file.filename,
                doc_type=kb_category,
                owner_id=user_id,
                storage_path=file_path,
            ))
            
            # 创建资产记录
            asset = self.dao.create_asset(
                project_id=project_id,
                kind=kind,
                asset_type="document",
                filename=file.filename,
                storage_path=file_path,
                file_size=os.path.getsize(file_path),
                mime_type=file.content_type,
                document_id=None,
                doc_version_id=ingest_result.doc_version_id,
                meta_json={
                    "ingest_v2_status": "success",
                    "segment_count": ingest_result.segment_count,
                    "milvus_count": ingest_result.milvus_count,
                },
            )
            assets.append(asset)
            
            logger.info(f"[DeclareService] Imported asset: {asset['asset_id']} doc_version_id={ingest_result.doc_version_id} segments={ingest_result.segment_count}")
        
        return assets
    
    def extract_requirements(
        self,
        project_id: str,
        model_id: Optional[str],
        run_id: Optional[str] = None,
    ):
        """抽取申报要求（同步入口）"""
        from app.services.db.postgres import _get_pool
        
        pool = _get_pool()
        extract_v2 = DeclareExtractV2Service(pool, self.llm)
        
        try:
            result = run_async(extract_v2.extract_requirements(
                project_id=project_id,
                model_id=model_id,
                run_id=run_id,
            ))
            
            # 保存到数据库
            self.dao.upsert_requirements(
                project_id=project_id,
                data_json=result.get("data", {}),
                evidence_chunk_ids=result.get("evidence_chunk_ids", []),
                retrieval_trace=result.get("retrieval_trace", {}),
            )
            
            # 更新 run 状态
            if run_id:
                self.dao.update_run(
                    run_id,
                    "success",
                    progress=1.0,
                    message="Requirements extracted",
                    result_json=result,
                )
            
            logger.info(f"[DeclareService] extract_requirements success project_id={project_id}")
            
        except (ExtractionParseError, ExtractionSchemaError) as e:
            logger.error(f"[DeclareService] extract_requirements failed: {e}")
            if run_id:
                self.dao.update_run(
                    run_id,
                    "failed",
                    progress=0.0,
                    message=str(e),
                    result_json={"error": str(e), "error_type": type(e).__name__},
                )
            raise
    
    def generate_directory(
        self,
        project_id: str,
        model_id: Optional[str],
        run_id: Optional[str] = None,
    ):
        """生成申报书目录（同步入口，支持多项目类型）"""
        from app.services.db.postgres import _get_pool
        
        pool = _get_pool()
        extract_v2 = DeclareExtractV2Service(pool, self.llm)
        
        try:
            result = run_async(extract_v2.generate_directory(
                project_id=project_id,
                model_id=model_id,
                run_id=run_id,
            ))
            
            # 提取数据
            data = result.get("data", {})
            
            # 支持新格式（多项目）和旧格式（单项目）
            projects = data.get("projects", [])
            if not projects:
                # 兼容旧格式：如果没有 projects 字段，尝试提取 nodes
                nodes = data.get("nodes", [])
                if nodes:
                    projects = [{
                        "project_type": "默认",
                        "project_description": None,
                        "nodes": nodes
                    }]
            
            if not projects:
                raise ValueError("Directory projects empty")
            
            total_nodes = 0
            version_ids = []
            
            # 为每个项目类型创建独立的目录版本
            for project in projects:
                project_type = project.get("project_type", "默认")
                project_description = project.get("project_description")
                nodes = project.get("nodes", [])
                
                if not nodes:
                    logger.warning(f"Project type '{project_type}' has no nodes, skipping")
                    continue
                
                # 后处理：排序 + 构建树
                nodes_sorted = sorted(nodes, key=lambda n: (n.get("level", 99), n.get("order_no", 0)))
                nodes_with_tree = self._build_directory_tree(nodes_sorted)
                
                # 保存（版本化，关联项目类型）
                version_id = self.dao.create_directory_version(
                    project_id, 
                    source="notice", 
                    run_id=run_id,
                    project_type=project_type,
                    project_description=project_description
                )
                self.dao.upsert_directory_nodes(version_id, project_id, nodes_with_tree)
                
                version_ids.append(version_id)
                total_nodes += len(nodes_with_tree)
                
                logger.info(
                    f"[DeclareService] Saved directory for project_type='{project_type}' "
                    f"nodes={len(nodes_with_tree)} version_id={version_id}"
                )
            
            # 设置所有新版本为活跃状态（每个项目类型都应该可见）
            for version_id in version_ids:
                self.dao.set_active_directory_version(project_id, version_id)
            
            # 更新 run 状态
            if run_id:
                self.dao.update_run(
                    run_id,
                    "success",
                    progress=1.0,
                    message=f"Directory generated: {len(projects)} project types, {total_nodes} nodes",
                    result_json=result,
                )
            
            logger.info(
                f"[DeclareService] generate_directory success "
                f"project_id={project_id} project_types={len(projects)} total_nodes={total_nodes}"
            )
            
        except (ExtractionParseError, ExtractionSchemaError, ValueError) as e:
            logger.error(f"[DeclareService] generate_directory failed: {e}")
            if run_id:
                self.dao.update_run(
                    run_id,
                    "failed",
                    progress=0.0,
                    message=str(e),
                    result_json={"error": str(e), "error_type": type(e).__name__},
                )
            raise
    
    def _build_directory_tree(self, nodes: List[Dict]) -> List[Dict]:
        """构建目录树：生成 parent_id 和 numbering"""
        import uuid
        stack = {}
        result = []
        
        for i, node in enumerate(nodes):
            level = node.get("level", 1)
            
            # 生成 parent_id
            if level > 1:
                parent_node = stack.get(level - 1)
                node["parent_id"] = parent_node.get("id") if parent_node else None
            else:
                node["parent_id"] = None
            
            # 生成唯一 id（使用 UUID 避免冲突）
            node["id"] = f"declare_node_{uuid.uuid4().hex[:16]}"
            
            # 更新栈
            stack[level] = node
            for l in list(stack.keys()):
                if l > level:
                    del stack[l]
            
            result.append(node)
        
        return result
    
    
    async def generate_document(
        self,
        project_id: str,
        run_id: Optional[str] = None,
        auto_generate_content: bool = True,
        model_id: Optional[str] = None,
    ):
        """生成申报书文档（同步入口）"""
        from app.services.export.declare_docx_exporter import DeclareDocxExporter
        
        try:
            exporter = DeclareDocxExporter(self.dao)
            result = await exporter.export(
                project_id,
                auto_generate_content=auto_generate_content,
                model_id=model_id,
            )
            
            # 更新 run 状态
            if run_id:
                self.dao.update_run(
                    run_id,
                    "success",
                    progress=1.0,
                    message="Document generated",
                    result_json=result,
                )
            
            logger.info(f"[DeclareService] generate_document success project_id={project_id} document_id={result.get('document_id')}")
            
        except Exception as e:
            logger.error(f"[DeclareService] generate_document failed: {e}")
            if run_id:
                self.dao.update_run(
                    run_id,
                    "failed",
                    progress=0.0,
                    message=str(e),
                    result_json={"error": str(e), "error_type": type(e).__name__},
                )
            raise
    
    def _parse_image_description_excel(self, file_bytes: bytes) -> Dict[str, str]:
        """
        解析图片说明Excel文件
        
        Args:
            file_bytes: Excel文件字节内容
        
        Returns:
            {图片文件名: 图片说明}
        """
        import pandas as pd
        from io import BytesIO
        
        try:
            df = pd.read_excel(BytesIO(file_bytes))
            
            # 检查列数
            if df.shape[1] < 2:
                logger.warning("[DeclareService] Image description Excel has less than 2 columns")
                return {}
            
            result = {}
            # 使用前两列：第一列是文件名，第二列是说明
            for idx, row in df.iterrows():
                filename = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
                description = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
                
                if filename and description:
                    result[filename] = description
            
            return result
        except Exception as e:
            logger.error(f"[DeclareService] Failed to parse image description Excel: {e}")
            return {}
    
    def _determine_asset_type(self, filename: str, kind: str) -> str:
        """
        判断资产类型
        
        Args:
            filename: 文件名
            kind: 上传时指定的kind
        
        Returns:
            asset_type: document | image | image_description
        """
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        
        # 图片扩展名
        image_exts = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff', 'svg'}
        
        # Excel扩展名
        excel_exts = {'xlsx', 'xls'}
        
        if kind == "image":
            if ext in excel_exts:
                return "image_description"
            elif ext in image_exts:
                return "image"
        
        return "document"

