"""
Debug endpoints for development and testing.

Only enabled when DEBUG=true or ENV=dev.
"""
import os
from typing import Optional
from fastapi import APIRouter, HTTPException

from ..config import get_feature_flags
from ..core.cutover import get_cutover_config, CutoverMode

# Only create router if debug is enabled
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
ENV = os.getenv("ENV", "production").lower()

router = APIRouter(prefix="/api/_debug", tags=["debug"])


@router.get("/flags")
def get_flags():
    """Get all feature flags (existing implementation - keeping compatible)"""
    flags = get_feature_flags()
    return {
        "feature_flags": flags.model_dump(),
        "environment": "development" if (DEBUG or ENV == "dev") else ENV,
        "note": "All flags are disabled by default to ensure backward compatibility"
    }


@router.get("/cutover")
def get_cutover(project_id: Optional[str] = None):
    """
    Get cutover configuration.
    
    If project_id provided, also compute effective modes for that project.
    """
    config = get_cutover_config()
    result = {
        "config": config.to_dict(),
    }
    
    if project_id:
        result["project_id"] = project_id
        result["should_cutover"] = config.should_cutover(project_id)
        result["effective_modes"] = {
            "retrieval": config.get_mode("retrieval", project_id).value,
            "ingest": config.get_mode("ingest", project_id).value,
            "extract": config.get_mode("extract", project_id).value,
            "review": config.get_mode("review", project_id).value,
            "rules": config.get_mode("rules", project_id).value,
        }
    
    return result


@router.get("/health")
def debug_health():
    """Debug health check"""
    return {
        "status": "ok",
        "debug_mode": DEBUG or ENV == "dev",
        "env": ENV
    }


@router.get("/docstore/assets/{asset_id}")
def get_asset_docstore_info(asset_id: str):
    """
    获取资产的 DocStore 信息
    
    用于验证 DOCSTORE_DUALWRITE 是否正常工作
    """
    from ..services.dao.tender_dao import TenderDAO
    from ..services.db.postgres import _get_pool
    from ..platform.docstore.service import DocStoreService
    
    pool = _get_pool()
    dao = TenderDAO(pool)
    docstore = DocStoreService(pool)
    
    # 获取资产信息
    asset = dao.get_asset_by_id(asset_id)
    if not asset:
        return {
            "asset_id": asset_id,
            "found": False,
            "message": "Asset not found"
        }
    
    # 从 meta_json 中获取 doc_version_id
    meta_json = asset.get("meta_json") or {}
    doc_version_id = meta_json.get("doc_version_id")
    
    result = {
        "asset_id": asset_id,
        "found": True,
        "kind": asset.get("kind"),
        "filename": asset.get("filename"),
        "doc_version_id": doc_version_id,
        "ingest_v2_status": meta_json.get("ingest_v2_status"),
        "ingest_v2_segments": meta_json.get("ingest_v2_segments"),
        "ingest_v2_error": meta_json.get("ingest_v2_error"),
    }
    
    # 如果有 doc_version_id，查询 DocStore 信息
    if doc_version_id:
        version_info = docstore.get_document_version(doc_version_id)
        segments_count = docstore.count_segments_by_version(doc_version_id)
        
        result["docstore"] = {
            "version_found": version_info is not None,
            "version_info": version_info,
            "segments_count": segments_count
        }
    else:
        result["docstore"] = {
            "message": "No doc_version_id in meta_json (DOCSTORE_DUALWRITE may be disabled)"
        }
    
    return result


@router.get("/ingest/v2")
def debug_ingest_v2(asset_id: Optional[str] = None):
    """
    查看 IngestV2 状态
    
    用于验证 INGEST_MODE=SHADOW 是否正常工作
    """
    from ..services.dao.tender_dao import TenderDAO
    from ..services.db.postgres import _get_pool
    from ..platform.docstore.service import DocStoreService
    from ..services.vectorstore.milvus_docseg_store import milvus_docseg_store
    
    pool = _get_pool()
    dao = TenderDAO(pool)
    docstore = DocStoreService(pool)
    
    if not asset_id:
        return {
            "message": "Please provide asset_id parameter",
            "example": "/api/_debug/ingest/v2?asset_id=ta_xxx"
        }
    
    # 获取资产信息
    asset = dao.get_asset_by_id(asset_id)
    if not asset:
        return {
            "asset_id": asset_id,
            "found": False,
            "message": "Asset not found"
        }
    
    meta_json = asset.get("meta_json") or {}
    doc_version_id = meta_json.get("doc_version_id")
    
    result = {
        "asset_id": asset_id,
        "found": True,
        "kind": asset.get("kind"),
        "filename": asset.get("filename"),
        "ingest_v2": {
            "status": meta_json.get("ingest_v2_status", "not_run"),
        "doc_version_id": doc_version_id,
            "segments_count": meta_json.get("ingest_v2_segments", 0),
            "error": meta_json.get("ingest_v2_error"),
        }
    }
    
    # 如果有 doc_version_id，查询实际写入情况
    if doc_version_id:
        segments_count = docstore.count_segments_by_version(doc_version_id)
        result["ingest_v2"]["actual_segments_in_db"] = segments_count
        
        # 查询 Milvus（简单检查是否有数据）
        try:
            # 无法直接查询 Milvus 的总数，这里仅标记已实现
            result["ingest_v2"]["milvus_collection"] = "doc_segments_v1"
            result["ingest_v2"]["milvus_note"] = "Use Milvus client to check vector count"
        except Exception as e:
            result["ingest_v2"]["milvus_error"] = str(e)
    
    return result


