from typing import List

from pydantic import BaseModel, Field

from .types import KbCategory


class CaseRecord(BaseModel):
    """Structured representation of a history case entry."""

    id: str
    title: str
    kb_category: KbCategory = Field(default="history_case")
    situation: str
    problem: str
    action: str
    result: str
    lessons: str
    tags: List[str] = Field(default_factory=list)


