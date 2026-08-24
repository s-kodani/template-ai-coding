from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from import_langflow import import_langflow

from knowledge_mcp.config import get_settings
from knowledge_mcp.langflow_ingest import LangflowClient, ingest_files


async def run(paths: list[Path]) -> None:
    settings = get_settings()
    targets = paths or [Path(settings.langflow_ingest_dir)]
    client = LangflowClient(
        settings.langflow_url,
        api_key=settings.langflow_api_key,
        timeout=settings.langflow_timeout,
    )
    try:
        await client.authenticate()
        flow_id = settings.langflow_flow_id or await client.resolve_flow_id(
            flow_name=settings.langflow_flow_name
        )

        async def sync(overrides: dict[str, str]) -> int:
            return await import_langflow(settings, source_overrides=overrides)

        report = await ingest_files(client, targets, cwd=Path.cwd(), flow_id=flow_id, sync=sync)
        print(
            f"Ingested {report.uploaded} files via Langflow API, "
            f"imported {report.imported_chunks} chunks."
        )
    finally:
        await client.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload host files to Langflow, run Ingest Flow, then sync documents."
    )
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Host files or directories. Default: data/ingest",
    )
    args = parser.parse_args()
    asyncio.run(run(args.files))


if __name__ == "__main__":
    main()
