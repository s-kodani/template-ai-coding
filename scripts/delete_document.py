from __future__ import annotations

import argparse
import asyncio
import uuid

from knowledge_mcp.config import get_settings
from knowledge_mcp.ingest import delete_document
from knowledge_mcp.repository import VectorRepository


async def run(document_id: uuid.UUID) -> int:
    settings = get_settings()
    repository = VectorRepository(settings.host_database_url, settings.db_timeout)
    await repository.connect()
    try:
        return await delete_document(repository, document_id)
    finally:
        await repository.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete all chunks for a parent document_id.")
    parser.add_argument("document_id", type=uuid.UUID)
    args = parser.parse_args()
    deleted = asyncio.run(run(args.document_id))
    print(f"Deleted {deleted} chunks for document_id={args.document_id}.")


if __name__ == "__main__":
    main()
