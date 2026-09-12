from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from web_search_mcp.auth import (
    WEB_SEARCH_MCP_TOOLS_SCOPE,
    WEB_SEARCH_READER_ROLE,
    build_mcp_auth,
    require_web_search_reader,
)
from web_search_mcp.config import Settings
from web_search_mcp.search_client import BraveSearchClient, _parse_hits


def test_parse_hits_extracts_title_url_snippet() -> None:
    payload = {
        "web": {
            "results": [
                {
                    "title": "Example",
                    "url": "https://example.com",
                    "description": "An example page",
                }
            ]
        }
    }
    hits = _parse_hits(payload, limit=5)
    assert len(hits) == 1
    assert hits[0].title == "Example"
    assert hits[0].url == "https://example.com"
    assert hits[0].snippet == "An example page"


@pytest.mark.asyncio
async def test_search_web_rejects_empty_query() -> None:
    client = BraveSearchClient(api_key="test-key", base_url="https://example.test", timeout=1.0)
    with pytest.raises(ValueError, match="query must not be empty"):
        await client.search_web(query="  ")


@pytest.mark.asyncio
async def test_search_web_requires_api_key() -> None:
    client = BraveSearchClient(api_key="", base_url="https://example.test", timeout=1.0)
    with pytest.raises(ValueError, match="BRAVE_SEARCH_API_KEY"):
        await client.search_web(query="hello")


@pytest.mark.asyncio
async def test_search_web_calls_brave_api() -> None:
    response = httpx.Response(
        200,
        json={
            "web": {
                "results": [
                    {
                        "title": "Brave",
                        "url": "https://brave.com",
                        "description": "Privacy browser",
                    }
                ]
            }
        },
        request=httpx.Request("GET", "https://api.search.brave.com/res/v1/web/search"),
    )
    http_client = AsyncMock()
    http_client.get = AsyncMock(return_value=response)

    client = BraveSearchClient(
        api_key="secret",
        base_url="https://api.search.brave.com/res/v1/web/search",
        timeout=1.0,
        client=http_client,
    )
    result = await client.search_web(query="privacy browser", count=3)

    assert result.query == "privacy browser"
    assert len(result.results) == 1
    assert result.results[0].title == "Brave"
    http_client.get.assert_awaited_once()
    call_kwargs = http_client.get.await_args.kwargs
    assert call_kwargs["headers"]["X-Subscription-Token"] == "secret"
    assert call_kwargs["params"]["q"] == "privacy browser"


def test_require_web_search_reader_checks_role() -> None:
    ctx = MagicMock()
    ctx.token = MagicMock(claims={"realm_access": {"roles": [WEB_SEARCH_READER_ROLE]}})
    assert require_web_search_reader(ctx) is True

    ctx.token.claims = {"realm_access": {"roles": ["other-role"]}}
    assert require_web_search_reader(ctx) is False


def test_build_mcp_auth_uses_web_search_scope() -> None:
    settings = Settings(
        mcp_jwks_uri="http://localhost:8081/realms/knowledge/protocol/openid-connect/certs",
        mcp_audience="http://localhost:8001/mcp",
    )
    auth = build_mcp_auth(settings)
    assert auth is not None
    assert WEB_SEARCH_MCP_TOOLS_SCOPE in auth._scopes_supported
