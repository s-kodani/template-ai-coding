# Verification

Phase 5 の検証詳細。

## 基本

実装完了前に、変更内容に応じた検証を行う。

- `project-verification` Skill — 本リポジトリの CI / Docker / トレース / Ingest 検証表
- `test-strategy` Skill — テスト観点漏れの確認
- `test-driven-development` Skill — 自動化可能な振る舞い変更時

例: Unit / Integration / E2E Test、Lint、Build、Migration、Infrastructure、手動確認。

**実行していない検証を成功済みと報告してはいけない。**

## OKF Documentation Validation

OKF を採用している場合、実装検証に加えて以下を確認する。

- Knowledge Bundle 配下の非予約 `.md` に YAML frontmatter がある
- Concept Document の `type` が空でない
- YAML が parse 可能
- `index.md` / `log.md` を Concept Document として扱っていない
- 新規・移動・削除・deprecated 化した Concept が関連 `index.md` に反映されている
- 内部 cross-link が意図した Concept を指している
- Current-state Documentation が最終実装と一致している
- `verified` を実際の確認なしに追加していない
- `generated` / `sources` / `stale_after` を捏造していない

リポジトリに OKF validator があれば実行する（例: `uv run python scripts/validate_okf.py`）。
