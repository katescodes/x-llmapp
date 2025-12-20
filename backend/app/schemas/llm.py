from pydantic import BaseModel
from typing import Optional


class LLMProfileOut(BaseModel):
    key: str
    name: str
    description: Optional[str] = None
    is_default: bool = False
