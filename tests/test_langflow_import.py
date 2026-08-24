import uuid

from pgvector.vector import Vector

from knowledge_mcp.langflow_import import LANGFLOW_UNREACHABLE, map_langflow_rows, remap_sources


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
