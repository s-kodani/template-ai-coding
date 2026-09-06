import uuid
from typing import Any

import pytest
from pgvector.vector import Vector

from knowledge_mcp.ingest import ChunkDraft, content_hash, sync_document
from knowledge_mcp.langflow_import import (
    LANGFLOW_UNREACHABLE,
    fallback_ids_sharing_hashes,
    is_fallback_source,
    map_langflow_rows,
    remap_sources,
    should_sync_group,
    sync_mapped_chunks,
)


def test_langflow_unreachable_message_mentions_recreate() -> None:
    assert "localhost:5434" in LANGFLOW_UNREACHABLE
    assert "langflow-up" in LANGFLOW_UNREACHABLE
    assert "langflow-down" in LANGFLOW_UNREACHABLE


def test_map_langflow_rows_assigns_shared_parent_and_chunk_index() -> None:
    rows = [
        {
            "id": "e-1",
            "document": "first chunk about architecture",
            "embedding": [0.1, 0.2],
            "cmetadata": {"source": "notes/architecture.md", "title": "Architecture"},
        },
        {
            "id": "e-2",
            "document": "second chunk about architecture",
            "embedding": [0.3, 0.4],
            "cmetadata": {"source": "notes/architecture.md"},
        },
        {
            "id": "e-3",
            "document": "unrelated file",
            "embedding": [0.5, 0.6],
            "cmetadata": {"source": "notes/ops.md", "title": "Ops"},
        },
    ]

    mapped = map_langflow_rows(rows)

    architecture = [row for row in mapped if row.source == "notes/architecture.md"]
    ops = [row for row in mapped if row.source == "notes/ops.md"]
    architecture_parent = uuid.uuid5(uuid.NAMESPACE_URL, "notes/architecture.md")

    assert [row.chunk_index for row in architecture] == [0, 1]
    assert {row.document_id for row in architecture} == {architecture_parent}
    assert architecture[0].title == "Architecture"
    assert architecture[1].title == "architecture.md"
    assert architecture[0].content == "first chunk about architecture"
    assert architecture[0].metadata["source"] == "notes/architecture.md"
    assert ops[0].chunk_index == 0
    assert ops[0].document_id != architecture[0].document_id


def test_map_langflow_rows_uses_fallback_source_when_metadata_lacks_source() -> None:
    rows = [
        {
            "id": "orphan-1",
            "document": "no source metadata",
            "embedding": [0.9],
            "cmetadata": {},
        }
    ]

    mapped = map_langflow_rows(rows)

    assert mapped[0].source == "langflow:orphan-1"
    assert mapped[0].document_id == uuid.uuid5(uuid.NAMESPACE_URL, "langflow:orphan-1")
    assert mapped[0].chunk_index == 0
    assert mapped[0].title == "Untitled"


def test_map_langflow_rows_accepts_pgvector_vector() -> None:
    rows = [
        {
            "id": "e-1",
            "document": "chunk",
            "embedding": Vector([0.25, 0.5]),
            "cmetadata": {"source": "notes/architecture.md"},
        }
    ]

    mapped = map_langflow_rows(rows)

    assert mapped[0].embedding == [0.25, 0.5]


def test_remap_sources_matches_uploaded_path_not_just_filename() -> None:
    langflow_source = "user-1/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.md"
    rows = [
        {
            "id": "e-1",
            "document": "chunk",
            "embedding": [0.1],
            "cmetadata": {"source": langflow_source},
        }
    ]

    mapped = map_langflow_rows(rows)
    remapped = remap_sources(mapped, {langflow_source: "data/ingest/notes.md"})

    assert remapped[0].source == "data/ingest/notes.md"
    assert remapped[0].document_id == uuid.uuid5(uuid.NAMESPACE_URL, "data/ingest/notes.md")
    assert remapped[0].title == "notes.md"


def test_remap_sources_replaces_untitled_with_host_filename() -> None:
    rows = [
        {
            "id": "orphan-1",
            "document": "chunk",
            "embedding": [0.1],
            "cmetadata": {},
        }
    ]

    mapped = map_langflow_rows(rows)
    remapped = remap_sources(mapped, {"Untitled": "data/ingest/sample.md"})

    assert mapped[0].title == "Untitled"
    assert remapped[0].source == "data/ingest/sample.md"
    assert remapped[0].title == "sample.md"


