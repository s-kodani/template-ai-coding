#!/usr/bin/env python3
"""Validate OKF bundle structure for docs/."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def main() -> int:
    errors: list[str] = []

    index = DOCS / "index.md"
    if not index.exists():
        errors.append("docs/index.md is missing")
    else:
        text = index.read_text(encoding="utf-8")
        if 'okf_version: "0.2"' not in text:
            errors.append('docs/index.md must declare okf_version: "0.2"')

    for path in DOCS.rglob("*.md"):
        if path.name == "index.md" and path.parent != DOCS:
            if path.read_text(encoding="utf-8").startswith("---"):
                errors.append(f"{path.relative_to(ROOT)} must not have frontmatter")
            continue
        if path.name == "log.md":
            continue
        if path == index:
            if not text.startswith("---"):
                errors.append("docs/index.md missing frontmatter")
            continue
        if not path.read_text(encoding="utf-8").startswith("---"):
            errors.append(f"{path.relative_to(ROOT)} missing frontmatter")

        content = path.read_text(encoding="utf-8")
        if content.startswith("---"):
            frontmatter = content.split("---", 2)[1]
            if "type:" not in frontmatter:
                errors.append(f"{path.relative_to(ROOT)} missing type in frontmatter")

    log = DOCS / "releases" / "log.md"
    if log.exists():
        dates = re.findall(r"^## (\d{4}-\d{2}-\d{2})", log.read_text(encoding="utf-8"), re.MULTILINE)
        if dates != sorted(dates, reverse=True):
            errors.append("docs/releases/log.md dates must be descending")

    if errors:
        print("OKF validation failed:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("OKF validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
