from pydantic import BaseModel
from typing import List


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str


class SearchResults(BaseModel):
    query: str
    results: List[SearchResult]
