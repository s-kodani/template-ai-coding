"""Reject incomplete delivery using GitHub state, including the original no-PR incident."""

from __future__ import annotations

from copy import deepcopy

import pytest

SHA = "a" * 40
REPO = "owner/repo"
PREFIX = "repos/owner/repo"
CHECKS = ("quality", "security", "build-and-scan", "okf", "workflow")


def state(*, merged=False):
    return {
        f"{PREFIX}/issues/139": {
            "state": "open",
            "body": "## Acceptance Criteria\n- [x] implemented\n\n## Work PRs\n- #142\n",
        },
        f"{PREFIX}/pulls/142": {
            "state": "closed" if merged else "open", "merged": merged,
            "merged_at": "2026-11-15T00:00:00Z" if merged else None,
            "body": "Refs #139", "head": {"sha": SHA},
            "base": {"ref": "main", "repo": {"full_name": REPO}},
            "user": {"login": "author"},
        },
        f"{PREFIX}/commits/{SHA}/check-runs?filter=latest&per_page=100": {
            "check_runs": [
                {"name": name, "head_sha": SHA, "status": "completed", "conclusion": "success",
                 "app": {"slug": "github-actions"}}
                for name in CHECKS
            ]
        },
        f"{PREFIX}/pulls/142/reviews?per_page=100": [
            {"state": "APPROVED", "commit_id": SHA, "user": {"login": "reviewer", "type": "User"},
             "author_association": "COLLABORATOR"}
        ],
    }


def validate(data, *, phase="close", prs=None, sha=SHA):
    from scripts.validate_delivery import validate_delivery

    return validate_delivery(
        REPO, 139, [142] if prs is None else prs,
        phase=phase, expected_sha=sha, read_json=lambda path: deepcopy(data[path]),
    )


def test_original_incident_all_ac_checked_but_no_pr_is_not_completion():
    result = validate(state(), prs=[])
    assert not result.ok
    assert any("PR_REQUIRED" in error for error in result.errors)


def test_pushed_head_with_registered_open_pr_is_submitted_not_issue_completion():
    data = state()
    assert validate(data, phase="submitted").ok
    assert not validate(data, phase="close").ok


@pytest.mark.parametrize("kind", ["unmerged", "wrong-head", "wrong-base", "wrong-issue", "closed-issue"])
def test_incomplete_or_unrelated_remote_state_is_rejected(kind):
    data = state(merged=True)
    pull = data[f"{PREFIX}/pulls/142"]
    if kind == "unmerged":
        pull.update(merged=False, merged_at=None)
    elif kind == "wrong-head":
        pull["head"]["sha"] = "b" * 40
    elif kind == "wrong-base":
        pull["base"]["ref"] = "other"
    elif kind == "wrong-issue":
        pull["body"] = "Refs #999"
    else:
        data[f"{PREFIX}/issues/139"]["state"] = "closed"
    assert not validate(data, phase="submitted" if kind == "wrong-head" else "close").ok


@pytest.mark.parametrize("body", [
    "## Acceptance Criteria\n- [x] done\n",
    "## Acceptance Criteria\n- [x] done\n## Work PRs\n- #142\n- #143\n",
])
def test_missing_registration_or_omitted_followup_pr_is_rejected(body):
    data = state(merged=True)
    data[f"{PREFIX}/issues/139"]["body"] = body
    assert not validate(data).ok


@pytest.mark.parametrize("task", ["- [ ] pending", "- [~] unknown", "- [x]", "no criteria"])
def test_incomplete_empty_or_malformed_acceptance_criteria_is_rejected(task):
    data = state(merged=True)
    data[f"{PREFIX}/issues/139"]["body"] = f"## Acceptance Criteria\n{task}\n## Work PRs\n- #142\n"
    assert not validate(data).ok


@pytest.mark.parametrize("marker", ["*", "+", "1.", "1)", "> -", "> > +"])
def test_mixed_markdown_task_markers_cannot_hide_unchecked_criteria(marker):
    data = state(merged=True)
    data[f"{PREFIX}/issues/139"]["body"] = (
        f"## Acceptance Criteria\n- [x] implemented\n{marker} [ ] pending\n"
        "## Work PRs\n- #142\n"
    )
    assert not validate(data).ok


