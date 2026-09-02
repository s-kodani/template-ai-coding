from __future__ import annotations

from pathlib import Path

from scripts.check_skill_deploy import check_skill_deploy


def _write_skill(root: Path, name: str, body: str = "# Skill\n") -> None:
    skill = root / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(body, encoding="utf-8")


def _layout(tmp_path: Path) -> tuple[Path, Path, Path]:
    apm = tmp_path / ".apm" / "skills"
    agents = tmp_path / ".agents" / "skills"
    claude = tmp_path / ".claude" / "skills"
    apm.mkdir(parents=True)
    agents.mkdir(parents=True)
    claude.mkdir(parents=True)
    return apm, agents, claude


def test_check_passes_when_first_party_and_external_skills_match(tmp_path: Path) -> None:
    apm, agents, claude = _layout(tmp_path)
    _write_skill(apm, "local-skill")
    _write_skill(agents, "local-skill")
    _write_skill(claude, "local-skill")
    _write_skill(agents, "upstream-skill", "# Upstream\n")
    _write_skill(claude, "upstream-skill", "# Upstream\n")

    assert check_skill_deploy(tmp_path) == []


def test_check_fails_when_first_party_dest_is_stale(tmp_path: Path) -> None:
    apm, agents, claude = _layout(tmp_path)
    _write_skill(apm, "local-skill", "# New\n")
    _write_skill(agents, "local-skill", "# Old\n")
    _write_skill(claude, "local-skill", "# New\n")

    errors = check_skill_deploy(tmp_path)

    assert errors
    assert any("local-skill" in error and "out of sync" in error for error in errors)


def test_check_fails_when_external_skills_differ_across_targets(tmp_path: Path) -> None:
    _apm, agents, claude = _layout(tmp_path)
    _write_skill(agents, "upstream-skill", "# Agents\n")
    _write_skill(claude, "upstream-skill", "# Claude\n")

    errors = check_skill_deploy(tmp_path)

    assert errors
    assert any("upstream-skill" in error for error in errors)


def test_check_fails_when_a_deployed_skill_is_missing_from_one_target(tmp_path: Path) -> None:
    _apm, agents, _claude = _layout(tmp_path)
    _write_skill(agents, "upstream-skill")

    errors = check_skill_deploy(tmp_path)

    assert errors
    assert any("upstream-skill" in error for error in errors)
