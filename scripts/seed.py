from __future__ import annotations

import asyncio

from knowledge_mcp.chunk_ids import parent_document_id
from knowledge_mcp.config import Settings
from knowledge_mcp.embedding import EmbeddingClient
from knowledge_mcp.repository import VectorRepository

FIXTURES: list[dict[str, str]] = [
    {
        "title": "Architecture Overview",
        "source": "docs/current/architecture.md",
        "content": (
            "The system uses FastMCP over Streamable HTTP for vector search, "
            "PostgreSQL with pgvector for embeddings, Chainlit as the chat UI, "
            "and Langfuse for distributed tracing."
        ),
    },
    {
        "title": "MCP Tools",
        "source": "docs/current/features/api.md",
        "content": (
            "Available MCP tools are search_knowledge for semantic search and "
            "get_document for fetching a full document by id."
        ),
    },
    {
        "title": "Tracing",
        "source": "docs/current/infrastructure.md",
        "content": (
            "Trace context propagates through MCP _meta using FastMCP native telemetry. "
            "Chainlit creates the root chat.turn span and MCP server spans attach as children."
        ),
    },
]


async def seed(settings: Settings) -> None:
    embedding_client = EmbeddingClient(settings)
    repository = VectorRepository(settings.host_database_url, settings.db_timeout)
    await repository.connect()

    try:
        for fixture in FIXTURES:
            vector = await embedding_client.embed(fixture["content"])
            await repository.upsert_document(
                title=fixture["title"],
                content=fixture["content"],
                source=fixture["source"],
                embedding=vector,
                document_id=parent_document_id(fixture["source"]),
                chunk_index=0,
                metadata={},
            )
        count = await repository.count_documents()
        print(f"Seeded {count} documents.")
    finally:
        await repository.close()
        await embedding_client.aclose()


def main() -> None:
    from knowledge_mcp.config import get_settings

    asyncio.run(seed(get_settings()))


if __name__ == "__main__":
    main()
