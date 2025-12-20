from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..schemas.kb import (
    DocumentOut,
    ImportResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    KnowledgeBaseUpdate,
)
from ..services import kb_service
from ..schemas.types import KbCategory

router = APIRouter(prefix="/api/kb", tags=["knowledge-base"])


@router.get("", response_model=List[KnowledgeBaseOut])
def list_kbs():
    return kb_service.list_kbs()


@router.post("", response_model=KnowledgeBaseOut)
def create_kb(payload: KnowledgeBaseCreate):
    kb_id = kb_service.create_kb(payload.name, payload.description or "", payload.category_id)
    return kb_service.get_kb_or_raise(kb_id)


@router.put("/{kb_id}", response_model=KnowledgeBaseOut)
def update_kb(kb_id: str, payload: KnowledgeBaseUpdate):
    try:
        kb_service.update_kb(kb_id, payload.name, payload.description, payload.category_id)
    except ValueError as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return kb_service.get_kb_or_raise(kb_id)


@router.delete("/{kb_id}")
def delete_kb(kb_id: str):
    try:
        kb_service.delete_kb(kb_id)
    except ValueError as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "ok"}


@router.get("/{kb_id}/docs", response_model=List[DocumentOut])
def list_docs(kb_id: str):
    try:
        docs = kb_service.list_documents(kb_id)
    except ValueError as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return docs


@router.delete("/{kb_id}/docs/{doc_id}")
def delete_doc(kb_id: str, doc_id: str):
    try:
        kb_service.delete_document(kb_id, doc_id)
    except ValueError as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "ok"}


@router.post("/{kb_id}/import", response_model=ImportResponse)
async def import_docs(
    kb_id: str,
    files: List[UploadFile] = File(...),
    kb_category: KbCategory = Form("general_doc"),
):
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个文件")
    results = []
    for upload in files:
        try:
            data = await upload.read()
            if not data:
                results.append(
                    {
                        "filename": upload.filename or "unknown",
                        "status": "failed",
                        "error": "文件内容为空",
                    }
                )
                continue
            result = await kb_service.import_document(
                kb_id,
                upload.filename or "unnamed",
                data,
                kb_category=kb_category,
            )
            results.append(result)
        except ValueError as exc:
            results.append(
                {
                    "filename": upload.filename or "unknown",
                    "status": "failed",
                    "error": str(exc),
                }
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "filename": upload.filename or "unknown",
                    "status": "failed",
                    "error": f"导入失败: {exc}",
                }
            )
    return ImportResponse(items=results)

