from __future__ import annotations

import uuid

PARENT_NAMESPACE = uuid.NAMESPACE_URL


def parent_document_id(source: str | None, *, fallback: uuid.UUID | None = None) -> uuid.UUID:
    if source and source.strip():
        return uuid.uuid5(PARENT_NAMESPACE, source.strip())
    if fallback is None:
        raise ValueError("source or fallback is required")
    return fallback
