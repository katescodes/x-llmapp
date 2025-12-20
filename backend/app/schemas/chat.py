from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional

# Import ChatSection from orchestrator to avoid duplicate definitions
from .orchestrator import ChatSection


RoleType = Literal["user", "assistant", "system"]
ChatMode = Literal["normal", "decision", "history_decision"]
DetailLevelType = Literal["brief", "normal", "detailed"]


class Message(BaseModel):
    role: RoleType
    content: str


class UsedModel(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    history: List[Message] = Field(default_factory=list)
    # off | smart | force (兼容旧前端，已废弃)
    search_mode: Optional[Literal["off", "smart", "force"]] = None
    # 指定使用哪个 LLM（key），为空则用默认
    llm_key: Optional[str] = None
    session_id: Optional[str] = None
    mode: ChatMode = "normal"
    # 兼容旧字段：kb_ids
    kb_ids: Optional[List[str]] = None
    kb_mode: Optional[Literal["blend", "only"]] = None
    # 新字段：是否启用联网 + 选中的知识库
    enable_web: Optional[bool] = None
    selected_kb_ids: Optional[List[str]] = None
    # 附件ID列表
    attachment_ids: Optional[List[str]] = None
    # 编排器相关（编排器已默认启用）
    enable_orchestrator: Optional[bool] = True  # 是否启用编排器（默认 True）
    detail_level: Optional[DetailLevelType] = None  # 详尽度设置


class Source(BaseModel):
    id: int
    kb_id: Optional[str] = None
    kb_name: Optional[str] = None
    doc_id: Optional[str] = None
    doc_name: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    score: Optional[float] = None
    snippet: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    sources: List[Source] = []
    llm_key: str
    llm_name: str
    session_id: str
    search_mode: Literal["off", "smart", "force"]
    used_search: bool
    search_queries: List[str] = []
    search_usage_count: Optional[int] = None
    search_usage_warning: Optional[str] = None
    used_model: Optional[UsedModel] = None
    # 编排器相关（新增）
    sections: Optional[List[ChatSection]] = None  # 结构化答案模块（启用编排器时）
    followups: Optional[List[str]] = None  # 可选补充信息提示
    orchestrator_meta: Optional[Dict[str, Any]] = None  # 编排器元数据
