from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowledge_mcp import tracing


def test_sanitize_tool_output_truncates_document_content() -> None:
    long_content = "x" * 600
    sanitized = tracing.sanitize_tool_output_for_trace(
        {
            "document_id": "doc-1",
            "title": "Example",
            "content": long_content,
            "source": "fixture",
        }
    )

    assert sanitized["document_id"] == "doc-1"
    assert sanitized["title"] == "Example"
    assert sanitized["source"] == "fixture"
    assert len(sanitized["content"]) < len(long_content)
    assert sanitized["content"].endswith("…")


def test_sanitize_tool_output_leaves_search_results_unchanged() -> None:
    output = {
        "query": "architecture",
        "hits": [
            {
                "document_id": "doc-1",
                "title": "Architecture",
                "excerpt": "System design overview",
                "source": "fixture",
                "similarity": 0.91,
            }
        ],
    }

    assert tracing.sanitize_tool_output_for_trace(output) == output


def test_record_tool_output_updates_current_span_when_enabled() -> None:
    output = {"query": "tracing", "hits": []}
    mock_client = MagicMock()
    tracing._langfuse_enabled = True

    with patch.object(tracing, "get_client", return_value=mock_client):
        tracing.record_tool_output(output)

    mock_client.update_current_span.assert_called_once_with(output=output)


def test_record_tool_output_noops_when_disabled() -> None:
    tracing._langfuse_enabled = False

    with patch.object(tracing, "get_client") as get_client:
        tracing.record_tool_output({"query": "tracing", "hits": []})

    get_client.assert_not_called()


@pytest.mark.asyncio
async def test_search_knowledge_records_tool_output_on_server_span() -> None:
    from knowledge_mcp import server
    from knowledge_mcp.models import SearchHit, SearchResult

    fake_result = SearchResult(
        query="tracing",
        hits=[
            SearchHit(
                document_id="doc-1",
                title="Tracing",
                excerpt="Trace context propagates",
                source="fixture",
                similarity=0.91,
            )
        ],
    )
    tracing._langfuse_enabled = True
    mock_client = MagicMock()

    with patch.object(server.repository, "connect", AsyncMock()), patch.object(
        server.repository, "close", AsyncMock()
    ), patch.object(server.embedding_client, "aclose", AsyncMock()), patch.object(
        server.search_service, "search_knowledge", AsyncMock(return_value=fake_result)
    ), patch.object(tracing, "get_client", return_value=mock_client):
        from fastmcp import Client

        async with Client(server.mcp) as client:
            await client.call_tool("search_knowledge", {"query": "tracing", "top_k": 3})

    output_calls = [
        call.kwargs["output"]
        for call in mock_client.update_current_span.call_args_list
        if call.kwargs.get("output") is not None
    ]
    assert output_calls
    assert output_calls[-1]["query"] == "tracing"
    assert output_calls[-1]["hits"][0]["document_id"] == "doc-1"
