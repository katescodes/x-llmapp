from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict, field_validator


class LLMModelIn(BaseModel):
    """输入 schema，用于创建/更新"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=100)
    base_url: str = Field(..., min_length=1)
    endpoint_path: str = Field("/v1/chat/completions")
    model: str = Field(..., min_length=1, max_length=100)
    api_key: Optional[str] = None
    temperature: float = Field(0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(16000, gt=0)
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    presence_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0)
    frequency_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0)
    timeout_ms: int = Field(30000, gt=0)
    extra_headers: Optional[Dict[str, Any]] = None

    @field_validator("extra_headers")
    @classmethod
    def validate_jsonable(cls, v: Optional[Dict[str, Any]]):
        if v is None:
            return v
        # Pydantic 能够序列化任意可 JSON 的对象；这里简单确保可转换为 dict
        dict(v)  # may raise TypeError
        return v


class LLMModelUpdate(BaseModel):
    """用于 PATCH/PUT"""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    base_url: Optional[str] = Field(None, min_length=1)
    endpoint_path: Optional[str] = Field(None)
    model: Optional[str] = Field(None, min_length=1, max_length=100)
    api_key: Optional[str] = Field(
        None, description="为 None/空串表示不修改 token，传值则覆盖"
    )
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    presence_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0)
    frequency_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0)
    timeout_ms: Optional[int] = Field(None, gt=0)
    extra_headers: Optional[Dict[str, Any]] = None

    @field_validator("extra_headers")
    @classmethod
    def validate_jsonable(cls, v: Optional[Dict[str, Any]]):
        if v is None:
            return v
        dict(v)
        return v


class LLMModelStored(LLMModelIn):
    """持久化模型，包含敏感字段"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_default: bool = False


class LLMModelOut(BaseModel):
    """对外响应模型（无敏感字段）"""

    id: str
    name: str
    base_url: str
    endpoint_path: str
    model: str
    temperature: float
    max_tokens: int
    top_p: Optional[float]
    presence_penalty: Optional[float]
    frequency_penalty: Optional[float]
    timeout_ms: int
    extra_headers: Optional[Dict[str, Any]]
    is_default: bool
    created_at: datetime
    updated_at: datetime
    has_token: bool = False
    token_hint: Optional[str] = None


class LLMTestResponse(BaseModel):
    ok: bool
    error: Optional[str] = None
