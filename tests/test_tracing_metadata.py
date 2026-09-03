"""Tests for Langfuse trace attribute helpers."""

from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from knowledge_mcp import tracing


def test_configure_langfuse_passes_environment_and_release(monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_TRACING_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_TRACING_ENVIRONMENT", "staging")
    monkeypatch.setenv("LANGFUSE_RELEASE", "abc123")

    captured: dict = {}

    def fake_langfuse(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(tracing, "Langfuse", fake_langfuse)
    tracing._langfuse_client = None
    tracing._langfuse_enabled = False

    try:
        client = tracing.configure_langfuse_tracing()
        assert client is not None
        assert captured["environment"] == "staging"
        assert captured["release"] == "abc123"
    finally:
        tracing._langfuse_client = None
        tracing._langfuse_enabled = False


def test_chat_trace_attributes_noops_when_disabled() -> None:
    tracing._langfuse_enabled = False
    with tracing.chat_trace_attributes(
        user_id="user-1",
        session_id="sess-1",
        chat_model="gpt-4o-mini",
    ):
        pass


def test_chat_trace_attributes_uses_propagate_attributes(monkeypatch) -> None:
    tracing._langfuse_enabled = True
    mock_propagate = MagicMock(return_value=nullcontext())
    monkeypatch.setattr(tracing, "propagate_attributes", mock_propagate)

    with tracing.chat_trace_attributes(
        user_id="kc-sub",
        session_id="sess-1",
        chat_model="gpt-4o-mini",
        tags=["chainlit", "gateway"],
    ):
        pass

    mock_propagate.assert_called_once_with(
        user_id="kc-sub",
        session_id="sess-1",
        tags=["chainlit", "gateway"],
        metadata={"component": "chainlit", "chat_model": "gpt-4o-mini"},
        as_baggage=True,
    )
    tracing._langfuse_enabled = False


def test_tool_observation_passes_metadata() -> None:
    tracing._langfuse_enabled = True
    mock_client = MagicMock()
    mock_observation = MagicMock()
    mock_client.start_as_current_observation.return_value.__enter__ = MagicMock(
        return_value=mock_observation
    )
    mock_client.start_as_current_observation.return_value.__exit__ = MagicMock(return_value=False)

    with (
        patch.object(tracing, "get_client", return_value=mock_client),
        tracing.tool_observation(
            "search_knowledge",
            {"query": "hello"},
            metadata={"tool.route": "gateway"},
        ),
    ):
        pass

    mock_client.start_as_current_observation.assert_called_once_with(
        as_type="tool",
        name="search_knowledge",
        input={"query": "hello"},
        metadata={"tool.route": "gateway"},
    )
    tracing._langfuse_enabled = False


def test_record_generation_result_updates_generation() -> None:
    tracing._langfuse_enabled = True
    mock_client = MagicMock()
    response = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    )

    with patch.object(tracing, "get_client", return_value=mock_client):
        tracing.record_generation_result(response, model="gpt-4o-mini")

    mock_client.update_current_generation.assert_called_once_with(
        model="gpt-4o-mini",
        usage_details={"input": 10, "output": 5, "total": 15},
        metadata={"tool_choice": "auto"},
    )
    tracing._langfuse_enabled = False
