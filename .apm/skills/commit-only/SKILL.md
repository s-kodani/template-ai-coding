---
name: commit-only
description: Commit local changes on the current branch without pushing. Use when the user asks to commit only, create a local commit, or record current changes without remote push or PR creation.
---

# Commit Only

Use this skill when committing local changes on the current branch without pushing.

## Preconditions

- There are modified files.
- Commit messages follow `reference.md` and `delivery-reference.md`（`../commit-push-pr/delivery-reference.md`）。

## Workflow

1. Inspect uncommitted changes with `git status`, `git diff`, and `git diff --cached` as needed.
2. Generate a Japanese Conventional Commits-style message from the actual diff.
3. Stage changes with `git add -A`.
4. Commit with the generated message.

Read `reference.md` when generating the commit message. See `delivery-reference.md` for branch and quality-check rules.

## Example

```bash
git status
git diff
git add -A
git commit -m "fix: 不要なデバッグログ出力を削除" \
  -m "- ユーザー情報取得処理の冗長なログ行を削除" \
  -m "- 必要な情報は残しつつログボリュームを削減"
```
