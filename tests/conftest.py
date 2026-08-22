"""Shared pytest configuration for unit tests."""

from __future__ import annotations

import os

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

# Keep unit tests on the in-memory OTel exporter; do not initialize Langfuse SDK.
os.environ["LANGFUSE_TRACING_ENABLED"] = "false"
os.environ["LANGFUSE_PUBLIC_KEY"] = ""
os.environ["LANGFUSE_SECRET_KEY"] = ""
os.environ.setdefault("FASTMCP_TELEMETRY_MODE", "native")


@pytest.fixture(scope="session")
def otel_span_exporter() -> InMemorySpanExporter:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return exporter


@pytest.fixture
def span_exporter(otel_span_exporter: InMemorySpanExporter) -> InMemorySpanExporter:
    otel_span_exporter.clear()
    yield otel_span_exporter
    otel_span_exporter.clear()
