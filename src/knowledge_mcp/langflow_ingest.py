from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx

from knowledge_mcp.langflow_import import MappedChunk, remap_sources

FILE_COMPONENT_ID = "File-ifAAu"
INGEST_FLOW_NAME = "Ingest"
INGEST_OUTPUT_COMPONENT = "ext:pgvector:PGVectorStoreComponent@official-mB2mI"
LANGFLOW_API_UNREACHABLE = (
    "Cannot reach Langflow (http://localhost:7860). Run `make -C infra langflow-up`."
)
LANGFLOW_RUN_TIMEOUT = (
    "Langflow Ingest Flow timed out. "
    "The server may still be running; check Langflow logs."
)


class LangflowAPIError(Exception):
    """Langflow Files / Flow API failed."""


@dataclass(frozen=True)
class UploadedFile:
    id: str
    path: str


@dataclass(frozen=True)
class IngestReport:
    uploaded: int
    source_overrides: dict[str, str]
    imported_chunks: int


class IngestClient(Protocol):
    async def upload_file(self, path: Path) -> UploadedFile: ...

    async def run_ingest(self, flow_id: str, uploaded_path: str) -> None: ...

    async def delete_file(self, file_id: str) -> None: ...


def resolve_ingest_paths(paths: Sequence[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(
                candidate
                for candidate in sorted(path.rglob("*"))
                if _is_ingest_file(candidate)
            )
        elif _is_ingest_file(path):
            files.append(path)
        else:
            raise LangflowAPIError(f"Ingest path does not exist: {path}")
    unique = list(dict.fromkeys(files))
    if not unique:
        raise LangflowAPIError(
            "No ingest files found. Put files in data/ingest or pass paths."
        )
    return unique


def host_source(path: Path, *, cwd: Path | None = None) -> str:
    base = (cwd or Path.cwd()).resolve()
    resolved = path.resolve()
    try:
        return resolved.relative_to(base).as_posix()
    except ValueError:
        return resolved.as_posix()


def extract_upload(payload: dict[str, Any]) -> UploadedFile:
    file_id = payload.get("id")
    path = payload.get("path") or payload.get("file_path")
    if not file_id or not path:
        raise LangflowAPIError("Langflow Files API did not return id and path.")
    return UploadedFile(id=str(file_id), path=str(path))


def build_run_payload(
    uploaded_path: str, *, component_id: str = FILE_COMPONENT_ID
) -> dict[str, Any]:
    return {
        "output_type": "any",
        "output_component": INGEST_OUTPUT_COMPONENT,
        "tweaks": {component_id: {"path": [uploaded_path]}},
    }


async def ingest_files(
    client: IngestClient,
    paths: Sequence[Path],
    *,
    cwd: Path | None = None,
    flow_id: str = INGEST_FLOW_NAME,
    sync: Callable[[dict[str, str]], Awaitable[int]] | None = None,
) -> IngestReport:
    resolved = resolve_ingest_paths(paths)
    report_overrides: dict[str, str] = {}
    sync_overrides: dict[str, str] = {}
    for path in resolved:
        uploaded = await client.upload_file(path)
        try:
            await client.run_ingest(flow_id, uploaded.path)
        finally:
            await client.delete_file(uploaded.id)
        host = host_source(path, cwd=cwd)
        report_overrides[path.name] = host
        sync_overrides[path.name] = host
        sync_overrides[uploaded.path] = host
        sync_overrides[Path(uploaded.path).name] = host
    imported = await sync(sync_overrides) if sync is not None else 0
    return IngestReport(len(resolved), report_overrides, imported)


class LangflowClient:
    def __init__(
        self,
        base_url: str,
        *,
        api_key: str = "",
        timeout: float = 120.0,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._headers = {"x-api-key": api_key} if api_key else {}
        self._owns_http = http is None
        self._http = http or httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout)

    async def authenticate(self) -> None:
        if self._api_key:
            self._headers = {"x-api-key": self._api_key}
            return
        response = await self._request(self._http.get, "/api/v1/auto_login")
        token = (response.json() or {}).get("access_token")
        if response.status_code >= 400 or not token:
            raise LangflowAPIError(
                "Langflow API key is not configured. Set LANGFLOW_API_KEY in .env."
            )
        self._headers = {"Authorization": f"Bearer {token}"}

    async def resolve_flow_id(
        self, flow_id: str = "", flow_name: str = INGEST_FLOW_NAME
    ) -> str:
        if flow_id:
            return flow_id
        response = await self._request(
            self._http.get,
            "/api/v1/flows/",
            params={"get_all": "true", "remove_example_flows": "true"},
            headers=self._headers,
        )
        self._raise_for_status(response, "Failed to list Langflow flows")
        flows = response.json()
        if isinstance(flows, dict):
            flows = flows.get("items") or flows.get("flows") or []
        for flow in flows:
            if flow.get("name") == flow_name:
                return str(flow["id"])
        raise LangflowAPIError(
            f"Langflow flow '{flow_name}' was not found. "
            "Import infra/langflow/flows/Ingest.json in the UI or set LANGFLOW_FLOW_ID."
        )

    async def upload_file(self, path: Path) -> UploadedFile:
        with path.open("rb") as handle:
            response = await self._request(
                self._http.post,
                "/api/v2/files",
                headers=self._headers,
                files={"file": (path.name, handle, "application/octet-stream")},
            )
        self._raise_for_status(response, "Langflow Files API upload failed")
        return extract_upload(response.json())

    async def run_ingest(self, flow_id: str, uploaded_path: str) -> None:
        response = await self._request(
            self._http.post,
            f"/api/v1/run/{flow_id}",
            headers={**self._headers, "Content-Type": "application/json"},
            json=build_run_payload(uploaded_path),
        )
        if response.status_code >= 400:
            detail = response.text[:300].replace("\n", " ")
            raise LangflowAPIError(f"Ingest Flow failed (status {response.status_code}): {detail}")

    async def delete_file(self, file_id: str) -> None:
        response = await self._request(
            self._http.delete,
            f"/api/v2/files/{file_id}",
            headers=self._headers,
        )
        self._raise_for_status(response, "Langflow Files API delete failed")

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def _request(self, method: Callable[..., Awaitable[httpx.Response]], *args: Any, **kwargs: Any) -> httpx.Response:
        try:
            return await method(*args, **kwargs)
        except httpx.TimeoutException as exc:
            raise LangflowAPIError(LANGFLOW_RUN_TIMEOUT) from exc
        except httpx.RequestError as exc:
            raise LangflowAPIError(LANGFLOW_API_UNREACHABLE) from exc

    def _raise_for_status(self, response: httpx.Response, message: str) -> None:
        if response.status_code >= 400:
            raise LangflowAPIError(f"{message} (status {response.status_code}).")


def _is_ingest_file(path: Path) -> bool:
    return path.is_file() and not path.name.startswith(".") and path.name != ".gitkeep"


__all__ = [
    "FILE_COMPONENT_ID",
    "INGEST_FLOW_NAME",
    "INGEST_OUTPUT_COMPONENT",
    "LANGFLOW_API_UNREACHABLE",
    "LANGFLOW_RUN_TIMEOUT",
    "IngestReport",
    "LangflowAPIError",
    "LangflowClient",
    "MappedChunk",
    "UploadedFile",
    "build_run_payload",
    "extract_upload",
    "host_source",
    "ingest_files",
    "remap_sources",
    "resolve_ingest_paths",
]
