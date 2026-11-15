from __future__ import annotations

from pydantic import BaseModel, Field


class SearchHit(BaseModel):
    document_id: str
    title: str
    excerpt: str
    source: str | None = None
    similarity: float = Field(ge=-1.0, le=1.0)


class SearchPagination(BaseModel):
    offset: int = Field(default=0, ge=0)
    page_size: int = Field(default=5, ge=1, le=20)
    has_more: bool = False
    next_offset: int | None = None


class SearchResult(BaseModel):
    query: str
    hits: list[SearchHit]
    pagination: SearchPagination = Field(default_factory=SearchPagination)


class DocumentDetail(BaseModel):
    document_id: str
    title: str
    content: str
    source: str | None = None
