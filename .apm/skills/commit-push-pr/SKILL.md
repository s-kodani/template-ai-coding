---
name: commit-push-pr
description: Commit local changes, push the current branch, and create a Pull Request. Use when the user asks to commit, push, and open a PR in one workflow.
---

# Commit, Push, And Create PR

Use this skill when committing local changes, pushing the current branch, and opening a Pull Request.

## Preconditions

- There are modified files.
- Remote `origin` is configured.
- Work is on a feature branch, not the default base branch（`main` / `master` への直接作業は禁止）。
- Commit and PR messages follow `reference.md` and `delivery-reference.md`.

## Workflow

1. Check the current branch and reject direct work on `main` or `master`.
2. Inspect the actual diff and commit history.
3. Run project-appropriate quality checks（`delivery-reference.md` / `project-verification` Skill）。
4. Stage and commit changes.
5. Push the branch to `origin`.
6. Create a PR using **ManagePullRequest** tool（またはリポジトリ標準の PR API）。`gh pr create` に依存しない。

Read `reference.md` and `delivery-reference.md` when generating the commit message, PR title, or PR body.

## PR Generation Inputs

Use these sources when preparing the PR title and body（base branch は環境指定を優先）:

```bash
git branch --show-current
git merge-base origin/main HEAD
git diff --name-status $(git merge-base origin/main HEAD)...HEAD
git diff --stat $(git merge-base origin/main HEAD)...HEAD
git log origin/main..HEAD --oneline
```

## Branch Prefix To PR Prefix（参考）

リポジトリ／Cloud Agent のブランチ命名（例: `cursor/`）が優先。下表は Conventional Commits プレフィックスの参考。

| Branch prefix | PR prefix |
|---------------|-----------|
| `feature/` | `feat` |
| `fix/` | `fix` |
| `refactor/` | `refactor` |
| `perf/` | `perf` |
| `test/` | `test` |
| `docs/` | `docs` |
| `build/` | `build` |
| `ci/` | `ci` |
| `chore/` | `chore` |
| `cursor/` | `chore` または変更内容に合わせて選択 |
