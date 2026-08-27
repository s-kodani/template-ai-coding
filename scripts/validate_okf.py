#!/usr/bin/env python3
"""Validate OKF bundle structure for docs/."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

DATE_HEADING_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HEADING_RE = re.compile(r"^## (.+)$", re.MULTILINE)
LINK_RE = re.compile(r"\]\((/[^)#]+\.md)\)")
ACTOR_RE = re.compile(r"^(human:[^\s/]+|process:[^\s/]+|[^/\s]+/[^\s/]+)$")
RFC3339_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VALID_STATUS = frozenset({"draft", "stable", "deprecated"})
MAINTAINED_INDEX_RELATIVE_PATHS = (
    "index.md",
    "current/index.md",
    "current/features/index.md",
    "decisions/index.md",
    "releases/index.md",
)


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)

    def add(self, message: str) -> None:
        self.errors.append(message)

    @property
    def ok(self) -> bool:
        return not self.errors


def parse_version(tag: str) -> tuple[int, ...]:
    normalized = tag.lstrip("vV")
    parts: list[int] = []
    for segment in normalized.split("."):
        numeric = segment.split("-", 1)[0].split("+", 1)[0]
        if not numeric.isdigit():
            raise ValueError(f"invalid version tag heading: {tag!r}")
        parts.append(int(numeric))
    return tuple(parts)


def is_reserved_markdown(path: Path) -> bool:
    return path.name in {"index.md", "log.md"}


def is_concept_document(path: Path) -> bool:
    return path.suffix == ".md" and path.is_relative_to(DOCS) and not is_reserved_markdown(path)


def split_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    if not text.startswith("---"):
        return None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text
    try:
        metadata = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML frontmatter: {exc}") from exc
    if not isinstance(metadata, dict):
        raise ValueError("frontmatter must be a mapping")
    return metadata, parts[2]


def bundle_link_to_path(link: str, docs_root: Path = DOCS) -> Path:
    return docs_root / link.removeprefix("/")


def extract_bundle_links(text: str) -> list[str]:
    return LINK_RE.findall(text)


def validate_actor(actor: Any, context: str, result: ValidationResult) -> None:
    if not isinstance(actor, str) or not actor.strip():
        result.add(f"{context} must be a non-empty string")
        return
    if not ACTOR_RE.match(actor):
        result.add(f"{context} has invalid actor format: {actor!r}")


def validate_stale_after(value: Any, context: str, result: ValidationResult) -> None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            result.add(f"{context} datetime must include timezone offset")
        return
    if isinstance(value, date):
        return
    if not isinstance(value, str) or not value.strip():
        result.add(f"{context} must be a non-empty string")
        return
    if not (RFC3339_RE.match(value) or DATE_ONLY_RE.match(value)):
        result.add(
            f"{context} must be RFC3339 datetime with offset or YYYY-MM-DD date: {value!r}"
        )


def validate_frontmatter_metadata(
    metadata: dict[str, Any], rel_path: str, result: ValidationResult
) -> None:
    concept_type = metadata.get("type")
    if not isinstance(concept_type, str) or not concept_type.strip():
        result.add(f"{rel_path} missing type in frontmatter")
        return

    status = metadata.get("status")
    if status is not None and status not in VALID_STATUS:
        result.add(f"{rel_path} has invalid status: {status!r}")

    if "stale_after" in metadata:
        validate_stale_after(metadata["stale_after"], f"{rel_path} stale_after", result)

    generated = metadata.get("generated")
    if generated is not None:
        if not isinstance(generated, dict):
            result.add(f"{rel_path} generated must be a mapping")
        else:
            validate_actor(generated.get("by"), f"{rel_path} generated.by", result)

    verified = metadata.get("verified")
    if verified is not None:
        if not isinstance(verified, list):
            result.add(f"{rel_path} verified must be a list")
        else:
            for index, entry in enumerate(verified):
                if not isinstance(entry, dict):
                    result.add(f"{rel_path} verified[{index}] must be a mapping")
                    continue
                validate_actor(entry.get("by"), f"{rel_path} verified[{index}].by", result)


def validate_log_md(text: str, result: ValidationResult) -> None:
    headings = HEADING_RE.findall(text)
    if not headings:
        return

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
            result.add(str(exc))
            return

        sorted_tags = [tag for tag, _ in sorted(parsed, key=lambda item: item[1], reverse=True)]
        if version_tags != sorted_tags:
            result.add("docs/releases/log.md version tag headings must be descending (newest first)")

    if date_entries:
        date_strings = [date for _, date in date_entries]
        if date_strings != sorted(date_strings, reverse=True):
            result.add("docs/releases/log.md legacy date headings must be descending")

    if version_entries and date_entries:
        last_version_index = max(index for index, _ in version_entries)
        first_date_index = min(index for index, _ in date_entries)
        if last_version_index > first_date_index:
            result.add(
                "docs/releases/log.md version tag headings must appear above legacy date headings"
            )


def validate_cross_links(
    path: Path, text: str, result: ValidationResult, docs_root: Path = DOCS
) -> None:
    rel_path = path.relative_to(docs_root.parent).as_posix()
    for link in extract_bundle_links(text):
        target = bundle_link_to_path(link, docs_root)
        if not target.exists():
            result.add(f"{rel_path} has broken bundle-relative link: {link}")


def validate_bundle(docs_root: Path = DOCS) -> ValidationResult:
    result = ValidationResult()
    index = docs_root / "index.md"
    repo_root = docs_root.parent

    if not index.exists():
        result.add("docs/index.md is missing")
        return result

    try:
        root_text = index.read_text(encoding="utf-8")
    except OSError as exc:
        result.add(f"docs/index.md is unreadable: {exc}")
        return result

    if 'okf_version: "0.2"' not in root_text:
        result.add('docs/index.md must declare okf_version: "0.2"')

    if not root_text.startswith("---"):
        result.add("docs/index.md missing frontmatter")

    concept_paths: list[Path] = []
    markdown_paths = sorted(docs_root.rglob("*.md"))

    for path in markdown_paths:
        rel_path = path.relative_to(repo_root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            result.add(f"{rel_path} is unreadable: {exc}")
            continue

        validate_cross_links(path, text, result, docs_root)

        if path.name == "index.md" and path != index:
            if text.startswith("---"):
                result.add(f"{rel_path} must not have frontmatter")
            continue

        if path.name == "log.md":
            validate_log_md(text, result)
            continue

        if path == index:
            continue

        if not (path.suffix == ".md" and not is_reserved_markdown(path)):
            continue

        concept_paths.append(path)

        if not text.startswith("---"):
            result.add(f"{rel_path} missing frontmatter")
            continue

        try:
            metadata, _ = split_frontmatter(text)
        except ValueError as exc:
            result.add(f"{rel_path}: {exc}")
            continue

        if metadata is None:
            result.add(f"{rel_path} missing frontmatter")
            continue

        validate_frontmatter_metadata(metadata, rel_path, result)

    index_links: set[str] = set()
    for relative in MAINTAINED_INDEX_RELATIVE_PATHS:
        index_path = docs_root / relative
        if not index_path.exists():
            result.add(f"{index_path.relative_to(repo_root).as_posix()} is missing")
            continue
        index_text = index_path.read_text(encoding="utf-8")
        index_links.update(extract_bundle_links(index_text))

    for concept_path in concept_paths:
        rel_link = f"/{concept_path.relative_to(docs_root).as_posix()}"
        if rel_link not in index_links:
            result.add(
                f"{concept_path.relative_to(repo_root).as_posix()} is not linked from a maintained index.md"
            )

    for link in sorted(index_links):
        target = bundle_link_to_path(link, docs_root)
        if not target.exists():
            result.add(f"maintained index has broken bundle-relative link: {link}")

    return result


def main() -> int:
    result = validate_bundle()
    if not result.ok:
        print("OKF validation failed:")
        for err in result.errors:
            print(f"  - {err}")
        return 1

    print("OKF validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
