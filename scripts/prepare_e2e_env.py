"""Write CI/local secrets into .env for e2e stack runs."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"

KEYS = ("OPENAI_API_KEY", "BRAVE_SEARCH_API_KEY", "OPENAI_BASE_URL")


def _load_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _set_or_append(lines: list[str], key: str, value: str) -> None:
    prefix = f"{key}="
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = f"{prefix}{value}"
            return
    lines.append(f"{prefix}{value}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--brave-empty",
        action="store_true",
        help="Force BRAVE_SEARCH_API_KEY to empty (e2e-brave-empty job).",
    )
    args = parser.parse_args()

    lines = _load_lines(ENV_PATH)
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not openai_key:
        msg = "OPENAI_API_KEY is required to prepare .env for e2e"
        raise SystemExit(msg)

    _set_or_append(lines, "OPENAI_API_KEY", openai_key)
    brave_key = "" if args.brave_empty else os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    _set_or_append(lines, "BRAVE_SEARCH_API_KEY", brave_key)

    base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
    if base_url:
        _set_or_append(lines, "OPENAI_BASE_URL", base_url)

    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