@router.get("/retrieval/test")
async def test_new_retrieval(
    query: str,
    project_id: str,
    doc_types: Optional[str] = None,
    top_k: int = 5,
    override_mode: Optional[str] = None  # Dev-only: 强制覆盖模式
):
    """
    测试检索器
    
    用于验证检索器能否正常工作，并返回真实的 provider 和 cutover 信息
    
    Args:
        override_mode: (Dev-only) 强制覆盖 RETRIEVAL_MODE，用于测试
                       仅在 ENV=dev 时生效
    """
    import time
    import os
    from ..platform.retrieval.facade import RetrievalFacade
    from ..services.db.postgres import _get_pool
    from ..services.embedding_provider_store import get_embedding_store
    from ..core.cutover import get_cutover_config, CutoverMode
    
    pool = _get_pool()
    
    # 获取 cutover 配置
    cutover = get_cutover_config()
    resolved_mode = cutover.get_mode("retrieval", project_id).value
    
    # Dev-only: 支持 override_mode
    if override_mode and os.getenv("ENV", "production") == "dev":
        try:
            resolved_mode = CutoverMode(override_mode).value
        except ValueError:
            return {
                "error": f"Invalid override_mode: {override_mode}",
                "valid_modes": ["OLD", "SHADOW", "PREFER_NEW", "NEW_ONLY"]
            }
    
    # 创建 facade（会根据 resolved_mode 选择 retriever）
    retriever = RetrievalFacade(pool)
    
    # 临时覆盖模式（仅用于测试）
    if override_mode and os.getenv("ENV", "production") == "dev":
        # 直接修改 cutover 配置（仅用于此次请求）
        original_mode = cutover.retrieval_mode
        try:
            cutover.retrieval_mode = CutoverMode(override_mode)
        except:
            pass
    
    # 获取 embedding provider
    embedding_store = get_embedding_store()
    embedding_provider = embedding_store.get_default()
    
    if not embedding_provider:
        return {
            "error": "No default embedding provider configured",
            "resolved_mode": resolved_mode,
            "provider_used": "none"
        }
    
    # 解析 doc_types
    doc_types_list = None
    if doc_types:
        doc_types_list = [dt.strip() for dt in doc_types.split(",") if dt.strip()]
    
    # 执行检索
    start_time = time.time()
    provider_used = "unknown"
    try:
        results = await retriever.retrieve(
            query=query,
            project_id=project_id,
            doc_types=doc_types_list,
            embedding_provider=embedding_provider,
            top_k=top_k,
        )
        latency_ms = int((time.time() - start_time) * 1000)
        
        # 根据实际执行的模式判断 provider
        actual_mode = cutover.get_mode("retrieval", project_id).value
        if override_mode:
            actual_mode = resolved_mode
        
        if actual_mode in ("NEW_ONLY", "PREFER_NEW"):
            provider_used = "new"
        elif actual_mode == "OLD":
            provider_used = "legacy"
        elif actual_mode == "SHADOW":
            provider_used = "legacy"  # SHADOW 返回 legacy 结果
        
        top_ids = [r.chunk_id for r in results[:10]]
        
        return {
            "query": query,
            "project_id": project_id,
            "doc_types": doc_types_list,
            "resolved_mode": resolved_mode,
            "provider_used": provider_used,
            "latency_ms": latency_ms,
            "results_count": len(results),
            "top_ids": top_ids,
            "results": [r.to_dict() for r in results],
        }
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        
        # NEW_ONLY 失败时返回可读错误
        error_msg = str(e)
        if resolved_mode == "NEW_ONLY" or (override_mode == "NEW_ONLY"):
            provider_used = "new"
            # 简化错误信息，不返回堆栈
            if "RETRIEVAL_MODE=NEW_ONLY failed" in error_msg:
                error_msg = error_msg.split("(mode=")[0].strip()
        
        return {
            "error": error_msg,
            "error_type": type(e).__name__,
            "query": query,
            "project_id": project_id,
            "doc_types": doc_types_list,
            "resolved_mode": resolved_mode,
            "provider_used": provider_used,
            "latency_ms": latency_ms,
        }


