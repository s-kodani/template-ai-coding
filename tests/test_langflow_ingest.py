from pathlib import Path
from uuid import uuid5

import httpx
import pytest

from knowledge_mcp.chunk_ids import PARENT_NAMESPACE
from knowledge_mcp.langflow_import import MappedChunk
from knowledge_mcp.langflow_ingest import (
    FILE_COMPONENT_ID,
    INGEST_OUTPUT_COMPONENT,
    LANGFLOW_API_UNREACHABLE,
    LANGFLOW_RUN_TIMEOUT,
    LangflowAPIError,
    LangflowClient,
    UploadedFile,
    build_run_payload,
    extract_upload,
    host_source,
    ingest_files,
    remap_sources,
    resolve_ingest_paths,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ingest" / "sample.md"
MAKEFILE = (ROOT / "infra" / "Makefile").read_text(encoding="utf-8")
ENV_EXAMPLE = (ROOT / ".env.example").read_text(encoding="utf-8")
COMPOSE = (ROOT / "infra" / "langflow" / "compose.yml").read_text(encoding="utf-8")
FLOW = (ROOT / "infra" / "langflow" / "flows" / "Ingest.json").read_text(encoding="utf-8")
QUERY_FLOW = (ROOT / "infra" / "langflow" / "flows" / "QueryPgVector.json").read_text(
    encoding="utf-8"
)
SCRIPT = (ROOT / "scripts" / "run_langflow_ingest.py").read_text(encoding="utf-8")


def test_resolve_ingest_paths_expands_directory_and_skips_hidden(tmp_path: Path) -> None:
    keep = tmp_path / "keep.md"
    keep.write_text("ok", encoding="utf-8")
    (tmp_path / ".hidden.md").write_text("no", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    nested_file = nested / "nested.txt"
    nested_file.write_text("nested", encoding="utf-8")

    resolved = resolve_ingest_paths([tmp_path])

    assert resolved == [keep, nested_file]


def test_resolve_ingest_paths_rejects_empty_directory(tmp_path: Path) -> None:
    with pytest.raises(LangflowAPIError, match="No ingest files"):
        resolve_ingest_paths([tmp_path])


def test_host_source_uses_repo_relative_posix_path() -> None:
    assert host_source(FIXTURE, cwd=ROOT) == "tests/fixtures/ingest/sample.md"


def test_extract_upload_reads_v2_id_and_path() -> None:
    uploaded = extract_upload(
        {
            "id": "file-1",
            "name": "sample",
            "path": "user-1/file-1.md",
            "size": 12,
        }
    )

    assert uploaded == UploadedFile(id="file-1", path="user-1/file-1.md")


def test_build_run_payload_sends_uploaded_path_to_read_file() -> None:
    payload = build_run_payload("user-1/file-1.md")

    assert payload["tweaks"][FILE_COMPONENT_ID]["path"] == ["user-1/file-1.md"]
    assert payload["output_type"] == "any"
    assert payload["output_component"] == INGEST_OUTPUT_COMPONENT
    assert "debug" not in payload.values()


def test_remap_sources_uses_host_path_for_document_id() -> None:
    langflow_source = "07e5b864-e367-4f52-b647-a48035ae7e5e/file-1.md"
    chunk = MappedChunk(
        document_id=uuid5(PARENT_NAMESPACE, langflow_source),
        chunk_index=0,
        title="sample.md",
        content="hello",
        source=langflow_source,
        metadata={"source": langflow_source},
        embedding=[0.1],
    )

    remapped = remap_sources(
        [chunk],
        {
            "sample.md": "data/ingest/sample.md",
            langflow_source: "data/ingest/sample.md",
        },
    )

    assert remapped[0].source == "data/ingest/sample.md"
    assert remapped[0].document_id == uuid5(PARENT_NAMESPACE, "data/ingest/sample.md")
    assert remapped[0].chunk_index == 0


@pytest.mark.asyncio
async def test_ingest_files_uploads_runs_and_deletes_sequentially(tmp_path: Path) -> None:
    first = tmp_path / "a.md"
    second = tmp_path / "b.md"
    first.write_text("a", encoding="utf-8")
    second.write_text("b", encoding="utf-8")
    client = FakeLangflowClient()

    report = await ingest_files(client, [first, second], cwd=tmp_path, sync=fake_sync)

    assert [call[0] for call in client.calls] == [
        "upload",
        "run",
        "delete",
        "upload",
        "run",
        "delete",
    ]
    assert report.uploaded == 2
    assert report.source_overrides == {"a.md": "a.md", "b.md": "b.md"}
    assert report.imported_chunks == 2


@pytest.mark.asyncio
async def test_ingest_files_deletes_upload_when_run_fails(tmp_path: Path) -> None:
    path = tmp_path / "fail.md"
    path.write_text("x", encoding="utf-8")
    client = FakeLangflowClient(fail_run=True)

    with pytest.raises(LangflowAPIError, match="Ingest Flow failed"):
        await ingest_files(client, [path], cwd=tmp_path, sync=fake_sync)

    assert [call[0] for call in client.calls] == ["upload", "run", "delete"]


@pytest.mark.asyncio
async def test_client_upload_and_run_use_files_and_flow_api() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST" and request.url.path == "/api/v2/files":
            return httpx.Response(
                200,
                json={"id": "file-1", "path": "user-1/file-1.md", "name": "sample"},
            )
        if request.method == "POST" and request.url.path == "/api/v1/run/Ingest":
            return httpx.Response(200, json={"ok": True})
        if request.method == "DELETE" and request.url.path == "/api/v2/files/file-1":
            return httpx.Response(200, json={"message": "File deleted successfully"})
        return httpx.Response(404, json={"detail": "not found"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://langflow.test",
    ) as http:
        client = LangflowClient("http://langflow.test", api_key="test-key", http=http)
        uploaded = await client.upload_file(FIXTURE)
        await client.run_ingest("Ingest", uploaded.path)
        await client.delete_file(uploaded.id)

    assert uploaded.path == "user-1/file-1.md"
    assert requests[0].headers["x-api-key"] == "test-key"
    assert requests[0].url.path == "/api/v2/files"
    assert requests[1].url.path == "/api/v1/run/Ingest"
    assert requests[1].read()  # consumed; payload checked via rebuild below
    assert requests[2].method == "DELETE"


@pytest.mark.asyncio
async def test_client_uses_auto_login_when_api_key_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/auto_login":
            return httpx.Response(200, json={"access_token": "jwt-token"})
        if request.method == "GET" and request.url.path == "/api/v1/flows/":
            assert request.headers["Authorization"] == "Bearer jwt-token"
            return httpx.Response(200, json=[{"id": "flow-1", "name": "Ingest"}])
        return httpx.Response(404)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://langflow.test",
    ) as http:
        client = LangflowClient("http://langflow.test", api_key="", http=http)
        await client.authenticate()
        flow_id = await client.resolve_flow_id()

    assert flow_id == "flow-1"


@pytest.mark.asyncio
async def test_client_unreachable_is_actionable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://langflow.test",
    ) as http:
        client = LangflowClient("http://langflow.test", api_key="k", http=http)
        with pytest.raises(LangflowAPIError, match="langflow-up"):
            await client.upload_file(FIXTURE)
    assert "localhost:7860" in LANGFLOW_API_UNREACHABLE


@pytest.mark.asyncio
async def test_client_run_timeout_is_not_reported_as_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://langflow.test",
    ) as http:
        client = LangflowClient("http://langflow.test", api_key="k", http=http)
        with pytest.raises(LangflowAPIError, match="timed out") as exc_info:
            await client.run_ingest("Ingest", "user-1/file-1.md")
    assert "langflow-up" not in str(exc_info.value)
    assert "timed out" in LANGFLOW_RUN_TIMEOUT


