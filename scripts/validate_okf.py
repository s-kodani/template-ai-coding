#!/usr/bin/env python3
"""Validate OKF bundle structure for docs/."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

DATE_HEADING_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HEADING_RE = re.compile(r"^## (.+)$", re.MULTILINE)


def parse_version(tag: str) -> tuple[int, ...]:
    normalized = tag.lstrip("vV")
    parts: list[int] = []
    for segment in normalized.split("."):
        numeric = segment.split("-", 1)[0].split("+", 1)[0]
        if not numeric.isdigit():
            raise ValueError(f"invalid version tag heading: {tag!r}")
        parts.append(int(numeric))
    return tuple(parts)


def validate_log_md(text: str) -> list[str]:
    errors: list[str] = []
    headings = HEADING_RE.findall(text)
    if not headings:
        return errors

    version_entries: list[tuple[int, str]] = []
    date_entries: list[tuple[int, str]] = []

    for index, heading in enumerate(headings):
        if DATE_HEADING_RE.match(heading):
            date_entries.append((index, heading))
        else:
            version_entries.append((index, heading))

    if version_entries:
        version_tags = [tag for _, tag in version_entries]
        try:
            parsed = [(tag, parse_version(tag)) for tag in version_tags]
        except ValueError as exc:
            errors.append(str(exc))
            return errors

        sorted_tags = [tag for tag, _ in sorted(parsed, key=lambda item: item[1], reverse=True)]
        if version_tags != sorted_tags:
            errors.append("docs/releases/log.md version tag headings must be descending (newest first)")

    if date_entries:
        date_strings = [date for _, date in date_entries]
        if date_strings != sorted(date_strings, reverse=True):
            errors.append("docs/releases/log.md legacy date headings must be descending")

    if version_entries and date_entries:
        last_version_index = max(index for index, _ in version_entries)
        first_date_index = min(index for index, _ in date_entries)
        if last_version_index > first_date_index:
            errors.append(
                "docs/releases/log.md version tag headings must appear above legacy date headings"
            )

    return errors


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
        errors.extend(validate_log_md(log.read_text(encoding="utf-8")))

    if errors:
        print("OKF validation failed:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("OKF validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
