"""Read-only gates for PR submission and post-merge Issue completion.

This does not restrict direct GitHub mutations through other tools.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess  # nosec B404
from collections.abc import Callable
from typing import Any

from scripts.validate_pr_workflow import ValidationResult, extract_refs_issue_numbers

REQUIRED_CHECKS = frozenset({"quality", "security", "build-and-scan", "okf", "workflow"})


def _command(program: str, *args: str) -> str:
    executable = shutil.which(program)
    if executable is None:
        raise RuntimeError("Required executable unavailable")
    # program is fixed by the callers; API paths and git arguments are not shell code.
    return subprocess.run(  # nosec B603
        [executable, *args], text=True, capture_output=True, check=True, timeout=60
    ).stdout


def github_read(path: str) -> Any:
    pages = json.loads(_command("gh", "api", "--paginate", "--slurp", path))
    if not isinstance(pages, list) or not pages:
        raise ValueError("Incomplete API response")
    if all(isinstance(page, list) for page in pages):
        return [item for page in pages for item in page]
    if all(isinstance(page, dict) and "check_runs" in page for page in pages):
        return {"check_runs": [item for page in pages for item in page["check_runs"]]}
    if len(pages) == 1 and isinstance(pages[0], dict):
        return pages[0]
    raise ValueError("Unsupported paginated API response")


def _section(body: str, heading: str) -> str:
    start = re.search(rf"(?m)^##[ \t]+(?:{heading})[ \t]*\r?$", body)
    if start is None:
        return ""
    return re.split(r"(?m)^#{1,2}[ \t]+", body[start.end():], maxsplit=1)[0]


def _registered_prs(body: str) -> set[int]:
    rows = [line.strip() for line in _section(body, "Work PRs").splitlines() if line.strip()]
    matches = [re.fullmatch(r"-[ \t]+#([1-9][0-9]*)", row) for row in rows]
    if not rows or not all(matches):
        return set()
    numbers = [int(match[1]) for match in matches if match]
    return set(numbers) if len(numbers) == len(set(numbers)) else set()


def _complete_ac(body: str) -> bool:
    section = _section(body, "Acceptance Criteria|受入条件|受け入れ条件")
    tasks = re.findall(r"(?m)^[ \t>]*(?:[-+*]|[0-9]+[.)])[ \t]+\[([^\]]*)\](.*)$", section)
    return bool(tasks) and all(status.lower() == "x" and label.strip() for status, label in tasks)


def _approved(reviews: list[dict], sha: str, author: str, merged_by: dict | None) -> bool:
    decisions = {}
    for review in reviews:  # GitHub returns reviews chronologically, across every fetched page.
        user = review["user"]
        if user["type"] != "User" or user["login"] == author:
            continue
        if review.get("author_association") not in {"OWNER", "MEMBER", "COLLABORATOR"}:
            continue
        if review["state"] in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
            decisions[user["login"]] = review
    if any(review["state"] == "CHANGES_REQUESTED" for review in decisions.values()):
        return False
    human_merge = (
        isinstance(merged_by, dict) and merged_by.get("type") == "User"
        and isinstance(merged_by.get("login"), str) and bool(merged_by["login"].strip())
    )
    return human_merge or any(
        review["state"] == "APPROVED" and review["commit_id"] == sha
        for review in decisions.values()
    )


def validate_delivery(
    repository: str,
    issue_number: int,
    pr_numbers: list[int],
    *,
    phase: str,
    expected_sha: str | None = None,
    read_json: Callable[[str], Any] = github_read,
) -> ValidationResult:
    result = ValidationResult()
    if (
        not re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+", repository)
        or repository.split("/")[-1] in {".", ".."}
        or issue_number < 1 or phase not in {"submitted", "close"}
    ):
        result.add("INVALID_INPUT")
        return result
    if not pr_numbers or any(number < 1 for number in pr_numbers):
        result.add("PR_REQUIRED: at least one registered work PR is required")
        return result
    if len(pr_numbers) != len(set(pr_numbers)):
        result.add("PR_SET_MISMATCH: duplicate PR numbers")
        return result
    if phase == "submitted" and (
        len(pr_numbers) != 1 or not re.fullmatch(r"[a-f0-9]{40}", expected_sha or "")
    ):
        result.add("HEAD_REQUIRED: submission checks one PR against local HEAD")
        return result
    prefix = f"repos/{repository}"
    try:
        issue = read_json(f"{prefix}/issues/{issue_number}")
        if issue["state"] != "open" or "pull_request" in issue:
            result.add("ISSUE_NOT_OPEN")
        body = issue["body"] or ""
        registered = _registered_prs(body)
        selected = set(pr_numbers)
        if not registered or (
            selected != registered if phase == "close" else not selected.issubset(registered)
        ):
            result.add("PR_SET_MISMATCH: register every required PR in Issue Work PRs")
            return result
        if phase == "close" and not _complete_ac(body):
            result.add("AC_INCOMPLETE: nonempty Acceptance Criteria must all be checked")
        for number in pr_numbers:
            pull = read_json(f"{prefix}/pulls/{number}")
            sha = pull["head"]["sha"]
            if not re.fullmatch(r"[a-f0-9]{40}", sha):
                raise ValueError("Unknown head")
            if (
                pull["base"]["repo"]["full_name"].lower() != repository.lower()
                or pull["base"]["ref"] != "main"
                or issue_number not in extract_refs_issue_numbers(pull["body"])
            ):
                result.add(f"PR_BINDING_INVALID: #{number}")
            if phase == "submitted":
                if pull["state"] != "open":
                    result.add(f"PR_NOT_OPEN: #{number}")
                if sha != expected_sha:
                    result.add(f"HEAD_MISMATCH: #{number}")
                continue
            if pull["merged"] is not True or not pull["merged_at"] or pull["state"] != "closed":
                result.add(f"PR_NOT_MERGED: #{number}")
            checks = read_json(f"{prefix}/commits/{sha}/check-runs?filter=latest&per_page=100")
            latest = {}
            for check in checks["check_runs"]:
                if check["app"]["slug"] == "github-actions":
                    old = latest.get(check["name"])
                    if old is None or check.get("id", 0) > old.get("id", 0):
                        latest[check["name"]] = check
            if not all(
                name in latest and latest[name]["head_sha"] == sha
                and latest[name]["status"] == "completed"
                and latest[name]["conclusion"] == "success"
                for name in REQUIRED_CHECKS
            ):
                result.add(f"CI_NOT_SUCCESSFUL: #{number} final HEAD checks are incomplete")
            reviews = read_json(f"{prefix}/pulls/{number}/reviews?per_page=100")
            if not isinstance(reviews, list):
                raise TypeError("Unknown review response")
            if not _approved(reviews, sha, pull["user"]["login"], pull.get("merged_by")):
                result.add(f"REVIEW_REQUIRED: #{number} needs human merge/review approval with no unresolved changes")
    except Exception:  # noqa: BLE001 - unknown/failed reads must fail closed without leaking responses
        result.add("API_UNAVAILABLE: GitHub state could not be fully verified")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--pr", type=int, action="append", required=True)
    parser.add_argument("--phase", choices=("submitted", "close"), required=True)
    args = parser.parse_args(argv)
    sha = None
    if args.phase == "submitted":
        try:
            if _command("git", "status", "--porcelain").strip():
                raise ValueError("Uncommitted changes")
            if _command("git", "branch", "--show-current").strip() in {"main", "master", ""}:
                raise ValueError("Feature branch required")
            sha = _command("git", "rev-parse", "HEAD").strip()
        except Exception:  # noqa: BLE001 - incomplete local state cannot count as delivery
            print(json.dumps({"ok": False, "errors": ["LOCAL_STATE_INVALID"]}))
            return 1
    result = validate_delivery(
        args.repo, args.issue, args.pr, phase=args.phase, expected_sha=sha,
        read_json=github_read,
    )
    print(json.dumps({"ok": result.ok, "phase": args.phase, "head": sha, "errors": result.errors}))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
