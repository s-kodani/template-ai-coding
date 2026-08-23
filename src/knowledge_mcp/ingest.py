from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Literal, Protocol
from uuid import UUID

INGEST_VERSION = "1"


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ChunkDraft:
    document_id: UUID
    chunk_index: int
    title: str
    content: str
    source: str | None
    embedding: list[float]
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class SyncResult:
    action: Literal["skipped", "replaced"]
    document_id: UUID
    chunk_count: int


class LifecycleRepository(Protocol):
    async def list_chunk_fingerprints(self, document_id: UUID) -> list[dict[str, Any]]: ...

    async def delete_by_document_id(self, document_id: UUID) -> int: ...

    async def upsert_document(
        self,
        *,
        title: str,
        content: str,
        source: str | None,
        embedding: list[float],
        document_id: UUID | None = None,
        chunk_index: int = 0,
        metadata: dict | None = None,
        content_hash: str | None = None,
        embedding_model: str | None = None,
    ) -> str: ...


def investigation_metadata(
    source: str | None,
    chunk_index: int,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = dict(extra or {})
    metadata["source"] = source
    metadata["chunk_index"] = chunk_index
    metadata["ingest_version"] = INGEST_VERSION
    return metadata


async def fingerprint_matches(
    repository: LifecycleRepository,
    document_id: UUID,
    contents: list[str],
    *,
    embedding_model: str,
) -> bool:
    incoming = [(index, content_hash(text)) for index, text in enumerate(contents)]
    existing = await repository.list_chunk_fingerprints(document_id)
    existing_pairs = [(row["chunk_index"], row["content_hash"]) for row in existing]
    models = {row["embedding_model"] for row in existing}
    return bool(existing) and existing_pairs == incoming and models == {embedding_model}


async def replace_document(
    repository: LifecycleRepository,
    chunks: list[ChunkDraft],
    *,
    embedding_model: str,
) -> None:
    document_id = _single_document_id(chunks)
    await repository.delete_by_document_id(document_id)
    for chunk in sorted(chunks, key=lambda item: item.chunk_index):
        await repository.upsert_document(
            title=chunk.title,
            content=chunk.content,
            source=chunk.source,
            embedding=chunk.embedding,
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            metadata=investigation_metadata(chunk.source, chunk.chunk_index, chunk.metadata),
            content_hash=content_hash(chunk.content),
            embedding_model=embedding_model,
        )


async def sync_document(
    repository: LifecycleRepository,
    chunks: list[ChunkDraft],
    *,
    embedding_model: str,
) -> SyncResult:
    document_id = _single_document_id(chunks)
    ordered = sorted(chunks, key=lambda item: item.chunk_index)
    if await fingerprint_matches(
        repository,
        document_id,
        [chunk.content for chunk in ordered],
        embedding_model=embedding_model,
    ):
        return SyncResult("skipped", document_id, len(ordered))
    await replace_document(repository, ordered, embedding_model=embedding_model)
    return SyncResult("replaced", document_id, len(ordered))


async def delete_document(repository: LifecycleRepository, document_id: UUID) -> int:
    return await repository.delete_by_document_id(document_id)


def _single_document_id(chunks: list[ChunkDraft]) -> UUID:
    if not chunks:
        raise ValueError("sync_document requires at least one chunk")
    document_ids = {chunk.document_id for chunk in chunks}
    if len(document_ids) != 1:
        raise ValueError("sync_document requires chunks with the same document_id")
    return next(iter(document_ids))
