from __future__ import annotations

import subprocess
from pathlib import Path

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


def test_git_diff_name_only_against_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True, capture_output=True)
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()

    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")
    subprocess.run(["git", "add", "src/app.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add src"], cwd=repo, check=True, capture_output=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()

    from scripts.validate_pr_workflow import git_diff_name_only

    changed = git_diff_name_only(base, head, cwd=repo)
    assert changed == ["src/app.py"]
