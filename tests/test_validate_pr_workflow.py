from __future__ import annotations

import sys

from scripts.validate_pr_workflow import (
    RELEASE_LOG_PATH,
    validate_pr_workflow,
)


def test_requires_issue_reference_for_src_changes() -> None:
    result = validate_pr_workflow(
        changed_files=["src/knowledge_mcp/server.py"],
        pr_body="Summary only",
    )
    assert not result.ok
    assert any("issue reference" in error for error in result.errors)


def test_accepts_issue_reference_for_src_changes() -> None:
    result = validate_pr_workflow(
        changed_files=["src/knowledge_mcp/server.py", RELEASE_LOG_PATH],
        pr_body="Refs #42\n\n## Summary",
    )
    assert result.ok, result.errors


def test_issue_reference_not_required_without_src_changes() -> None:
    result = validate_pr_workflow(
        changed_files=["scripts/validate_pr_workflow.py", "tests/test_validate_pr_workflow.py"],
        pr_body="No issue link",
    )
    assert result.ok, result.errors


def test_requires_release_log_for_src_changes() -> None:
    result = validate_pr_workflow(
        changed_files=["src/knowledge_mcp/server.py"],
        pr_body="Refs #1",
    )
    assert not result.ok
    assert any(RELEASE_LOG_PATH in error for error in result.errors)


def test_requires_release_log_for_infra_changes() -> None:
    result = validate_pr_workflow(
        changed_files=["infra/app/compose.yml"],
        pr_body="Refs #1",
    )
    assert not result.ok
    assert any(RELEASE_LOG_PATH in error for error in result.errors)


def test_passes_when_src_and_release_log_change() -> None:
    result = validate_pr_workflow(
        changed_files=["src/knowledge_mcp/server.py", RELEASE_LOG_PATH],
        pr_body="Closes #7",
    )
    assert result.ok, result.errors


def test_closes_keyword_is_accepted() -> None:
    result = validate_pr_workflow(
        changed_files=["src/foo.py", RELEASE_LOG_PATH],
        pr_body="This closes #99",
    )
    assert result.ok, result.errors


def test_reads_changed_files_from_stdin(monkeypatch) -> None:
    import io

    from scripts.validate_pr_workflow import read_changed_files_from_stdin

    monkeypatch.setattr(sys, "stdin", io.StringIO("src/a.py\n\n"))
    assert read_changed_files_from_stdin() == ["src/a.py"]