def test_is_fallback_source() -> None:
    assert is_fallback_source("langflow:orphan-1") is True
    assert is_fallback_source("data/ingest/notes.md") is False


def test_should_sync_group_skips_fallback_when_host_hash_exists() -> None:
    mapped = map_langflow_rows(
        [
            {
                "id": "orphan-1",
                "document": "same body",
                "embedding": [0.1],
                "cmetadata": {},
            }
        ]
    )
    host_hashes = {content_hash("same body")}

    assert should_sync_group(mapped, host_hashes) is False
    assert should_sync_group(mapped, set()) is True


def test_should_sync_group_keeps_host_path_even_if_hash_exists() -> None:
    mapped = map_langflow_rows(
        [
            {
                "id": "e-1",
                "document": "same body",
                "embedding": [0.1],
                "cmetadata": {"source": "data/ingest/notes.md"},
            }
        ]
    )

    assert should_sync_group(mapped, {content_hash("same body")}) is True


def test_fallback_ids_sharing_hashes() -> None:
    fallback_id = uuid.uuid5(uuid.NAMESPACE_URL, "langflow:orphan-1")
    other_id = uuid.uuid5(uuid.NAMESPACE_URL, "langflow:other")
    digest = content_hash("same body")
    ids = fallback_ids_sharing_hashes(
        [(fallback_id, digest), (other_id, content_hash("other"))],
        {digest},
    )
    assert ids == [fallback_id]


class FakeImportRepository:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

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

    async def list_host_path_hashes(self) -> set[str]:
        return {
            row["content_hash"]
            for row in self.rows
            if row["content_hash"] and not str(row["source"] or "").startswith("langflow:")
        }

    async def list_fallback_fingerprints(self) -> list[tuple[uuid.UUID, str]]:
        return [
            (row["document_id"], row["content_hash"])
            for row in self.rows
            if str(row["source"] or "").startswith("langflow:") and row["content_hash"]
        ]


def _rows(*items: tuple[str, str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"id": row_id, "document": body, "embedding": [0.1], "cmetadata": metadata}
        for row_id, body, metadata in items
    ]


@pytest.mark.asyncio
async def test_sync_mapped_chunks_skips_fallback_when_host_hash_exists() -> None:
    repo = FakeImportRepository()
    host = map_langflow_rows(
        _rows(("e-1", "same body", {"source": "data/ingest/notes.md"}))
    )
    await sync_document(
        repo,
        [
            ChunkDraft(
                document_id=host[0].document_id,
                chunk_index=0,
                title=host[0].title,
                content=host[0].content,
                source=host[0].source,
                embedding=host[0].embedding,
                metadata=host[0].metadata,
            )
        ],
        embedding_model="text-embedding-3-small",
    )
    fallback = map_langflow_rows(_rows(("orphan-1", "same body", {})))

    count = await sync_mapped_chunks(
        repo, fallback, embedding_model="text-embedding-3-small"
    )

    sources = [row["source"] for row in repo.rows]
    assert count == 0
    assert sources == ["data/ingest/notes.md"]
    assert not any(str(source).startswith("langflow:") for source in sources)


@pytest.mark.asyncio
async def test_sync_mapped_chunks_deletes_fallback_after_host_path_import() -> None:
    repo = FakeImportRepository()
    fallback = map_langflow_rows(_rows(("orphan-1", "same body", {})))
    await sync_mapped_chunks(repo, fallback, embedding_model="text-embedding-3-small")
    host = map_langflow_rows(
        _rows(("e-1", "same body", {"source": "data/ingest/notes.md"}))
    )

    count = await sync_mapped_chunks(repo, host, embedding_model="text-embedding-3-small")

    sources = [row["source"] for row in repo.rows]
    assert count == 1
    assert sources == ["data/ingest/notes.md"]


@pytest.mark.asyncio
async def test_sync_mapped_chunks_imports_fallback_when_no_host_hash() -> None:
    repo = FakeImportRepository()
    fallback = map_langflow_rows(_rows(("orphan-1", "ui only body", {})))

    count = await sync_mapped_chunks(
        repo, fallback, embedding_model="text-embedding-3-small"
    )

    assert count == 1
    assert repo.rows[0]["source"] == "langflow:orphan-1"
    assert repo.rows[0]["title"] == "Untitled"
