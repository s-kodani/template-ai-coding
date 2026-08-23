from __future__ import annotations

import json
from uuid import UUID

import asyncpg
from pgvector.asyncpg import register_vector

from knowledge_mcp.chunk_ids import parent_document_id
from knowledge_mcp.models import DocumentDetail, SearchHit


class DatabaseError(Exception):
    """Database operation failed."""


class VectorRepository:
    def __init__(self, database_url: str, timeout: float) -> None:
        self._database_url = database_url
        self._timeout = timeout
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self._pool is not None:
            return

        async def init(conn: asyncpg.Connection) -> None:
            await register_vector(conn)

        self._pool = await asyncpg.create_pool(
            self._database_url,
            init=init,
            command_timeout=self._timeout,
            min_size=1,
            max_size=5,
        )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def search(self, embedding: list[float], top_k: int) -> list[SearchHit]:
        pool = self._require_pool()
        try:
            rows = await pool.fetch(
                """
                SELECT id::text,
                       title,
                       content,
                       source,
                       1 - (embedding <=> $1::vector) AS similarity
                FROM documents
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> $1::vector
                LIMIT $2
                """,
                embedding,
                top_k,
            )
        except asyncpg.PostgresError as exc:
            raise DatabaseError(
                "Vector search failed. Ensure pgvector is installed and documents are seeded."
            ) from exc

        hits: list[SearchHit] = []
        for row in rows:
            content = row["content"]
            excerpt = content[:240] + ("..." if len(content) > 240 else "")
            hits.append(
                SearchHit(
                    document_id=row["id"],
                    title=row["title"],
                    excerpt=excerpt,
                    source=row["source"],
                    similarity=float(row["similarity"]),
                )
            )
        return hits

    async def get_document(self, document_id: str) -> DocumentDetail | None:
        pool = self._require_pool()
        try:
            row = await pool.fetchrow(
                """
                SELECT id::text, title, content, source
                FROM documents
                WHERE id = $1::uuid
                """,
                document_id,
            )
        except asyncpg.PostgresError as exc:
            raise DatabaseError("Document lookup failed.") from exc
        if row is None:
            return None
        return DocumentDetail(
            document_id=row["id"],
            title=row["title"],
            content=row["content"],
            source=row["source"],
        )

    async def count_documents(self) -> int:
        pool = self._require_pool()
        return int(await pool.fetchval("SELECT COUNT(*) FROM documents"))

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
    ) -> str:
        pool = self._require_pool()
        parent_id = document_id or parent_document_id(source)
        row = await pool.fetchrow(
            """
            INSERT INTO documents (
                document_id, chunk_index, title, content, source, metadata, embedding
            )
            VALUES ($1::uuid, $2, $3, $4, $5, $6::jsonb, $7::vector)
            ON CONFLICT (document_id, chunk_index) DO UPDATE
            SET title = EXCLUDED.title,
                content = EXCLUDED.content,
                source = EXCLUDED.source,
                metadata = EXCLUDED.metadata,
                embedding = EXCLUDED.embedding
            RETURNING id::text
            """,
            str(parent_id),
            chunk_index,
            title,
            content,
            source,
            json.dumps(metadata or {}),
            embedding,
        )
        return row["id"]

    def _require_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise DatabaseError("Database pool is not connected.")
        return self._pool
