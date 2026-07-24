from pydantic import BaseModel
from typing import List


class SearchResultItem(BaseModel):
    type: str  # "inspection" | "camera"
    id: int
    title: str
    subtitle: str
    link: str


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem]