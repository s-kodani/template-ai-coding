from __future__ import annotations

from pathlib import Path

from scripts.check_skill_deploy import check_agent_deploy


def _write_source(tmp_path: Path, stem: str, body: str = "# Agent\n") -> Path:
    source = tmp_path / ".apm" / "agents"
    source.mkdir(parents=True, exist_ok=True)
    path = source / f"{stem}.agent.md"
    path.write_text(body, encoding="utf-8")
    return path


def _write_deployed(tmp_path: Path, target: str, stem: str, body: str = "# Agent\n") -> Path:
    dest = tmp_path / target / "agents"
    dest.mkdir(parents=True, exist_ok=True)
    suffix = ".toml" if target == ".codex" else ".md"
    path = dest / f"{stem}{suffix}"
    path.write_text(body, encoding="utf-8")
    return path


def test_check_passes_when_source_matches_cursor_and_claude(tmp_path: Path) -> None:
    body = "---\nname: review\n---\n# Review\n"
    _write_source(tmp_path, "review", body)
    _write_deployed(tmp_path, ".cursor", "review", body)
    _write_deployed(tmp_path, ".claude", "review", body)

    assert check_agent_deploy(tmp_path) == []


def test_check_fails_when_cursor_copy_is_stale(tmp_path: Path) -> None:
    _write_source(tmp_path, "review", "# New\n")
    _write_deployed(tmp_path, ".cursor", "review", "# Old\n")
    _write_deployed(tmp_path, ".claude", "review", "# New\n")

    errors = check_agent_deploy(tmp_path)

    assert errors
    assert any("review" in error and "out of sync" in error for error in errors)


def test_check_fails_when_claude_copy_is_missing(tmp_path: Path) -> None:
    _write_source(tmp_path, "review", "# Review\n")
    _write_deployed(tmp_path, ".cursor", "review", "# Review\n")

    errors = check_agent_deploy(tmp_path)

    assert errors
    assert any("review" in error and "missing" in error for error in errors)


def test_check_fails_when_deployed_agent_has_no_source(tmp_path: Path) -> None:
    _write_deployed(tmp_path, ".cursor", "orphan", "# Orphan\n")
    _write_deployed(tmp_path, ".claude", "orphan", "# Orphan\n")

    errors = check_agent_deploy(tmp_path)

    assert errors
    assert any("orphan" in error for error in errors)


def test_check_ignores_missing_codex_toml(tmp_path: Path) -> None:
    body = "# Review\n"
    _write_source(tmp_path, "review", body)
    _write_deployed(tmp_path, ".cursor", "review", body)
    _write_deployed(tmp_path, ".claude", "review", body)

    assert check_agent_deploy(tmp_path) == []


def test_check_does_not_compare_codex_toml_bytes(tmp_path: Path) -> None:
    body = "# Review\n"
    _write_source(tmp_path, "review", body)
    _write_deployed(tmp_path, ".cursor", "review", body)
    _write_deployed(tmp_path, ".claude", "review", body)
    _write_deployed(tmp_path, ".codex", "review", "name = 'review'\n")

    assert check_agent_deploy(tmp_path) == []
