from __future__ import annotations

import os
from collections.abc import AsyncIterator
from importlib.resources import files
from typing import Annotated

from knowledge_mcp.tracing import (
    configure_langfuse_tracing,
    instrument_asyncpg,
    record_tool_input,
    record_tool_output,
)

# Langfuse must initialize before FastMCP import.
_langfuse = configure_langfuse_tracing()
instrument_asyncpg()

from fastmcp import FastMCP
from fastmcp.apps import AppConfig, ResourceCSP
from fastmcp.server.lifespan import lifespan
from pydantic import Field

from knowledge_mcp.auth import build_mcp_auth, require_mcp_reader
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
    auth=build_mcp_auth(settings),
)


@mcp.tool(
    auth=require_mcp_reader,
    app=AppConfig(resource_uri="ui://knowledge/search-results.html"),
)
async def search_knowledge(
    query: Annotated[str, Field(description="Text to find similar knowledge-base passages for.")],
    top_k: Annotated[int, Field(ge=1, le=20, description="Results per page (1–20).")] = 5,
    offset: Annotated[int, Field(ge=0, description="Zero-based result offset; use next_offset.")] = 0,
) -> dict:
    """Search knowledge passages by similarity. Page with pagination.next_offset until has_more is false."""
    record_tool_input({"query": query, "top_k": top_k, "offset": offset})
    try:
        result = await search_service.search_knowledge(query=query, top_k=top_k, offset=offset)
    except ValueError as exc:
        output = {"error": str(exc)}
        record_tool_output(output)
        return output
    except Exception as exc:  # noqa: BLE001 - return LLM-actionable errors
        output = {"error": str(exc)}
        record_tool_output(output)
        return output
    output = result.model_dump()
    record_tool_output(output)
    return output


@mcp.resource(
    "ui://knowledge/search-results.html",
    mime_type="text/html;profile=mcp-app",
    auth=require_mcp_reader,
    app=AppConfig(
        csp=ResourceCSP(connect_domains=[], resource_domains=[], frame_domains=[], base_uri_domains=[]),
    ),
)
def search_results_app() -> str:
    """Self-contained knowledge search results and document detail interface."""
    return files("knowledge_mcp").joinpath("static/search-results.html").read_text(encoding="utf-8")


@mcp.tool(auth=require_mcp_reader)
async def get_document(document_id: str) -> dict:
    """Fetch the document chunk identified by a search_knowledge result id."""
    record_tool_input({"document_id": document_id})
    try:
        document = await search_service.get_document(document_id=document_id)
    except ValueError as exc:
        output = {"error": str(exc)}
        record_tool_output(output)
        return output
    except Exception as exc:  # noqa: BLE001
        output = {"error": str(exc)}
        record_tool_output(output)
        return output
    if document is None:
        output = {"error": f"Document {document_id} was not found."}
        record_tool_output(output)
        return output
    output = document.model_dump()
    record_tool_output(output)
    return output


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
