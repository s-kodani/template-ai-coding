from __future__ import annotations

from pathlib import Path

import pytest

from scripts.validate_okf import (
    PENDING_VERSION_HEADING,
    ValidationResult,
    validate_bundle,
    validate_log_md,
)


def write_concept(path: Path, body: str = "# Example\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""---
type: Architecture
title: Example
description: Example concept
status: stable
---
{body}
""",
        encoding="utf-8",
    )


def write_minimal_bundle(docs_root: Path) -> None:
    docs_root.mkdir(parents=True)
    (docs_root / "index.md").write_text(
        """---
okf_version: "0.2"
---

# Bundle

- [Current](/current/index.md)
""",
        encoding="utf-8",
    )
    (docs_root / "current").mkdir()
    (docs_root / "current" / "index.md").write_text(
        "- [Architecture](/current/architecture.md)\n",
        encoding="utf-8",
    )
    (docs_root / "decisions").mkdir()
    (docs_root / "decisions" / "index.md").write_text("# Decisions\n", encoding="utf-8")
    (docs_root / "releases").mkdir()
    (docs_root / "releases" / "index.md").write_text(
        "- [Log](/releases/log.md)\n",
        encoding="utf-8",
    )
    (docs_root / "releases" / "log.md").write_text("# Release Log\n\n## v1.0.0\n", encoding="utf-8")
    (docs_root / "current" / "features").mkdir(parents=True)
    (docs_root / "current" / "features" / "index.md").write_text("# Features\n", encoding="utf-8")
    write_concept(docs_root / "current" / "architecture.md")


def test_validate_log_md_accepts_pending_heading_first() -> None:
    text = f"""# Release Log

## {PENDING_VERSION_HEADING}

- **Added**: example

## v1.0.0

- **Added**: initial
"""
    result = ValidationResult()
    validate_log_md(text, result)
    assert result.ok, result.errors


def test_validate_log_md_rejects_pending_heading_not_first() -> None:
    text = f"""# Release Log

## v1.0.0

- **Added**: initial

## {PENDING_VERSION_HEADING}

- **Added**: example
"""
    result = ValidationResult()
    validate_log_md(text, result)
    assert not result.ok
    assert any("must appear first" in error for error in result.errors)


def test_validate_log_md_rejects_multiple_pending_headings() -> None:
    text = f"""# Release Log

## {PENDING_VERSION_HEADING}

- **Added**: one

## {PENDING_VERSION_HEADING}

- **Added**: two
"""
    result = ValidationResult()
    validate_log_md(text, result)
    assert not result.ok
    assert any("at most one pending version heading" in error for error in result.errors)


def test_validate_bundle_passes_for_minimal_bundle(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    write_minimal_bundle(docs_root)

    result = validate_bundle(docs_root)

    assert result.ok, result.errors


def test_validate_bundle_detects_broken_cross_link(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    write_minimal_bundle(docs_root)
    concept = docs_root / "current" / "architecture.md"
    concept.write_text(
        concept.read_text(encoding="utf-8")
        + "\nSee [Missing](/current/missing.md).\n",
        encoding="utf-8",
    )

    result = validate_bundle(docs_root)

    assert not result.ok
    assert any("broken bundle-relative link" in error for error in result.errors)


def test_validate_bundle_detects_unlisted_concept(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    write_minimal_bundle(docs_root)
    write_concept(docs_root / "current" / "hidden.md")

    result = validate_bundle(docs_root)

    assert not result.ok
    assert any("not linked from a maintained index.md" in error for error in result.errors)


def test_validate_bundle_detects_invalid_frontmatter(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    write_minimal_bundle(docs_root)
    (docs_root / "current" / "architecture.md").write_text(
        """---
type:
title: Broken
description: Broken concept
---
# Broken
""",
        encoding="utf-8",
    )

    result = validate_bundle(docs_root)

    assert not result.ok
    assert any("missing type" in error for error in result.errors)


def test_validate_bundle_detects_invalid_stale_after(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    write_minimal_bundle(docs_root)
    (docs_root / "current" / "architecture.md").write_text(
        """---
type: Architecture
title: Example
description: Example concept
status: stable
stale_after: soon
---
# Example
""",
        encoding="utf-8",
    )

    result = validate_bundle(docs_root)

    assert not result.ok
    assert any("stale_after" in error for error in result.errors)


def test_validate_bundle_accepts_rfc3339_stale_after(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    write_minimal_bundle(docs_root)
    (docs_root / "current" / "architecture.md").write_text(
        """---
type: Architecture
title: Example
description: Example concept
status: stable
stale_after: 2026-12-31T00:00:00+09:00
---
# Example
""",
        encoding="utf-8",
    )

    result = validate_bundle(docs_root)

    assert result.ok, result.errors


def test_validate_bundle_detects_invalid_actor(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    write_minimal_bundle(docs_root)
    (docs_root / "current" / "architecture.md").write_text(
        """---
type: Architecture
title: Example
description: Example concept
status: stable
generated:
  by: invalid actor
  at: 2026-08-27T00:00:00Z
---
# Example
""",
        encoding="utf-8",
    )

    result = validate_bundle(docs_root)

    assert not result.ok
    assert any("generated.by" in error for error in result.errors)
