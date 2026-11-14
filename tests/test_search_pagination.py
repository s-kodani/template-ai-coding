"""Pagination contracts; a missing offset or has-more flag must break these tests."""
from __future__ import annotations

import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID, uuid4

import pytest

from knowledge_mcp.models import SearchHit
from knowledge_mcp.repository import VectorRepository
from knowledge_mcp.service import SearchService


class Embeddings:
    model = "test-embedding"
    dimensions = 3

    async def embed(self, _query: str):
        return [1.0, 0.0, 0.0], None


class RankedDocuments:
    async def search(self, _embedding, top_k, offset=0):
        return [
            SearchHit(document_id=str(i), title=f"Chunk {i}", excerpt="excerpt", similarity=0.9)
            for i in range(offset, min(offset + top_k, 43))
        ]


@pytest.mark.asyncio
async def test_search_page_returns_only_requested_hits_and_next_offset() -> None:
    result = await SearchService(Embeddings(), RankedDocuments()).search_knowledge(
        " tracing ", top_k=5, offset=20
    )

    assert result.query == "tracing"
    assert [hit.document_id for hit in result.hits] == ["20", "21", "22", "23", "24"]
    assert result.pagination.model_dump() == {
        "offset": 20, "page_size": 5, "has_more": True, "next_offset": 25
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("offset, count", [(40, 3), (43, 0), (100, 0)])
async def test_search_last_and_empty_pages_have_no_next_offset(offset, count) -> None:
    result = await SearchService(Embeddings(), RankedDocuments()).search_knowledge(
        "tracing", top_k=5, offset=offset
    )

    assert len(result.hits) == count
    assert result.pagination.offset == offset
    assert result.pagination.has_more is False
    assert result.pagination.next_offset is None


@pytest.mark.asyncio
async def test_offset_defaults_to_first_page_for_existing_clients() -> None:
    result = await SearchService(Embeddings(), RankedDocuments()).search_knowledge(
        "tracing", top_k=5
    )

    assert [hit.document_id for hit in result.hits] == ["0", "1", "2", "3", "4"]
    assert result.pagination.offset == 0


@pytest.mark.asyncio
async def test_negative_offset_is_rejected_before_embedding() -> None:
    class OfflineEmbeddings(Embeddings):
        async def embed(self, _query):
            raise AssertionError("invalid pagination must not call the embedding API")

    with pytest.raises(ValueError, match="offset"):
        await SearchService(OfflineEmbeddings(), RankedDocuments()).search_knowledge(
            "tracing", top_k=5, offset=-1
        )


@pytest.mark.asyncio
async def test_repository_paging_reaches_past_hnsw_default_and_orders_ties() -> None:
    """Opt-in real pgvector check, isolated from application documents."""
    database_url = os.environ.get("PAGINATION_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set PAGINATION_TEST_DATABASE_URL to run the real pgvector contract")
    import asyncpg

    schema = "pagination_" + uuid4().hex
    admin = await asyncpg.connect(database_url)
    repository = None
    try:
        await admin.execute(f'CREATE SCHEMA "{schema}"')
        await admin.execute(
            f'CREATE TABLE "{schema}".documents ('
            'id uuid PRIMARY KEY, title text, content text, source text, embedding vector(3))'
        )
        await admin.executemany(
            f'INSERT INTO "{schema}".documents VALUES ($1, $2, $3, NULL, $4::vector)',
            [(UUID(int=i + 1), f"Chunk {i}", "body", f"[1,{i // 2 / 100},0]")
             for i in range(62)]
            + [(UUID(int=63), "Opposite", "body", "[-1,0,0]")],
        )
        await admin.execute(
            f'CREATE INDEX ON "{schema}".documents USING hnsw (embedding vector_cosine_ops)'
        )
        split = urlsplit(database_url)
        query = dict(parse_qsl(split.query))
        query["search_path"] = schema + ",public"
        isolated_url = urlunsplit(split._replace(query=urlencode(query)))
        repository = VectorRepository(isolated_url, timeout=10)
        await repository.connect()

        hits = await repository.search([1, 0, 0], top_k=20, offset=40)

        assert [hit.document_id for hit in hits] == [str(UUID(int=i)) for i in range(41, 61)]
        last = await repository.search([1, 0, 0], top_k=20, offset=62)
        assert len(last) == 1
        assert last[0].similarity == -1.0
    finally:
        if repository is not None:
            await repository.close()
        await admin.execute(f'DROP SCHEMA "{schema}" CASCADE')
        await admin.close()


def test_cosine_similarity_includes_negative_search_candidates() -> None:
    hit = SearchHit(document_id="opposite", title="Opposite", excerpt="body", similarity=-1.0)
    assert hit.similarity == -1.0
