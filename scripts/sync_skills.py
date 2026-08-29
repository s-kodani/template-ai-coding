"""Sync Agent Skills from .agents/skills (canonical) to .claude/skills (generated)."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "scripts" / "skills-manifest.json"


def load_manifest(path: Path = MANIFEST_PATH) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def sync_skills(manifest: dict, *, check: bool = False) -> list[str]:
    source_root = REPO_ROOT / manifest["source"]
    target_root = REPO_ROOT / manifest["target"]
    errors: list[str] = []

    for skill_name in manifest["skills"]:
        source = source_root / skill_name
        target = target_root / skill_name

        if not source.is_dir():
            errors.append(f"missing source skill directory: {source}")
            continue

        if check:
            if not target.is_dir():
                errors.append(f"missing generated skill directory: {target}")
                continue
            source_files = {path.relative_to(source) for path in source.rglob("*") if path.is_file()}
            target_files = {path.relative_to(target) for path in target.rglob("*") if path.is_file()}
            if source_files != target_files:
                missing = sorted(source_files - target_files)
                extra = sorted(target_files - source_files)
                if missing:
                    errors.append(f"{target}: missing files {missing}")
                if extra:
                    errors.append(f"{target}: unexpected files {extra}")
            for rel_path in sorted(source_files & target_files):
                source_bytes = (source / rel_path).read_bytes()
                target_bytes = (target / rel_path).read_bytes()
                if source_bytes != target_bytes:
                    errors.append(f"{target / rel_path}: out of sync with {source / rel_path}")
        else:
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify .claude/skills matches .agents/skills without writing.",
    )
    args = parser.parse_args(argv)

    manifest = load_manifest()
    errors = sync_skills(manifest, check=args.check)

    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        if args.check:
            print(
                "Run `uv run python scripts/sync_skills.py` to regenerate .claude/skills.",
                file=sys.stderr,
            )
        return 1

    if args.check:
        print("Skills are in sync.")
    else:
        print(f"Synced {len(manifest['skills'])} skills to {manifest['target']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
