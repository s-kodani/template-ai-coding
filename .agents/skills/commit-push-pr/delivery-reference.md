# Delivery Reference (Commit / Push / PR)

Commit / push / PR 系 Skill 共通のリポジトリ運用ルール。

## Commit Message

`reference.md` の Conventional Commits（日本語）に従う。Issue 参照は `Refs: #<issue>` を本文に含めてよい。

## Branch

- デフォルト base branch はリモートの `main`（Cloud Agent 等で別 base が指定されている場合はそれを優先）
- `main` / `master` への直接 commit / push は禁止
- ブランチ命名はリポジトリ／実行環境の規則に従う（例: `cursor/<descriptive-name>-<suffix>`）

## Pull Request

- PR 作成は **ManagePullRequest ツール**（またはリポジトリ標準の PR API）を優先する
- `gh pr create` は read-only 環境では使えない場合がある。CLI に依存しない
- 作成前に `.github/PULL_REQUEST_TEMPLATE.md` があれば確認する
- PR 本文には `Refs #<issue>` または `Closes #<issue>` を含める
  - 作業完了で Issue を Close できる: `Closes #<issue>`
  - 後続 PR や残作業がある: `Refs #<issue>`
- `src/` または `infra/` を変更する PR では **Release Note 要否宣言** を本文に含める（CI 検証）:

```markdown
Release-Note: required
```

または:

```markdown
Release-Note: not-required
Reason: 内部リファクタのみで観測可能な変更なし
```

- `Release-Note: required` の場合は `docs/releases/log.md` の `## v?.?.? (未確定)` を更新する
- PR タイトルは commit と同様の Conventional Commits 形式（日本語）

## Push

- `git push -u origin <branch-name>`
- ネットワークエラー時は指数バックオフで再試行してよい

## Quality Checks (before commit / PR)

Skill / 設定変更時の最低限:

```bash
uv run ruff check src tests scripts
uv run pytest
uv run python scripts/validate_okf.py
uv run python scripts/sync_skills.py --check
```

`src/` 変更を含む PR では上記に加え、リポジトリ CI と同等の検証を Phase 5 で実施する。詳細は `project-verification` Skill を参照。
