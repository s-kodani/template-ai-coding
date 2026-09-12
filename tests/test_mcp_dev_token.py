from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from scripts.mcp_dev_token import TARGET_SCOPES, main, resolve_scope


def test_resolve_scope_uses_target_defaults() -> None:
    assert resolve_scope(target="knowledge", scope=None) == "mcp-tools"
    assert resolve_scope(target="web-search", scope=None) == "web-search-mcp-tools"


def test_resolve_scope_allows_override() -> None:
    assert resolve_scope(target="knowledge", scope="custom-scope") == "custom-scope"


def test_resolve_scope_rejects_unknown_target() -> None:
    with pytest.raises(SystemExit):
        resolve_scope(target="unknown", scope=None)


@patch("scripts.mcp_dev_token.httpx.Client")
def test_main_exchanges_with_web_search_scope(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    password_response = MagicMock(status_code=200)
    password_response.json.return_value = {"access_token": "chainlit-token"}
    exchange_response = MagicMock(status_code=200)
    exchange_response.json.return_value = {"access_token": "mcp-token"}
    mock_client.post.side_effect = [password_response, exchange_response]

    with patch("sys.argv", ["mcp_dev_token.py", "--target", "web-search", "--username", "dev2"]):
        exit_code = main()

    assert exit_code == 0
    exchange_call = mock_client.post.call_args_list[1]
    assert exchange_call.kwargs["data"]["scope"] == TARGET_SCOPES["web-search"]
    assert "audience" not in exchange_call.kwargs["data"]


@patch("scripts.mcp_dev_token.httpx.Client")
def test_main_exchanges_with_knowledge_scope_by_default(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    password_response = MagicMock(status_code=200)
    password_response.json.return_value = {"access_token": "chainlit-token"}
    exchange_response = MagicMock(status_code=200)
    exchange_response.json.return_value = {"access_token": "mcp-token"}
    mock_client.post.side_effect = [password_response, exchange_response]

    with patch("sys.argv", ["mcp_dev_token.py"]):
        exit_code = main()

    assert exit_code == 0
    exchange_call = mock_client.post.call_args_list[1]
    assert exchange_call.kwargs["data"]["scope"] == TARGET_SCOPES["knowledge"]
