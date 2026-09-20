#!/usr/bin/env python3
"""Validate pull request workflow requirements (issue linkage, release log)."""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

ISSUE_REF_PREFIXES = (
    "src/",
    "tests/",
    "scripts/",
    "infra/",
    "e2e/",
    "gateway/",
    ".apm/",
)
RELEASE_LOG_TRIGGER_PREFIXES = ("src/", "infra/")
RELEASE_LOG_PATH = "docs/releases/log.md"
REFS_ISSUE_RE = re.compile(r"(?:^|\b)refs?\s*#(\d+)", re.IGNORECASE)
AUTO_CLOSE_ISSUE_RE = re.compile(
    r"(?:^|\b)(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*#\d+",
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

IssueFetcher = Callable[[str, str, int], dict[str, Any] | None]


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


def extract_refs_issue_numbers(pr_body: str | None) -> list[int]:
    if not pr_body:
        return []
    return [int(match) for match in REFS_ISSUE_RE.findall(pr_body)]


def has_auto_close_keyword(pr_body: str | None) -> bool:
    if not pr_body:
        return False
    return AUTO_CLOSE_ISSUE_RE.search(pr_body) is not None


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


def fetch_github_issue(owner: str, repo: str, number: int) -> dict[str, Any] | None:
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "template-ai-coding-pr-workflow",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}"
    with httpx.Client(timeout=10.0) as client:
        response = client.get(url, headers=headers)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()


def _repository_owner_name() -> tuple[str, str]:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    owner, sep, name = repository.partition("/")
    if not sep or not owner or not name:
        raise ValueError(
            "GITHUB_REPOSITORY must be set to 'owner/repo' when --verify-issue-exists is used."
        )
    return owner, name


def validate_pr_workflow(
    changed_files: list[str],
    pr_body: str | None,
    *,
    verify_issue_exists: bool = False,
    issue_fetcher: IssueFetcher | None = None,
) -> ValidationResult:
    result = ValidationResult()

    if has_auto_close_keyword(pr_body):
        result.add(
            "PR body must not use Closes/Close/Fixes/Resolves #<issue>; "
            "use 'Refs #<issue>' so merge does not auto-close the issue."
        )

    refs_numbers = extract_refs_issue_numbers(pr_body)
    if has_prefix(changed_files, ISSUE_REF_PREFIXES) and not refs_numbers:
        result.add(
            "PR body must include an issue reference such as "
            "'Refs #123' when src/, tests/, scripts/, infra/, e2e/, gateway/, "
            "or .apm/ files change."
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

    if verify_issue_exists and refs_numbers:
        if issue_fetcher is None:
            owner, repo = _repository_owner_name()
            fetcher = fetch_github_issue
        else:
            owner, repo = "owner", "repo"
            fetcher = issue_fetcher
        for number in refs_numbers:
            issue = fetcher(owner, repo, number)
            if issue is None:
                result.add(f"Referenced issue #{number} does not exist in {owner}/{repo}.")

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
    parser.add_argument(
        "--verify-issue-exists",
        action="store_true",
        help="Confirm each Refs #<issue> exists via the GitHub Issues API.",
    )
    args = parser.parse_args(argv)

    pr_body = args.pr_body or os.environ.get("PR_BODY", "")
    changed_files = args.changed_files or read_changed_files_from_stdin()
    try:
        result = validate_pr_workflow(
            changed_files,
            pr_body,
            verify_issue_exists=args.verify_issue_exists,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if result.ok:
        return 0

    for error in result.errors:
        print(f"error: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