@router.get("/llm/ping")
def check_llm_availability():
    """
    检查 LLM 可用性
    
    用于诊断 LLM 连接问题
    
    行为：
    - MOCK_LLM=true：直接返回 mock 模式（不访问 DB，不访问外部）
    - 否则：发送最小请求（max_tokens=16，timeout=10s），返回真实调用信息
    
    返回：
    {
        "ok": true/false,
        "mode": "mock"/"real",
        "model": "模型名称",  # 仅 real 模式
        "latency_ms": 123,  # 仅 real 模式
        "error": "错误信息"  # 仅失败时
    }
    """
    import time
    import logging
    import traceback
    
    logger = logging.getLogger(__name__)
    
    # 检查 MOCK_LLM 模式
    mock_llm_enabled = os.getenv("MOCK_LLM", "false").lower() in ("true", "1", "yes")
    debug_enabled = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    
    # MOCK_LLM 只在 DEBUG=true 时生效
    if mock_llm_enabled and not debug_enabled:
        logger.warning("[LLM Ping] MOCK_LLM=true but DEBUG=false, treating as real mode")
        mock_llm_enabled = False
    
    # MOCK 模式：直接返回成功（不访问任何资源）
    if mock_llm_enabled:
        logger.info("[LLM Ping] MOCK_LLM=true, returning mock success")
        return {
            "ok": True,
            "mode": "mock",
            "message": "MOCK_LLM enabled, no real LLM call made"
        }
    
    # REAL 模式：发送最小测试请求
    try:
        start_time = time.time()
        
        # 获取 LLM orchestrator（不依赖 llm_models 表查询，只用已初始化的实例）
        from ..main import app
        llm_orchestrator = app.state.llm_orchestrator
        
        if not llm_orchestrator:
            logger.error("[LLM Ping] llm_orchestrator not initialized")
            return {
                "ok": False,
                "mode": "real",
                "error": "LLM orchestrator not initialized in app.state"
            }
        
        # 最小测试请求（max_tokens=16，减少延迟）
        test_messages = [
            {"role": "user", "content": "Respond with: OK"}
        ]
        
        logger.info("[LLM Ping] Sending minimal test request (max_tokens=16)")
        result = llm_orchestrator.chat(
            messages=test_messages,
            max_tokens=16  # 最小化响应，加快测试速度
        )
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        # 提取响应和模型信息
        content = ""
        model = "unknown"
        
        if isinstance(result, dict):
            # OpenAI 格式
            if "choices" in result and result["choices"]:
                msg = result["choices"][0].get("message", {})
                if msg:
                    content = msg.get("content", "")
            if "model" in result:
                model = result["model"]
        
        content_len = len(content) if content else 0
        logger.info(f"[LLM Ping] Success: latency={latency_ms}ms model={model} content_len={content_len}")
        
        return {
            "ok": True,
            "mode": "real",
            "model": model,
            "latency_ms": latency_ms,
            "response_snippet": content[:100] if content else "(empty)"
        }
        
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000) if 'start_time' in locals() else 0
        error_msg = f"{type(e).__name__}: {str(e)}"
        stack_trace = traceback.format_exc()
        
        logger.error(f"[LLM Ping] Failed: {error_msg}")
        logger.error(f"[LLM Ping] Stack trace:\n{stack_trace}")
        
        return {
            "ok": False,
            "mode": "real",
            "latency_ms": latency_ms,
            "error": error_msg,
            "stack": stack_trace
        }


@router.get("/docstore/ready")
def check_docstore_ready(
    project_id: str,
    doc_type: str = "tender"
):
    """
    检查 DocStore 入库是否完成并就绪
    
    用于 smoke 测试等待入库完成
    """
    from ..services.dao.tender_dao import TenderDAO
    from ..services.db.postgres import _get_pool
    from ..platform.docstore.service import DocStoreService
    
    pool = _get_pool()
    dao = TenderDAO(pool)
    docstore = DocStoreService(pool)
    
    # 查找该project下该类型的assets
    assets = dao.list_assets(project_id)
    assets_of_type = [a for a in assets if a.get("kind") == doc_type]
    
    if not assets_of_type:
        return {
            "project_id": project_id,
            "doc_type": doc_type,
            "ready": False,
            "documents": 0,
            "versions": 0,
            "segments": 0,
            "milvus_vectors": None,
            "message": f"No assets of type '{doc_type}' found"
        }
    
    # 统计segments总数
    total_segments = 0
    doc_version_ids = []
    for asset in assets_of_type:
        meta_json = asset.get("meta_json") or {}
        doc_version_id = meta_json.get("doc_version_id")
        if doc_version_id:
            doc_version_ids.append(doc_version_id)
            segments_count = docstore.count_segments_by_version(doc_version_id)
            total_segments += segments_count
    
    # Milvus向量数（简化：标记为null，因为MilvusLite难以直接查询总数）
    milvus_vectors = None
    
    # Ready条件：至少有segments
    ready = total_segments > 0
    
    return {
        "project_id": project_id,
        "doc_type": doc_type,
        "ready": ready,
        "documents": len(assets_of_type),
        "versions": len(doc_version_ids),
        "segments": total_segments,
        "milvus_vectors": milvus_vectors,
        "last_error": None
    }

