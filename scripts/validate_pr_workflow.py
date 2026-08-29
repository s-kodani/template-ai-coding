#!/usr/bin/env python3
"""Validate pull request workflow requirements (issue linkage, release log)."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field

ISSUE_REF_PREFIXES = ("src/",)
RELEASE_LOG_TRIGGER_PREFIXES = ("src/", "infra/")
RELEASE_LOG_PATH = "docs/releases/log.md"
ISSUE_REF_RE = re.compile(
    r"(?:^|\b)(?:refs?|close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*#\d+",
    re.IGNORECASE,
)
RELEASE_NOTE_DECL_RE = re.compile(
    r"^Release-Note:\s*(required|not-required)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
RELEASE_NOTE_REASON_RE = re.compile(
    r"^Reason:\s*(.+)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)

    def add(self, message: str) -> None:
        self.errors.append(message)

    @property
    def ok(self) -> bool:
        return not self.errors


def read_changed_files_from_stdin() -> list[str]:
    return [line.strip() for line in sys.stdin if line.strip()]


def has_prefix(changed_files: list[str], prefixes: tuple[str, ...]) -> bool:
    return any(path.startswith(prefixes) for path in changed_files)


def has_issue_reference(pr_body: str | None) -> bool:
    if not pr_body:
        return False
    return ISSUE_REF_RE.search(pr_body) is not None


def parse_release_note_declaration(pr_body: str | None) -> tuple[str | None, str | None]:
    """Return (status, reason) where status is 'required' | 'not-required' | None."""
    if not pr_body:
        return None, None

    match = RELEASE_NOTE_DECL_RE.search(pr_body)
    if not match:
        return None, None

    status = match.group(1).lower()
    reason_match = RELEASE_NOTE_REASON_RE.search(pr_body)
    reason = reason_match.group(1).strip() if reason_match else None
    return status, reason


def validate_pr_workflow(
    changed_files: list[str],
    pr_body: str | None,
) -> ValidationResult:
    result = ValidationResult()

    if has_prefix(changed_files, ISSUE_REF_PREFIXES) and not has_issue_reference(pr_body):
        result.add(
            "PR body must include an issue reference such as "
            "'Refs #123' or 'Closes #123' when src/ files change."
        )

    if has_prefix(changed_files, RELEASE_LOG_TRIGGER_PREFIXES):
        status, reason = parse_release_note_declaration(pr_body)
        if status is None:
            result.add(
                "Changes under src/ or infra/ require a Release Note declaration in the PR body: "
                "'Release-Note: required' or 'Release-Note: not-required' with 'Reason: ...'."
            )
        elif status == "required" and RELEASE_LOG_PATH not in changed_files:
            result.add(
                f"Release-Note: required but {RELEASE_LOG_PATH} was not updated "
                "(add an entry under `## v?.?.? (未確定)`)."
            )
        elif status == "not-required" and not reason:
            result.add(
                "Release-Note: not-required requires a non-empty 'Reason:' line in the PR body."
            )

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        dest="changed_files",
        help="Changed file path (repeatable). If omitted, read paths from stdin.",
    )
    parser.add_argument(
        "--pr-body",
        default="",
        help="Pull request body text (or set PR_BODY environment variable)",
    )
    args = parser.parse_args(argv)

    import os

    pr_body = args.pr_body or os.environ.get("PR_BODY", "")
    changed_files = args.changed_files or read_changed_files_from_stdin()
    result = validate_pr_workflow(changed_files, pr_body)

    if result.ok:
        return 0

    for error in result.errors:
        print(f"error: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
