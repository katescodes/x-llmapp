from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends

from app.schemas.embedding_provider import (
    EmbeddingProviderIn,
    EmbeddingProviderStored,
    EmbeddingProviderUpdate,
)
from app.services.embedding_provider_store import get_embedding_store
from app.services.embedding.http_embedding_client import embed_texts
from app.models.user import TokenData
from app.utils.auth import get_current_user
from app.utils.permission import require_permission

router = APIRouter(prefix="/api/settings/embedding-providers", tags=["embedding-providers"])


def _sanitize(provider: EmbeddingProviderStored, is_default: bool) -> dict:
    data = provider.model_dump()
    data["has_api_key"] = bool(provider.api_key)
    data.pop("api_key", None)
    data["is_default"] = is_default
    return data


@router.get("")
def list_providers(current_user: TokenData = Depends(require_permission("system.embedding"))):
    """
    获取Embedding提供商列表
    
    权限要求：system.embedding
    """
    store = get_embedding_store()
    default_id = store._default_id  # pylint: disable=protected-access
    providers = [_sanitize(p, p.id == default_id) for p in store.list_providers()]
    return providers


@router.post("")
def create_provider(
    payload: EmbeddingProviderIn,
    current_user: TokenData = Depends(require_permission("system.embedding"))
):
    """
    创建Embedding提供商配置
    
    权限要求：system.embedding
    """
    store = get_embedding_store()
    try:
        created = store.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _sanitize(created, created.id == store._default_id)  # pylint: disable=protected-access


@router.put("/{provider_id}")
def update_provider(
    provider_id: str, 
    payload: EmbeddingProviderUpdate,
    current_user: TokenData = Depends(require_permission("system.embedding"))
):
    """
    更新Embedding提供商配置
    
    权限要求：system.embedding
    """
    store = get_embedding_store()
    try:
        updated = store.update(provider_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _sanitize(updated, updated.id == store._default_id)  # pylint: disable=protected-access


@router.delete("/{provider_id}")
def delete_provider(
    provider_id: str,
    current_user: TokenData = Depends(require_permission("system.embedding"))
):
    """
    删除Embedding提供商配置
    
    权限要求：system.embedding
    """
    store = get_embedding_store()
    try:
        store.delete(provider_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "ok"}


@router.post("/{provider_id}/set-default")
def set_default_provider(
    provider_id: str,
    current_user: TokenData = Depends(require_permission("system.embedding"))
):
    """
    设置默认Embedding提供商
    
    权限要求：system.embedding
    """
    store = get_embedding_store()
    try:
        provider = store.set_default(provider_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _sanitize(provider, True)


@router.post("/{provider_id}/test")
async def test_provider(
    provider_id: str,
    current_user: TokenData = Depends(require_permission("system.embedding"))
):
    """
    测试Embedding提供商连接
    
    权限要求：system.embedding
    """
    store = get_embedding_store()
    provider = store.get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Embedding provider 不存在")
    try:
        await embed_texts(["ping"], provider=provider)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"连接失败: {exc}") from exc
    return {"ok": True}

