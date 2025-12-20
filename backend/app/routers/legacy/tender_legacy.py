"""
DEPRECATED: Legacy tender APIs. Disabled by default.

These APIs use the old KB-based system (kb_documents/kb_chunks/tender_project_documents).
They are kept for backward compatibility but should not be used in new code.

To enable: set LEGACY_TENDER_APIS_ENABLED=true (not recommended)
"""
from fastapi import APIRouter, Request

from app.services.dao.tender_dao import TenderDAO
from app.services.db.postgres import get_pool as _get_pool

router = APIRouter()


@router.get("/projects/{project_id}/documents")
def list_legacy_documents(project_id: str, request: Request):
    """
    列出项目文档绑定（兼容旧 API）
    
    DEPRECATED: This uses the legacy tender_project_documents table.
    New code should use /projects/{project_id}/assets instead.
    """
    dao = TenderDAO(_get_pool(request))
    return dao.list_project_documents(project_id)

