import pytest

from knowledge_mcp.embedding import EmbeddingError
from knowledge_mcp.models import DocumentDetail, SearchHit
from knowledge_mcp.service import SearchService


class FakeEmbeddingClient:
    model = "text-embedding-3-small"
    dimensions = 1536

    def __init__(self, vector: list[float] | None = None, error: Exception | None = None) -> None:
        self.vector = vector or [0.1] * 1536
        self.error = error

    async def embed(self, text: str) -> tuple[list[float], dict[str, int] | None]:
        if self.error:
            raise self.error
        return self.vector, {"total": 1}


class FakeRepository:
    def __init__(
        self,
        hits: list[SearchHit] | None = None,
        document: DocumentDetail | None = None,
        error: Exception | None = None,
    ) -> None:
        self.hits = hits or []
        self.document = document
        self.error = error

    async def search(self, embedding: list[float], top_k: int) -> list[SearchHit]:
        if self.error:
            raise self.error
        return self.hits[:top_k]

    async def get_document(self, document_id: str) -> DocumentDetail | None:
        if self.error:
            raise self.error
        return self.document


@pytest.mark.asyncio
async def test_search_knowledge_returns_hits() -> None:
    hits = [
        SearchHit(
            document_id="doc-1",
            title="Tracing",
            excerpt="Trace context propagates",
            source="docs/infrastructure.md",
            similarity=0.91,
        )
    ]
    service = SearchService(FakeEmbeddingClient(), FakeRepository(hits=hits))

    result = await service.search_knowledge("How does tracing work?", top_k=3)

    assert result.query == "How does tracing work?"
    assert len(result.hits) == 1
    assert result.hits[0].title == "Tracing"


@pytest.mark.asyncio
async def test_search_knowledge_rejects_empty_query() -> None:
    service = SearchService(FakeEmbeddingClient(), FakeRepository())

    with pytest.raises(ValueError, match="query must not be empty"):
        await service.search_knowledge("   ", top_k=5)


@pytest.mark.asyncio
@pytest.mark.parametrize("top_k", [0, 21])
async def test_search_knowledge_rejects_invalid_top_k(top_k: int) -> None:
    service = SearchService(FakeEmbeddingClient(), FakeRepository())

    with pytest.raises(ValueError, match="top_k must be between 1 and 20"):
        await service.search_knowledge("hello", top_k=top_k)


@pytest.mark.asyncio
async def test_search_knowledge_surfaces_embedding_error() -> None:
    service = SearchService(
        FakeEmbeddingClient(error=EmbeddingError("missing key")),
        FakeRepository(),
    )

    with pytest.raises(EmbeddingError, match="missing key"):
        await service.search_knowledge("hello", top_k=5)


@pytest.mark.asyncio
async def test_get_document_returns_detail() -> None:
    document = DocumentDetail(
        document_id="doc-1",
        title="Tracing",
        content="Full content",
        source="docs/infrastructure.md",
    )
    service = SearchService(FakeEmbeddingClient(), FakeRepository(document=document))

    result = await service.get_document("doc-1")

    assert result == document


@pytest.mark.asyncio
async def test_get_document_rejects_empty_id() -> None:
    service = SearchService(FakeEmbeddingClient(), FakeRepository())

    with pytest.raises(ValueError, match="document_id must not be empty"):
        await service.get_document("  ")
