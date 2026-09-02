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

## Skill / Agent deploy

自前 Skill の正本は `.apm/skills/`。展開先は `.agents/skills/` と `.claude/skills/`。
自前 Agent の正本は `.apm/agents/`。展開先は `.cursor/agents/` と `.claude/agents/`。

Skill / Agent 変更 PR では CI 前にローカルで:

```bash
apm install
uv run python scripts/check_skill_deploy.py --check
```

`apm` が無い場合は、各自前 Skill ディレクトリと `*.agent.md` を展開先へコピーしてから check する。展開先の手編集はしない。
