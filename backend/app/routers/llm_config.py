from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status

from ..schemas.llm_config import (
    LLMModelIn,
    LLMModelOut,
    LLMModelUpdate,
    LLMTestResponse,
)
from ..services.llm_client import generate_answer_with_model
from ..services.llm_model_store import LLMModelStore, get_llm_store
from app.models.user import TokenData
from app.utils.auth import get_current_user
from app.utils.permission import require_permission

router = APIRouter(prefix="/api/settings/llm-models", tags=["llm-settings"])


def _to_out(store: LLMModelStore, stored) -> LLMModelOut:
    data = store.to_dict(stored)
    return LLMModelOut(**data)


@router.get("", response_model=List[LLMModelOut])
def list_models(
    store=Depends(get_llm_store),
    current_user: TokenData = Depends(require_permission("system.model"))
):
    """
    获取LLM模型列表
    
    权限要求：system.model
    """
    return [_to_out(store, m) for m in store.list_models()]


@router.post("", response_model=LLMModelOut)
def create_model(
    payload: LLMModelIn, 
    store=Depends(get_llm_store),
    current_user: TokenData = Depends(require_permission("system.model"))
):
    """
    创建LLM模型配置
    
    权限要求：system.model
    """
    try:
        created = store.create_model(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _to_out(store, created)


@router.put("/{model_id}", response_model=LLMModelOut)
def update_model(
    model_id: str, 
    payload: LLMModelUpdate, 
    store=Depends(get_llm_store),
    current_user: TokenData = Depends(require_permission("system.model"))
):
    """
    更新LLM模型配置
    
    权限要求：system.model
    """
    try:
        updated = store.update_model(model_id, payload)
    except ValueError as exc:
        msg = str(exc)
        if msg == "模型不存在":
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    return _to_out(store, updated)


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(
    model_id: str, 
    store=Depends(get_llm_store),
    current_user: TokenData = Depends(require_permission("system.model"))
):
    """
    删除LLM模型配置
    
    权限要求：system.model
    """
    try:
        store.delete_model(model_id)
    except ValueError as exc:
        msg = str(exc)
        if msg == "模型不存在":
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=409, detail=msg)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{model_id}/set-default", response_model=LLMModelOut)
def set_default(
    model_id: str, 
    store=Depends(get_llm_store),
    current_user: TokenData = Depends(require_permission("system.model"))
):
    """
    设置默认LLM模型
    
    权限要求：system.model
    """
    try:
        model = store.set_default_model(model_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _to_out(store, model)


@router.post("/{model_id}/test", response_model=LLMTestResponse)
async def test_model(
    model_id: str, 
    store=Depends(get_llm_store),
    current_user: TokenData = Depends(require_permission("system.model"))
):
    """
    测试LLM模型连接
    
    权限要求：system.model
    """
    model_tuple = store.get_model_with_token(model_id)
    if not model_tuple:
        raise HTTPException(status_code=404, detail="模型不存在")
    stored, token = model_tuple

    probe_model = stored.model_copy(
        update={"max_tokens": min(stored.max_tokens, 8)}
    )

    try:
        await generate_answer_with_model(
            system_prompt="[LLM Health Check]",
            user_message="ping",
            history=[],
            model=probe_model,
            api_key=token,
        )
        return LLMTestResponse(ok=True)
    except HTTPException as exc:
        return LLMTestResponse(ok=False, error=str(exc.detail))
    except Exception as exc:
        return LLMTestResponse(ok=False, error=str(exc))
