from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from uuid import UUID

from knowledge_mcp.chunk_ids import parent_document_id

LANGFLOW_UNREACHABLE = (
    "Cannot connect to Langflow Postgres (localhost:5434). "
    "Run `make -C infra langflow-up`. "
    "If the container was created before port 5434 was published, "
    "recreate it with `make -C infra langflow-down && make -C infra langflow-up`."
)


@dataclass(frozen=True)
class MappedChunk:
    document_id: UUID
    chunk_index: int
    title: str
    content: str
    source: str
    metadata: dict[str, Any]
    embedding: list[float]


def map_langflow_rows(rows: list[dict[str, Any]]) -> list[MappedChunk]:
    grouped: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for row in rows:
        metadata = _as_metadata(row.get("cmetadata"))
        source = _source_from_metadata(metadata, row.get("id"))
        grouped.setdefault(source, []).append((row, metadata))

    mapped: list[MappedChunk] = []
    for source, items in grouped.items():
        document_id = parent_document_id(source)
        for chunk_index, (row, metadata) in enumerate(items):
            mapped.append(
                MappedChunk(
                    document_id=document_id,
                    chunk_index=chunk_index,
                    title=_chunk_title(metadata, source),
                    content=str(row["document"]),
                    source=source,
                    metadata=metadata,
                    embedding=_as_float_list(row["embedding"]),
                )
            )
    return mapped


def remap_sources(chunks: list[MappedChunk], source_by_name: dict[str, str]) -> list[MappedChunk]:
    remapped = []
    for chunk in chunks:
        source = _override_source(chunk, source_by_name)
        title = _chunk_title(chunk.metadata, source) if source != chunk.source else chunk.title
        remapped.append(
            replace(chunk, source=source, document_id=parent_document_id(source), title=title)
        )

    grouped: dict[str, list[MappedChunk]] = {}
    for chunk in remapped:
        grouped.setdefault(chunk.source, []).append(chunk)

    result: list[MappedChunk] = []
    for source, items in grouped.items():
        document_id = parent_document_id(source)
        for chunk_index, chunk in enumerate(items):
            result.append(replace(chunk, document_id=document_id, chunk_index=chunk_index))
    return result


def _override_source(chunk: MappedChunk, source_by_name: dict[str, str]) -> str:
    for key in _source_keys(chunk):
        if key in source_by_name:
            return source_by_name[key]
    return chunk.source


def _source_keys(chunk: MappedChunk) -> list[str]:
    keys = [chunk.source, Path(chunk.source).name, chunk.title]
    for field in ("source", "file_path", "filename", "name"):
        value = chunk.metadata.get(field)
        if isinstance(value, str) and value.strip():
            keys.append(value.strip())
            keys.append(Path(value.strip()).name)
    return keys


def _as_float_list(value: Any) -> list[float]:
    if hasattr(value, "to_list"):
        value = value.to_list()
    return [float(item) for item in value]


def _as_metadata(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _source_from_metadata(metadata: dict[str, Any], row_id: Any) -> str:
    source = metadata.get("source")
    if isinstance(source, str) and source.strip():
        return source.strip()
    return f"langflow:{row_id}"


def _chunk_title(metadata: dict[str, Any], source: str) -> str:
    title = metadata.get("title")
    if isinstance(title, str) and title.strip() and title.strip() != "Untitled":
        return title.strip()
    if source.startswith("langflow:"):
        return "Untitled"
    name = Path(source).name
    return name or "Untitled"
