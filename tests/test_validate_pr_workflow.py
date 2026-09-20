from __future__ import annotations

import sys

from scripts.validate_pr_workflow import (
    RELEASE_LOG_PATH,
    validate_pr_workflow,
)


def test_requires_issue_reference_for_src_changes() -> None:
    result = validate_pr_workflow(
        changed_files=["src/knowledge_mcp/server.py"],
        pr_body="Summary only\n\nRelease-Note: required",
    )
    assert not result.ok
    assert any("Refs #" in error for error in result.errors)


def test_accepts_refs_for_src_changes() -> None:
    result = validate_pr_workflow(
        changed_files=["src/knowledge_mcp/server.py", RELEASE_LOG_PATH],
        pr_body="Refs #42\n\nRelease-Note: required",
    )
    assert result.ok, result.errors


def test_requires_refs_for_scripts_and_tests_changes() -> None:
    result = validate_pr_workflow(
        changed_files=["scripts/validate_pr_workflow.py", "tests/test_validate_pr_workflow.py"],
        pr_body="No issue link",
    )
    assert not result.ok
    assert any("Refs #" in error for error in result.errors)


def test_requires_refs_for_extended_prefixes() -> None:
    for path in (
        "infra/app/compose.yml",
        "e2e/test_auth.py",
        "gateway/src/app.py",
        ".apm/skills/implementation-workflow/SKILL.md",
    ):
        result = validate_pr_workflow(
            changed_files=[path],
            pr_body="Release-Note: not-required\nReason: n/a" if path.startswith("infra/") else "",
        )
        assert not result.ok, path
        assert any("Refs #" in error for error in result.errors), path


def test_issue_reference_not_required_for_lockfile_only() -> None:
    result = validate_pr_workflow(
        changed_files=["uv.lock", ".github/dependabot.yml"],
        pr_body="No issue link",
    )
    assert result.ok, result.errors


def test_requires_release_note_declaration_for_src_changes() -> None:
    result = validate_pr_workflow(
        changed_files=["src/knowledge_mcp/server.py"],
        pr_body="Refs #1",
    )
    assert not result.ok
    assert any("Release Note declaration" in error for error in result.errors)


def test_requires_release_log_when_declared_required() -> None:
    result = validate_pr_workflow(
        changed_files=["src/knowledge_mcp/server.py"],
        pr_body="Refs #1\n\nRelease-Note: required",
    )
    assert not result.ok
    assert any(RELEASE_LOG_PATH in error for error in result.errors)


def test_requires_release_log_for_infra_changes_when_required() -> None:
    result = validate_pr_workflow(
        changed_files=["infra/app/compose.yml"],
        pr_body="Refs #1\n\nRelease-Note: required",
    )
    assert not result.ok
    assert any(RELEASE_LOG_PATH in error for error in result.errors)


def test_passes_when_src_and_release_log_change() -> None:
    result = validate_pr_workflow(
        changed_files=["src/knowledge_mcp/server.py", RELEASE_LOG_PATH],
        pr_body="Refs #7\n\nRelease-Note: required",
    )
    assert result.ok, result.errors


def test_not_required_with_reason_skips_release_log() -> None:
    result = validate_pr_workflow(
        changed_files=["src/knowledge_mcp/server.py"],
        pr_body=(
            "Refs #1\n\n"
            "Release-Note: not-required\n"
            "Reason: Internal refactor with no observable behavior change."
        ),
    )
    assert result.ok, result.errors


def test_not_required_without_reason_fails() -> None:
    result = validate_pr_workflow(
        changed_files=["src/knowledge_mcp/server.py"],
        pr_body="Refs #1\n\nRelease-Note: not-required",
    )
    assert not result.ok
    assert any("Reason:" in error for error in result.errors)


def test_closes_keyword_is_rejected() -> None:
    result = validate_pr_workflow(
        changed_files=["src/foo.py", RELEASE_LOG_PATH],
        pr_body="This closes #99\n\nRelease-Note: required",
    )
    assert not result.ok
    assert any("Closes" in error or "auto-close" in error.lower() for error in result.errors)


def test_fixes_and_resolves_keywords_are_rejected() -> None:
    for body in ("Fixes #1\n\nRelease-Note: required", "Resolves #1\n\nRelease-Note: required"):
        result = validate_pr_workflow(
            changed_files=["src/foo.py", RELEASE_LOG_PATH],
            pr_body=body,
        )
        assert not result.ok, body


def test_refs_plus_closes_is_rejected() -> None:
    result = validate_pr_workflow(
        changed_files=["src/foo.py", RELEASE_LOG_PATH],
        pr_body="Refs #1\nCloses #1\n\nRelease-Note: required",
    )
    assert not result.ok


def test_verify_issue_exists_fails_on_missing_issue() -> None:
    result = validate_pr_workflow(
        changed_files=["scripts/validate_pr_workflow.py"],
        pr_body="Refs #99999",
        verify_issue_exists=True,
        issue_fetcher=lambda _owner, _repo, _number: None,
    )
    assert not result.ok
    assert any("does not exist" in error for error in result.errors)


def test_verify_issue_exists_allows_closed_issue() -> None:
    result = validate_pr_workflow(
        changed_files=["scripts/validate_pr_workflow.py"],
        pr_body="Refs #25",
        verify_issue_exists=True,
        issue_fetcher=lambda _owner, _repo, _number: {"number": 25, "state": "closed"},
    )
    assert result.ok, result.errors


def test_reads_changed_files_from_stdin(monkeypatch) -> None:
    import io

    from scripts.validate_pr_workflow import read_changed_files_from_stdin

    monkeypatch.setattr(sys, "stdin", io.StringIO("src/a.py\n\n"))
    assert read_changed_files_from_stdin() == ["src/a.py"]
