from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field


class Anchor(BaseModel):
    text: str
    type: Literal["id", "amount", "date", "name", "quoted", "other"] = "other"
    strength: Literal["strong", "medium", "weak"] = "medium"


class AnswerStyle(BaseModel):
    language: Literal["zh-CN", "en", "auto"] = "zh-CN"
    format: Literal["paragraph", "bullets"] = "paragraph"
    focus: List[str] = Field(default_factory=list)


class IntentPlan(BaseModel):
    task_type: Literal["web_search", "kb_qa", "mixed", "chit_chat"] = "kb_qa"
    need_web: bool = False
    freshness_days: Literal[0, 7, 30, 365] = 0
    anchors: List[Anchor] = Field(default_factory=list)
    queries: List[str] = Field(default_factory=list)
    answer_style: AnswerStyle = AnswerStyle()

