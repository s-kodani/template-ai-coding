"""Check that APM-deployed skills and agents match first-party sources."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _skill_names(root: Path) -> set[str]:
    if not root.is_dir():
        return set()
    return {path.name for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")}


def _files(root: Path) -> set[Path]:
    return {path.relative_to(root) for path in root.rglob("*") if path.is_file()}


def _compare_trees(source: Path, dest: Path) -> list[str]:
    if not dest.is_dir():
        return [f"missing skill directory: {dest}"]

    errors: list[str] = []
    source_files = _files(source)
    dest_files = _files(dest)
    missing = sorted(source_files - dest_files)
    extra = sorted(dest_files - source_files)
    if missing:
        errors.append(f"{dest}: missing files {missing}")
    if extra:
        errors.append(f"{dest}: unexpected files {extra}")
    for rel_path in sorted(source_files & dest_files):
        if (source / rel_path).read_bytes() != (dest / rel_path).read_bytes():
            errors.append(f"{dest / rel_path}: out of sync with {source / rel_path}")
    return errors


def _agent_stems(root: Path, suffix: str) -> dict[str, Path]:
    if not root.is_dir():
        return {}
    stems: dict[str, Path] = {}
    for path in root.iterdir():
        if path.is_file() and path.name.endswith(suffix):
            stems[path.name[: -len(suffix)]] = path
    return stems


def check_agent_deploy(repo_root: Path) -> list[str]:
    source = _agent_stems(repo_root / ".apm" / "agents", ".agent.md")
    cursor = _agent_stems(repo_root / ".cursor" / "agents", ".md")
    claude = _agent_stems(repo_root / ".claude" / "agents", ".md")
    errors: list[str] = []

    for stem, src_path in sorted(source.items()):
        for label, deployed in ((".cursor/agents", cursor), (".claude/agents", claude)):
            dest_path = deployed.get(stem)
            if dest_path is None:
                errors.append(f"{label}/{stem}.md: missing")
                continue
            if dest_path.read_bytes() != src_path.read_bytes():
                errors.append(f"{label}/{stem}.md: out of sync with {src_path}")

    extras = sorted((set(cursor) | set(claude)) - set(source))
    for stem in extras:
        errors.append(f"deployed agent has no source: {stem}")

    return errors


def check_skill_deploy(repo_root: Path) -> list[str]:
    apm = repo_root / ".apm" / "skills"
    agents = repo_root / ".agents" / "skills"
    claude = repo_root / ".claude" / "skills"
    errors: list[str] = []

    first_party = _skill_names(apm)
    for name in sorted(first_party):
        source = apm / name
        errors.extend(_compare_trees(source, agents / name))
        errors.extend(_compare_trees(source, claude / name))

    agents_names = _skill_names(agents)
    claude_names = _skill_names(claude)
    only_agents = sorted(agents_names - claude_names)
    only_claude = sorted(claude_names - agents_names)
    if only_agents or only_claude:
        errors.append(
            "deployed skill set mismatch: "
            f"only in .agents/skills: {only_agents}; only in .claude/skills: {only_claude}"
        )

    for name in sorted((agents_names & claude_names) - first_party):
        errors.extend(_compare_trees(agents / name, claude / name))

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Accepted for compatibility. This command only checks; it never writes.",
    )
    parser.parse_args(argv)

    errors = check_skill_deploy(REPO_ROOT) + check_agent_deploy(REPO_ROOT)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        print(
            "Edit `.apm/skills/` or `.apm/agents/` then run `apm install` "
            "(or copy first-party files to the Cursor / Claude deploy paths).",
            file=sys.stderr,
        )
        return 1

    print("Skills and agents are in sync.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
