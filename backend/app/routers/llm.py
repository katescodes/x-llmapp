from typing import List
from fastapi import APIRouter
from ..schemas.llm import LLMProfileOut
from ..services.llm_client import get_llm_profiles, get_default_llm_key
from ..services.llm_model_store import get_llm_store

router = APIRouter(prefix="/api/llms", tags=["llm"])


@router.get("", response_model=List[LLMProfileOut])
def list_llms() -> List[LLMProfileOut]:
    # 首先尝试使用新的存储系统
    store = get_llm_store()
    models = store.list_models()

    if models:
        # 使用新系统
        default_model = store.get_default_model()
        default_id = default_model.id if default_model else ""
        return [
            LLMProfileOut(
                key=model.id,
                name=model.name,
                description=f"模型: {model.model} @ {model.base_url}",
                is_default=(model.id == default_id),
            )
            for model in models
        ]

    # fallback到旧系统
    profiles = get_llm_profiles()
    default_key = get_default_llm_key()
    items: List[LLMProfileOut] = []

    for key, profile in profiles.items():
        items.append(
            LLMProfileOut(
                key=key,
                name=profile.display_name,
                description=f"模型: {profile.model} @ {profile.base_url}",
                is_default=(key == default_key),
            )
        )

    return items
