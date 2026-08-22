from __future__ import annotations

from pydantic import BaseModel, Field


class SearchHit(BaseModel):
    document_id: str
    title: str
    excerpt: str
    source: str | None = None
    similarity: float = Field(ge=0.0, le=1.0)


class SearchResult(BaseModel):
    query: str
    hits: list[SearchHit]


class DocumentDetail(BaseModel):
    document_id: str
    title: str
    content: str
    source: str | None = None
