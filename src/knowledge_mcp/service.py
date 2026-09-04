from __future__ import annotations

from knowledge_mcp.embedding import EmbeddingClient
from knowledge_mcp.models import DocumentDetail, SearchResult
from knowledge_mcp.repository import VectorRepository
from knowledge_mcp.tracing import (
    embedding_observation,
    record_embedding_usage,
    search_span,
)


class SearchService:
    def __init__(
        self,
        embedding_client: EmbeddingClient,
        repository: VectorRepository,
    ) -> None:
        self._embedding_client = embedding_client
        self._repository = repository

    async def search_knowledge(self, query: str, top_k: int) -> SearchResult:
        query = query.strip()
        if not query:
            raise ValueError("query must not be empty")
        if top_k < 1 or top_k > 20:
            raise ValueError("top_k must be between 1 and 20")

        with search_span("search.embed") as span:
            if hasattr(span, "update"):
                span.update(metadata={"search.query_length": len(query)})
            elif hasattr(span, "set_attribute"):
                span.set_attribute("search.query_length", len(query))
            with embedding_observation(
                model=self._embedding_client.model,
                input_length=len(query),
                dimensions=self._embedding_client.dimensions,
            ) as embed_observation:
                embedding, usage = await self._embedding_client.embed(query)
                record_embedding_usage(embed_observation, usage)

        with search_span("search.query") as span:
            hits = await self._repository.search(embedding, top_k)
            if hasattr(span, "update"):
                metadata: dict[str, float | int] = {"search.result_count": len(hits)}
                if hits:
                    metadata["search.top_similarity"] = hits[0].similarity
                span.update(metadata=metadata)
            elif hasattr(span, "set_attribute"):
                span.set_attribute("search.result_count", len(hits))
                if hits:
                    span.set_attribute("search.top_similarity", hits[0].similarity)

        return SearchResult(query=query, hits=hits)

    async def get_document(self, document_id: str) -> DocumentDetail | None:
        document_id = document_id.strip()
        if not document_id:
            raise ValueError("document_id must not be empty")
        with search_span("get_document.fetch") as span:
            document = await self._repository.get_document(document_id)
            if hasattr(span, "update"):
                span.update(
                    metadata={
                        "document.found": document is not None,
                        "document.id_length": len(document_id),
                    }
                )
            elif hasattr(span, "set_attribute"):
                span.set_attribute("document.found", document is not None)
        return document
