---
name: commit-push
description: Commit local changes and push the current branch to origin. Use when the user asks to commit and push, push current changes, or publish the current branch without creating a PR.
---

# Commit And Push

Use this skill when committing local changes and pushing the current branch.

## Preconditions

- There are modified files.
- Remote `origin` is configured.
- Commit messages follow `reference.md` and `../commit-push-pr/delivery-reference.md`.

## Workflow

1. Check the current branch.
2. Do not push directly to `main` or `master`.
3. Run project-appropriate quality checks when relevant.
4. Stage changes with `git add -A`.
5. Commit with a message generated from the actual diff.
6. Push with `git push -u origin <current-branch>`.

Read `reference.md` when generating the commit message. See `../commit-push-pr/delivery-reference.md` for branch, PR, and quality-check rules.

## Example

```bash
BRANCH=$(git branch --show-current)
if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
  echo "main/master への直接プッシュは禁止です"
  exit 1
fi

git status
git diff
git add -A
git commit -m "fix: 不要なデバッグログ出力を削除"
git push -u origin "$BRANCH"
```