def test_complete_criteria_with_mixed_markdown_task_markers_pass():
    data = state(merged=True)
    data[f"{PREFIX}/issues/139"]["body"] = (
        "## Acceptance Criteria\n- [x] first\n* [X] second\n+ [x] third\n"
        "1. [x] fourth\n2) [x] fifth\n## Work PRs\n- #142\n"
    )
    assert validate(data).ok


@pytest.mark.parametrize("defect", ["failure", "missing", "stale", "untrusted-app"])
def test_ci_must_succeed_for_the_final_sha(defect):
    data = state(merged=True)
    runs = data[f"{PREFIX}/commits/{SHA}/check-runs?filter=latest&per_page=100"]["check_runs"]
    if defect == "failure":
        runs[0]["conclusion"] = "failure"
    elif defect == "missing":
        runs.pop()
    elif defect == "stale":
        runs[0]["head_sha"] = "b" * 40
    else:
        runs[0]["app"]["slug"] = "other-app"
    assert not validate(data).ok


@pytest.mark.parametrize("defect", ["missing", "stale", "changes", "dismissed", "bot", "author"])
def test_review_must_be_current_valid_human_approval(defect):
    data = state(merged=True)
    reviews = data[f"{PREFIX}/pulls/142/reviews?per_page=100"]
    if defect == "missing":
        reviews.clear()
    elif defect == "stale":
        reviews[0]["commit_id"] = "b" * 40
    elif defect in {"changes", "dismissed"}:
        reviews.append({**reviews[0], "state": "CHANGES_REQUESTED" if defect == "changes" else "DISMISSED"})
    elif defect == "bot":
        reviews[0]["user"]["type"] = "Bot"
    else:
        reviews[0]["user"]["login"] = "author"
    assert not validate(data).ok


def test_merged_delivery_with_current_ci_review_and_complete_ac_passes():
    assert validate(state(merged=True)).ok


@pytest.mark.parametrize("login", ["author", "maintainer"])
def test_human_merge_is_approval_even_without_a_formal_review(login):
    data = state(merged=True)
    data[f"{PREFIX}/pulls/142"]["merged_by"] = {"type": "User", "login": login}
    data[f"{PREFIX}/pulls/142/reviews?per_page=100"] = []
    assert validate(data).ok


@pytest.mark.parametrize("merger", [
    None, {}, {"type": "Bot", "login": "automation[bot]"},
    {"type": "unknown", "login": "maintainer"},
    {"type": "User", "login": ""}, {"type": "User", "login": " "},
    {"type": "User", "login": 123},
])
def test_bot_or_unknown_merge_without_human_approval_is_rejected(merger):
    data = state(merged=True)
    data[f"{PREFIX}/pulls/142"]["merged_by"] = merger
    data[f"{PREFIX}/pulls/142/reviews?per_page=100"] = []
    result = validate(data)
    assert not result.ok
    assert any("REVIEW_REQUIRED" in error for error in result.errors)


def test_bot_merge_can_use_current_human_review_approval():
    data = state(merged=True)
    data[f"{PREFIX}/pulls/142"]["merged_by"] = {"type": "Bot", "login": "automation[bot]"}
    assert validate(data).ok


def test_human_merge_does_not_override_unresolved_changes_requested():
    data = state(merged=True)
    data[f"{PREFIX}/pulls/142"]["merged_by"] = {"type": "User", "login": "author"}
    data[f"{PREFIX}/pulls/142/reviews?per_page=100"][0]["state"] = "CHANGES_REQUESTED"
    result = validate(data)
    assert not result.ok
    assert any("REVIEW_REQUIRED" in error for error in result.errors)


