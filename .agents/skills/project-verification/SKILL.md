---
name: project-verification
description: >
  本リポジトリの CI / DevSecOps / Docker / Langfuse / Ingest 検証を、変更種別に応じて
  実行する Skill。src/ scripts/ infra/ tests/ docs/ .agents/skills/ の実装・変更時に
  implementation-workflow Phase 5 と併用する。
---

# Project Verification

## 目的

`AGENTS.md` と CI に定義された検証を、変更内容に応じて漏れなく実行する。

汎用 Skill の npm / pnpm 例ではなく、本リポジトリの `uv` / Docker / OKF コマンドを正本とする。

---

## 使い方

1. 変更ファイルの prefix を確認する
2. 下表の **必須** コマンドを実行する
3. 結果を Issue / PR / Completion Report に記録する
4. 実行していない検証を成功扱いにしない

詳細は必要に応じて `references/` を読む（一括読み込みしない）。

| 判断・作業 | 読む reference |
|---|---|
| CI ジョブ対応表 | `references/ci-matrix.md` |
| Docker Compose ローカルスタック | `references/local-stack.md` |
| Langfuse / MCP トレース | `references/trace-validation.md` |
| DB / Ingest / migration | `references/ingest-validation.md` |

---

## 変更種別ごとの必須検証

| 変更 | 必須 |
|---|---|
| `src/` / `tests/` / `scripts/`（Python） | `uv run ruff check src tests scripts`、`uv run pytest` |
| `docs/`（OKF） | `uv run python scripts/validate_okf.py` |
| `.agents/skills/` | `uv run python scripts/sync_skills.py --check`（または sync 後に再 check） |
| `infra/` | 上記 Python 検証 + `docker compose -f infra/app/compose.yml build` |
| PR（`src/` 変更） | Issue 参照 + Release Note 要否宣言（`validate_pr_workflow.py`） |
| トレース関連 | `uv run pytest tests/test_trace_propagation.py tests/test_langfuse_span_export.py` |
| Ingest / schema | `uv run pytest tests/test_ingest_lifecycle.py tests/test_documents_schema.py` |

### 推奨（時間が許せば）

- `uv run bandit -r src scripts -c pyproject.toml`
- `uv run pre-commit run --all-files`
- Langfuse UI 手動確認（`docs/current/infrastructure.md` のチェックリスト）

### Docker / secret が必要な検証

以下は Cloud Agent で Secrets または Docker 起動が必要。

- `make -C infra up && make -C infra seed`
- Chainlit 実チャット応答
- Langfuse UI で 1 ターン = 1 trace の目視確認

実行できない場合は理由と代替（自動テスト結果）を記録する。

---

## PR 本文テンプレ（検証記録）

```markdown
## Verification

```text
uv run ruff check src tests scripts  # pass
uv run pytest                       # N passed
uv run python scripts/validate_okf.py  # pass
uv run python scripts/sync_skills.py --check  # pass（該当時）
```

Release-Note: required
```

---

## 関連 Skill

- 実装フロー: `implementation-workflow` Phase 5
- テスト設計: `test-strategy`（観点表・TDD 適用判断）
- MCP 変更: `mcp-server-engineering` + `references/mcp-completion-checklist.md`