def test_makefile_and_env_expose_api_ingest_without_secrets() -> None:
    assert "ingest-langflow:" in MAKEFILE
    assert "scripts/run_langflow_ingest.py" in MAKEFILE
    assert "LANGFLOW_URL=http://localhost:7860" in ENV_EXAMPLE
    assert "LANGFLOW_API_KEY=" in ENV_EXAMPLE
    assert "LANGFLOW_API_KEY=" not in COMPOSE
    assert '"sk-' not in FLOW
    assert "import_langflow" in SCRIPT
    assert "ingest_files" in SCRIPT
    assert '"id": "File-ifAAu"' in FLOW
    assert '"name": "Ingest"' in FLOW
    assert INGEST_OUTPUT_COMPONENT in FLOW
    assert FLOW.count("PGVectorStoreComponent@") == FLOW.count(INGEST_OUTPUT_COMPONENT)
    assert "official-JGTq0" not in FLOW
    assert '"name": "QueryPgVector"' in QUERY_FLOW
    assert "official-JGTq0" in QUERY_FLOW
    assert "File-ifAAu" not in QUERY_FLOW
    assert '"sk-' not in QUERY_FLOW
    assert "knowledge_documents_v1" in QUERY_FLOW


class FakeLangflowClient:
    def __init__(self, *, fail_run: bool = False) -> None:
        self.calls: list[tuple[str, str]] = []
        self._fail_run = fail_run

    async def upload_file(self, path: Path) -> UploadedFile:
        self.calls.append(("upload", path.name))
        return UploadedFile(id=f"id-{path.name}", path=f"user/{path.name}")

    async def run_ingest(self, flow_id: str, uploaded_path: str) -> None:
        self.calls.append(("run", uploaded_path))
        if self._fail_run:
            raise LangflowAPIError("Ingest Flow failed")

    async def delete_file(self, file_id: str) -> None:
        self.calls.append(("delete", file_id))


async def fake_sync(source_overrides: dict[str, str]) -> int:
    return len(set(source_overrides.values()))
