import uuid

from knowledge_mcp.chunk_ids import parent_document_id


def test_parent_document_id_is_uuid5_of_source() -> None:
    # uuid.uuid5(uuid.NAMESPACE_URL, "docs/current/architecture.md")
    assert parent_document_id("docs/current/architecture.md") == uuid.UUID(
        "b8084f1f-649b-5463-9fc3-738178c0aeef"
    )


def test_parent_document_id_is_stable_for_same_source() -> None:
    first = parent_document_id("docs/current/features/api.md")
    second = parent_document_id("docs/current/features/api.md")

    assert first == second
    assert first != parent_document_id("docs/current/infrastructure.md")


def test_parent_document_id_falls_back_when_source_missing() -> None:
    fallback = uuid.UUID("11111111-1111-1111-1111-111111111111")

    assert parent_document_id(None, fallback=fallback) == fallback
    assert parent_document_id("   ", fallback=fallback) == fallback
