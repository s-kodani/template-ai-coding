from __future__ import annotations

import asyncio
from pathlib import Path

import asyncpg

from knowledge_mcp.config import Settings

ROOT = Path(__file__).resolve().parents[1]
MIGRATE_DIR = ROOT / "infra" / "app"


def _statements(sql: str) -> list[str]:
    return [part.strip() for part in sql.split(";") if part.strip()]


async def migrate(settings: Settings) -> None:
    connection = await asyncpg.connect(settings.host_database_url)
    try:
        for path in sorted(MIGRATE_DIR.glob("migrate_*.sql")):
            sql = path.read_text(encoding="utf-8")
            for statement in _statements(sql):
                await connection.execute(statement)
            print(f"Applied {path.name}")
    finally:
        await connection.close()


def main() -> None:
    from knowledge_mcp.config import get_settings

    asyncio.run(migrate(get_settings()))


if __name__ == "__main__":
    main()
