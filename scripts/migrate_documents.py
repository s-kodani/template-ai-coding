from __future__ import annotations

import asyncio
from pathlib import Path

import asyncpg

from knowledge_mcp.config import Settings

ROOT = Path(__file__).resolve().parents[1]
MIGRATE_SQL = ROOT / "infra" / "app" / "migrate_documents_chunks.sql"


def _statements(sql: str) -> list[str]:
    return [part.strip() for part in sql.split(";") if part.strip()]


async def migrate(settings: Settings) -> None:
    sql = MIGRATE_SQL.read_text(encoding="utf-8")
    connection = await asyncpg.connect(settings.host_database_url)
    try:
        for statement in _statements(sql):
            await connection.execute(statement)
        print("Applied documents chunk schema migration.")
    finally:
        await connection.close()


def main() -> None:
    from knowledge_mcp.config import get_settings

    asyncio.run(migrate(get_settings()))


if __name__ == "__main__":
    main()
