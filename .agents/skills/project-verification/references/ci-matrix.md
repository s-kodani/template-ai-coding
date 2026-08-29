# CI Matrix

本リポジトリの GitHub Actions とローカル相当コマンド。

## `.github/workflows/ci.yml`

| Job | 内容 | ローカル相当 |
|---|---|---|
| quality | ruff, pytest | `uv run ruff check src tests scripts` / `uv run pytest` |
| security | bandit, uv audit, gitleaks | `uv run bandit -r src scripts -c pyproject.toml` |
| build-and-scan | docker compose build, Trivy CRITICAL/HIGH | `docker compose -f infra/app/compose.yml build` |

## `.github/workflows/okf.yml`

| Job | 内容 | ローカル相当 |
|---|---|---|
| okf | validate_okf + test_validate_okf | `uv run python scripts/validate_okf.py` |

## `.github/workflows/pr-workflow.yml`

| Job | 内容 |
|---|---|
| workflow | `scripts/validate_pr_workflow.py`（Issue 参照、Release Note 要否） |

## Branch protection（main）

必須チェック: `quality`, `security`, `build-and-scan`, `okf`（リポジトリ設定による）

## Skill sync（本 Issue で追加）

Skill 変更 PR では CI 前にローカルで:

```bash
uv run python scripts/sync_skills.py --check
```

不一致時:

```bash
uv run python scripts/sync_skills.py
```
