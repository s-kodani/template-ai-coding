from __future__ import annotations

import asyncio
import json
from typing import Any

import asyncpg
from pgvector.asyncpg import register_vector

from knowledge_mcp.config import Settings
from knowledge_mcp.ingest import ChunkDraft, sync_document
from knowledge_mcp.langflow_import import LANGFLOW_UNREACHABLE, map_langflow_rows, remap_sources
from knowledge_mcp.repository import VectorRepository

FETCH_SQL = """
SELECT e.uuid::text AS id,
       e.document,
       e.embedding,
       e.cmetadata
FROM langchain_pg_embedding AS e
JOIN langchain_pg_collection AS c ON c.uuid = e.collection_id
WHERE c.name = $1
ORDER BY e.uuid
"""


async def fetch_langflow_rows(settings: Settings) -> list[dict[str, Any]]:
    try:
        connection = await asyncpg.connect(settings.langflow_vectors_url)
    except OSError as exc:
        raise RuntimeError(LANGFLOW_UNREACHABLE) from exc
    try:
        await register_vector(connection)
        rows = await connection.fetch(FETCH_SQL, settings.langflow_collection_name)
    except asyncpg.PostgresError as exc:
        raise RuntimeError(
            "Failed to read Langflow collection. "
            "Start Langflow (`make -C infra langflow-up`) and run Ingest first."
        ) from exc
    finally:
        await connection.close()

    mapped_rows: list[dict[str, Any]] = []
    for row in rows:
        metadata = row["cmetadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        embedding = row["embedding"]
        mapped_rows.append(
            {
                "id": row["id"],
                "document": row["document"],
                "embedding": embedding,
                "cmetadata": metadata or {},
            }
        )
    return mapped_rows


async def import_langflow(
    settings: Settings, source_overrides: dict[str, str] | None = None
) -> int:
    rows = await fetch_langflow_rows(settings)
    chunks = map_langflow_rows(rows)
    if source_overrides:
        chunks = remap_sources(chunks, source_overrides)
    grouped: dict[Any, list] = {}
    for chunk in chunks:
        grouped.setdefault(chunk.document_id, []).append(chunk)

    repository = VectorRepository(settings.host_database_url, settings.db_timeout)
    await repository.connect()
    try:
        for group in grouped.values():
            await sync_document(
                repository,
                [
                    ChunkDraft(
                        document_id=chunk.document_id,
                        chunk_index=chunk.chunk_index,
                        title=chunk.title,
                        content=chunk.content,
                        source=chunk.source,
                        embedding=chunk.embedding,
                        metadata=chunk.metadata,
                    )
                    for chunk in group
                ],
                embedding_model=settings.embedding_model,
            )
    finally:
        await repository.close()
    return len(chunks)


def main() -> None:
    from knowledge_mcp.config import get_settings

    count = asyncio.run(import_langflow(get_settings()))
    print(f"Imported {count} chunks into documents.")


if __name__ == "__main__":
    main()
