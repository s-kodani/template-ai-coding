import uuid
from typing import Any

import pytest

from knowledge_mcp.ingest import (
    INGEST_VERSION,
    ChunkDraft,
    content_hash,
    delete_document,
    fingerprint_matches,
    sync_document,
)


class FakeLifecycleRepository:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.upsert_calls = 0
        self.delete_calls = 0

    async def list_chunk_fingerprints(self, document_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = [row for row in self.rows if row["document_id"] == document_id]
        rows.sort(key=lambda row: row["chunk_index"])
        return [
            {
                "chunk_index": row["chunk_index"],
                "content_hash": row["content_hash"],
                "embedding_model": row["embedding_model"],
            }
            for row in rows
        ]

    async def delete_by_document_id(self, document_id: uuid.UUID) -> int:
        self.delete_calls += 1
        before = len(self.rows)
        self.rows = [row for row in self.rows if row["document_id"] != document_id]
        return before - len(self.rows)

    async def upsert_document(
        self,
        *,
        title: str,
        content: str,
        source: str | None,
        embedding: list[float],
        document_id: uuid.UUID | None = None,
        chunk_index: int = 0,
        metadata: dict | None = None,
        content_hash: str | None = None,
        embedding_model: str | None = None,
    ) -> str:
        self.upsert_calls += 1
        parent_id = document_id or uuid.uuid4()
        row_id = str(uuid.uuid4())
        self.rows.append(
            {
                "id": row_id,
                "document_id": parent_id,
                "chunk_index": chunk_index,
                "title": title,
                "content": content,
                "source": source,
                "metadata": metadata or {},
                "embedding": embedding,
                "content_hash": content_hash,
                "embedding_model": embedding_model,
            }
        )
        return row_id


def _draft(
    document_id: uuid.UUID,
    content: str,
    *,
    chunk_index: int = 0,
    source: str = "notes/architecture.md",
    title: str = "Architecture",
    embedding: list[float] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ChunkDraft:
    return ChunkDraft(
        document_id=document_id,
        chunk_index=chunk_index,
        title=title,
        content=content,
        source=source,
        embedding=embedding or [0.1, 0.2],
        metadata=metadata,
    )


def test_content_hash_is_stable_sha256_of_utf8_text() -> None:
    assert content_hash("hello") == content_hash("hello")
    assert content_hash("hello") != content_hash("hello!")
    assert content_hash("hello") == (
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )


@pytest.mark.asyncio
async def test_sync_skips_when_same_hashes_and_model_already_stored() -> None:
    document_id = uuid.uuid4()
    repo = FakeLifecycleRepository()
    first = await sync_document(
        repo, [_draft(document_id, "same text")], embedding_model="text-embedding-3-small"
    )

    result = await sync_document(
        repo,
        [_draft(document_id, "same text", embedding=[0.9])],
        embedding_model="text-embedding-3-small",
    )

    assert first.action == "replaced"
    assert result.action == "skipped"
    assert result.chunk_count == 1
    assert repo.upsert_calls == 1
    assert repo.delete_calls == 1
    assert repo.rows[0]["embedding"] == [0.1, 0.2]


@pytest.mark.asyncio
async def test_sync_replaces_when_content_changes() -> None:
    document_id = uuid.uuid4()
    repo = FakeLifecycleRepository()
    await sync_document(
        repo, [_draft(document_id, "old text")], embedding_model="text-embedding-3-small"
    )

    result = await sync_document(
        repo, [_draft(document_id, "new text")], embedding_model="text-embedding-3-small"
    )

    assert result.action == "replaced"
    assert [row["content"] for row in repo.rows] == ["new text"]
    assert repo.rows[0]["content_hash"] == content_hash("new text")
    assert repo.delete_calls == 2


@pytest.mark.asyncio
async def test_sync_deletes_stale_chunks_when_count_decreases() -> None:
    document_id = uuid.uuid4()
    other_id = uuid.uuid4()
    repo = FakeLifecycleRepository()
    await sync_document(
        repo,
        [
            _draft(document_id, "chunk-0", chunk_index=0),
            _draft(document_id, "chunk-1", chunk_index=1),
            _draft(document_id, "chunk-2", chunk_index=2),
        ],
        embedding_model="text-embedding-3-small",
    )
    await sync_document(
        repo, [_draft(other_id, "keep me")], embedding_model="text-embedding-3-small"
    )

    result = await sync_document(
        repo,
        [
            _draft(document_id, "chunk-0", chunk_index=0),
            _draft(document_id, "chunk-1-changed", chunk_index=1),
        ],
        embedding_model="text-embedding-3-small",
    )

    remaining = [row for row in repo.rows if row["document_id"] == document_id]
    assert result.action == "replaced"
    assert [row["chunk_index"] for row in remaining] == [0, 1]
    assert [row["content"] for row in remaining] == ["chunk-0", "chunk-1-changed"]
    assert any(row["content"] == "keep me" for row in repo.rows)


@pytest.mark.asyncio
async def test_sync_replaces_when_embedding_model_changes() -> None:
    document_id = uuid.uuid4()
    repo = FakeLifecycleRepository()
    await sync_document(
        repo, [_draft(document_id, "same text")], embedding_model="text-embedding-3-small"
    )

    result = await sync_document(
        repo, [_draft(document_id, "same text")], embedding_model="text-embedding-3-large"
    )

    assert result.action == "replaced"
    assert repo.rows[0]["embedding_model"] == "text-embedding-3-large"


@pytest.mark.asyncio
async def test_sync_writes_investigation_metadata() -> None:
    document_id = uuid.uuid4()
    repo = FakeLifecycleRepository()

    await sync_document(
        repo,
        [_draft(document_id, "body", metadata={"title": "Architecture"})],
        embedding_model="text-embedding-3-small",
    )

    metadata = repo.rows[0]["metadata"]
    assert metadata["source"] == "notes/architecture.md"
    assert metadata["chunk_index"] == 0
    assert metadata["ingest_version"] == INGEST_VERSION
    assert metadata["title"] == "Architecture"


@pytest.mark.asyncio
async def test_fingerprint_matches_does_not_write() -> None:
    document_id = uuid.uuid4()
    repo = FakeLifecycleRepository()
    await sync_document(
        repo, [_draft(document_id, "body")], embedding_model="text-embedding-3-small"
    )
    repo.upsert_calls = 0
    repo.delete_calls = 0

    assert await fingerprint_matches(
        repo, document_id, ["body"], embedding_model="text-embedding-3-small"
    )
    assert not await fingerprint_matches(
        repo, document_id, ["other"], embedding_model="text-embedding-3-small"
    )
    assert repo.upsert_calls == 0
    assert repo.delete_calls == 0


@pytest.mark.asyncio
async def test_delete_document_removes_only_target_chunks() -> None:
    target = uuid.uuid4()
    other = uuid.uuid4()
    repo = FakeLifecycleRepository()
    await sync_document(
        repo,
        [_draft(target, "a", chunk_index=0), _draft(target, "b", chunk_index=1)],
        embedding_model="text-embedding-3-small",
    )
    await sync_document(
        repo, [_draft(other, "keep")], embedding_model="text-embedding-3-small"
    )

    deleted = await delete_document(repo, target)

    assert deleted == 2
    assert [row["document_id"] for row in repo.rows] == [other]


@pytest.mark.asyncio
async def test_sync_rejects_empty_or_mixed_document_ids() -> None:
    repo = FakeLifecycleRepository()
    first = uuid.uuid4()
    second = uuid.uuid4()

    with pytest.raises(ValueError, match="at least one chunk"):
        await sync_document(repo, [], embedding_model="text-embedding-3-small")

    with pytest.raises(ValueError, match="same document_id"):
        await sync_document(
            repo,
            [_draft(first, "a"), _draft(second, "b", chunk_index=1)],
            embedding_model="text-embedding-3-small",
        )
