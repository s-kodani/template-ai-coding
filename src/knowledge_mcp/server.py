from __future__ import annotations

import os
from collections.abc import AsyncIterator

from knowledge_mcp.tracing import (
    configure_langfuse_tracing,
    instrument_asyncpg,
    record_tool_input,
)

# Langfuse must initialize before FastMCP import.
_langfuse = configure_langfuse_tracing()
instrument_asyncpg()

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan

from knowledge_mcp.config import get_settings
from knowledge_mcp.embedding import EmbeddingClient
from knowledge_mcp.repository import VectorRepository
from knowledge_mcp.service import SearchService

settings = get_settings()
embedding_client = EmbeddingClient(settings)
repository = VectorRepository(settings.database_url, settings.db_timeout)
search_service = SearchService(embedding_client, repository)


@lifespan
async def app_lifespan(_server: FastMCP) -> AsyncIterator[None]:
    await repository.connect()
    try:
        yield None
    finally:
        await repository.close()
        await embedding_client.aclose()
        if _langfuse is not None:
            _langfuse.flush()


mcp = FastMCP(
    name="knowledge-mcp",
    instructions=(
        "Search a local knowledge base with vector similarity and fetch documents by id."
    ),
    lifespan=app_lifespan,
)


@mcp.tool
async def search_knowledge(query: str, top_k: int = 5) -> dict:
    """Search the knowledge base for passages similar to the query."""
    record_tool_input({"query": query, "top_k": top_k})
    try:
        result = await search_service.search_knowledge(query=query, top_k=top_k)
    except ValueError as exc:
        return {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001 - return LLM-actionable errors
        return {"error": str(exc)}
    return result.model_dump()


@mcp.tool
async def get_document(document_id: str) -> dict:
    """Fetch a full document by id returned from search_knowledge."""
    record_tool_input({"document_id": document_id})
    try:
        document = await search_service.get_document(document_id=document_id)
    except ValueError as exc:
        return {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
    if document is None:
        return {"error": f"Document {document_id} was not found."}
    return document.model_dump()


def main() -> None:
    os.environ.setdefault("FASTMCP_STATELESS_HTTP", "true")
    os.environ.setdefault("FASTMCP_TELEMETRY_MODE", "native")
    mcp.run(
        transport="http",
        host=settings.mcp_host,
        port=settings.mcp_port,
        path=settings.mcp_path,
    )


if __name__ == "__main__":
    main()
