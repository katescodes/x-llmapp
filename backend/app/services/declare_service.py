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
            kind: 资产类型 (notice|company|tech|other)
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
        
        # doc_type 映射
        doc_type_map = {
            "notice": "declare_notice",
            "company": "declare_company",
            "tech": "declare_tech",
            "other": "declare_other",
        }
        doc_type = doc_type_map.get(kind, "declare_other")
        
        assets = []
        for file in files:
            # 读取文件内容
            file_bytes = file.file.read()
            
            # 保存文件
            storage_dir = os.getenv("DECLARE_STORAGE_DIR", "./data/declare/files")
            os.makedirs(storage_dir, exist_ok=True)
            file_path = os.path.join(storage_dir, f"{project_id}_{kind}_{file.filename}")
            
            with open(file_path, "wb") as f:
                f.write(file_bytes)
            
            # 生成临时 asset_id
            temp_asset_id = f"temp_{uuid.uuid4().hex}"
            
            # 调用 IngestV2 入库 - 使用正确的方法名 ingest_asset_v2
            ingest_result = run_async(ingest_service.ingest_asset_v2(
                project_id=project_id,
                asset_id=temp_asset_id,
                file_bytes=file_bytes,
                filename=file.filename,
                doc_type=doc_type,
                owner_id=user_id,
                storage_path=file_path,
            ))
            
            # 创建资产记录
            asset = self.dao.create_asset(
                project_id=project_id,
                kind=kind,
                filename=file.filename,
                storage_path=file_path,
                file_size=os.path.getsize(file_path),
                mime_type=file.content_type,
                document_id=None,  # IngestV2Result 没有 document_id
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
        """生成申报书目录（同步入口）"""
        from app.services.db.postgres import _get_pool
        
        pool = _get_pool()
        extract_v2 = DeclareExtractV2Service(pool, self.llm)
        
        try:
            result = run_async(extract_v2.generate_directory(
                project_id=project_id,
                model_id=model_id,
                run_id=run_id,
            ))
            
            # 提取 nodes
            nodes = result.get("data", {}).get("nodes", [])
            if not nodes:
                raise ValueError("Directory nodes empty")
            
            # 后处理：排序 + 构建树
            nodes_sorted = sorted(nodes, key=lambda n: (n.get("level", 99), n.get("order_no", 0)))
            nodes_with_tree = self._build_directory_tree(nodes_sorted)
            
            # 保存（版本化）
            version_id = self.dao.create_directory_version(project_id, source="notice", run_id=run_id)
            self.dao.upsert_directory_nodes(version_id, project_id, nodes_with_tree)
            self.dao.set_active_directory_version(project_id, version_id)
            
            # 更新 run 状态
            if run_id:
                self.dao.update_run(
                    run_id,
                    "success",
                    progress=1.0,
                    message=f"Directory generated: {len(nodes_with_tree)} nodes",
                    result_json=result,
                )
            
            logger.info(f"[DeclareService] generate_directory success project_id={project_id} nodes={len(nodes_with_tree)}")
            
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
    
    def autofill_sections(
        self,
        project_id: str,
        model_id: Optional[str],
        run_id: Optional[str] = None,
    ):
        """自动填充所有章节（同步入口）"""
        from app.services.db.postgres import _get_pool
        
        pool = _get_pool()
        extract_v2 = DeclareExtractV2Service(pool, self.llm)
        
        # 获取活跃目录节点
        nodes = self.dao.get_active_directory_nodes(project_id)
        if not nodes:
            raise ValueError("No active directory nodes found")
        
        # 获取申报要求摘要
        requirements = self.dao.get_requirements(project_id)
        requirements_summary = requirements.get("data_json", {}).get("summary", "") if requirements else ""
        
        # 创建章节版本
        version_id = self.dao.create_sections_version(project_id, run_id=run_id)
        
        try:
            for node in nodes:
                node_id = node.get("id")
                node_title = node.get("title", "")
                
                # 自动填充单个章节
                section_result = run_async(extract_v2.autofill_section(
                    project_id=project_id,
                    model_id=model_id,
                    node_title=node_title,
                    requirements_summary=requirements_summary,
                    run_id=run_id,
                ))
                
                # 保存章节
                self.dao.upsert_section(
                    version_id=version_id,
                    project_id=project_id,
                    node_id=node_id,
                    node_title=node_title,
                    content_md=section_result.get("data", {}).get("content_md", ""),
                    evidence_chunk_ids=section_result.get("evidence_chunk_ids", []),
                    retrieval_trace=section_result.get("retrieval_trace", {}),
                )
                
                logger.info(f"[DeclareService] Autofilled section: {node_title}")
            
            # 激活新版本
            self.dao.set_active_sections_version(project_id, version_id)
            
            # 更新 run 状态
            if run_id:
                self.dao.update_run(
                    run_id,
                    "success",
                    progress=1.0,
                    message=f"Sections autofilled: {len(nodes)} sections",
                    result_json={"sections_count": len(nodes)},
                )
            
            logger.info(f"[DeclareService] autofill_sections success project_id={project_id} count={len(nodes)}")
            
        except (ExtractionParseError, ExtractionSchemaError, ValueError) as e:
            logger.error(f"[DeclareService] autofill_sections failed: {e}")
            if run_id:
                self.dao.update_run(
                    run_id,
                    "failed",
                    progress=0.0,
                    message=str(e),
                    result_json={"error": str(e), "error_type": type(e).__name__},
                )
            raise
    
    def generate_document(
        self,
        project_id: str,
        run_id: Optional[str] = None,
    ):
        """生成申报书文档（同步入口）"""
        from app.services.export.declare_docx_exporter import DeclareDocxExporter
        
        try:
            exporter = DeclareDocxExporter(self.dao)
            result = exporter.export(project_id)
            
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