@pytest.mark.parametrize("defect, error", [
    ("ci-failure", "CI_NOT_SUCCESSFUL"), ("ci-stale", "CI_NOT_SUCCESSFUL"),
    ("ac", "AC_INCOMPLETE"), ("unmerged", "PR_NOT_MERGED"),
    ("api", "API_UNAVAILABLE"), ("reviews-api", "API_UNAVAILABLE"),
])
def test_human_merge_still_requires_all_other_close_conditions(defect, error):
    data = state(merged=True)
    data[f"{PREFIX}/pulls/142"]["merged_by"] = {"type": "User", "login": "author"}
    data[f"{PREFIX}/pulls/142/reviews?per_page=100"] = []
    checks_path = f"{PREFIX}/commits/{SHA}/check-runs?filter=latest&per_page=100"
    if defect == "ci-failure":
        data[checks_path]["check_runs"][0]["conclusion"] = "failure"
    elif defect == "ci-stale":
        data[checks_path]["check_runs"][0]["head_sha"] = "b" * 40
    elif defect == "ac":
        data[f"{PREFIX}/issues/139"]["body"] = data[f"{PREFIX}/issues/139"]["body"].replace(
            "[x]", "[ ]"
        )
    elif defect == "unmerged":
        data[f"{PREFIX}/pulls/142"].update(state="open", merged=False, merged_at=None)
    elif defect == "api":
        del data[checks_path]
    else:
        del data[f"{PREFIX}/pulls/142/reviews?per_page=100"]
    result = validate(data)
    assert not result.ok
    assert any(error in message for message in result.errors)


@pytest.mark.parametrize("reviews", [{}, "", None])
def test_human_merge_does_not_accept_malformed_review_api_responses(reviews):
    data = state(merged=True)
    data[f"{PREFIX}/pulls/142"]["merged_by"] = {"type": "User", "login": "author"}
    data[f"{PREFIX}/pulls/142/reviews?per_page=100"] = reviews
    result = validate(data)
    assert not result.ok
    assert any("API_UNAVAILABLE" in message for message in result.errors)


def test_github_failure_cannot_be_treated_as_no_remaining_work():
    from scripts.validate_delivery import validate_delivery

    def unavailable(_path):
        raise RuntimeError("private response must not be printed")

    result = validate_delivery(REPO, 139, [142], phase="close", read_json=unavailable)
    assert not result.ok
    assert "private response" not in str(result.errors)


def test_github_reader_combines_all_review_pages(monkeypatch):
    import json
    import shutil
    import subprocess

    from scripts.validate_delivery import github_read

    monkeypatch.setattr(shutil, "which", lambda _: "/fixed/gh")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(
        args[0], 0, json.dumps([[{"state": "APPROVED"}], [{"state": "CHANGES_REQUESTED"}]]), ""
    ))
    assert github_read("repos/owner/repo/pulls/142/reviews?per_page=100") == [
        {"state": "APPROVED"}, {"state": "CHANGES_REQUESTED"}
    ]


def test_one_submission_can_belong_to_a_multi_pr_issue():
    data = state()
    data[f"{PREFIX}/issues/139"]["body"] += "- #143\n"
    assert validate(data, phase="submitted").ok


@pytest.mark.parametrize("defect", ["dirty", "default-branch"])
def test_submission_cli_rejects_uncommitted_or_default_branch_state(monkeypatch, capsys, defect):
    from scripts import validate_delivery as delivery

    def git(_program, *args):
        if args == ("status", "--porcelain"):
            return " M src/example.py\n" if defect == "dirty" else ""
        if args == ("branch", "--show-current"):
            return "main\n"
        raise AssertionError("Invalid local state must be rejected before reading remote state")

    monkeypatch.setattr(delivery, "_command", git)
    assert delivery.main(["--repo", REPO, "--issue", "139", "--pr", "142", "--phase", "submitted"]) == 1
    assert "LOCAL_STATE_INVALID" in capsys.readouterr().out


def test_malformed_github_response_is_not_success():
    from scripts.validate_delivery import validate_delivery

    result = validate_delivery(REPO, 139, [142], phase="close", read_json=lambda _: {})
    assert not result.ok
    assert "API_UNAVAILABLE" in result.errors[0]


def test_github_reader_combines_all_check_pages(monkeypatch):
    import json
    import shutil
    import subprocess

    from scripts.validate_delivery import github_read

    monkeypatch.setattr(shutil, "which", lambda _: "/fixed/gh")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(
        args[0], 0, json.dumps([{"check_runs": [{"name": "quality"}]}, {"check_runs": [{"name": "workflow"}]}]), ""
    ))
    assert github_read("repos/owner/repo/commits/sha/check-runs?per_page=100") == {
        "check_runs": [{"name": "quality"}, {"name": "workflow"}]
    }
