# リリースログ

## v?.?.? (未確定)

- **Added**: PR workflow CI（`src/` 変更時の Issue 紐付け、`src/` / `infra/` 変更時の Release Log 更新チェック）、`.cursor/rules/implementation-workflow.mdc`、PR テンプレート（`scripts/validate_pr_workflow.py`、`.github/workflows/pr-workflow.yml`）
- **Changed**: `mcp-server-engineering` の workflow reference を MCP 固有の `mcp-completion-checklist.md` に改名・縮小し、共通ワークフローは `implementation-workflow` Skill を正本と明記（`AGENTS.md`）
- **Added**: MCP ツール実行の output を Langfuse トレースへ記録（`record_tool_output`、`get_document` 本文は先頭 500 文字に truncate）（[API 契約](/current/features/api.md)、[インフラ](/current/infrastructure.md)）
- **Added**: DevSecOps パターンA — CI（ruff / pytest / Docker build）、`uv.lock`、Dependabot、Bandit、`uv audit`、gitleaks、Trivy、pre-commit（[インフラ](/current/infrastructure.md)、[ADR-0010](/decisions/ADR-0010-devsecops-pattern-a.md)）
- **Fixed**: Chainlit 2.12 の MCP 設定へ移行し起動を復旧。`user_servers` と静的 URL allowlist を採用し、knowledge-mcp の autoload を 2.12 形式へ合わせる（[UI 機能](/current/features/ui.md)、[ADR-0009](/decisions/ADR-0009-chainlit-mcp-user-servers-allowlist.md)）
- **Changed**: README に Langflow 任意サイドカーの番号付きクイックスタートを追加し、末尾の重複 PoC 記述を整理
- **Added**: OKF validator を拡張（YAML frontmatter、cross-link、index 整合、メタデータ検証）し、CI ワークフローとテストを追加（`scripts/validate_okf.py`、`.github/workflows/okf.yml`）
- **Changed**: `AGENTS.md` に Knowledge Catalog 連携（オプション）ガイダンスと OKF メタデータ規則を追記
- **Changed**: Release Log を Phase 6 から `## v?.?.? (未確定)` 見出し下へ追記する運用に変更。タグ確定はユーザー依頼時のみ（`implementation-workflow` Skill）
- **Changed**: OKF validator が未確定リリース見出し（先頭・最大 1 件）を許容（`scripts/validate_okf.py`）

## v1.0.0

- **Changed**: リリースログをバージョンタグ単位（前回タグからの差分）で記録する運用に変更。`implementation-workflow` Skill に `grill-me` / `grilling` による計画 refinement を追加
- **Changed**: Langflow の書き込みと Collection 確認を分離する。`Ingest.json` は書き込みのみ、類似検索は `QueryPgVector.json`（[Ingest](/current/features/ingest.md)）
- **Added**: ホスト原本（`data/ingest/`）を Langflow Files API / Flow API から順次 Ingest し、`documents` へ載せる（[Ingest](/current/features/ingest.md)、[ADR-0008](/decisions/ADR-0008-host-originals-langflow-api.md)）
- **Changed**: 同一文書の再投入を `content_hash` で検出し、未変更は Skip、変更時は親 `document_id` の旧 chunk を削除してから再 Ingest する（[検索バックエンド](/current/features/backend.md)、[Ingest](/current/features/ingest.md)、[ADR-0007](/decisions/ADR-0007-document-lifecycle.md)）
- **Changed**: `documents` を 1 行 = 1 chunk にし、Langflow Collection からシステム検索インデックスへ複製できるようにする（[検索バックエンド](/current/features/backend.md)、[Ingest](/current/features/ingest.md)、[ADR-0006](/decisions/ADR-0006-documents-chunk-schema.md)）
- **Added**: Langflow を任意サイドカーとして追加し、ファイル Ingest PoC を既存検索経路から分離する（[Ingest](/current/features/ingest.md)、[ADR-0005](/decisions/ADR-0005-langflow-ingest-sidecar.md)）
- **Fixed**: MCP `_meta` に Langfuse `langfuse_trace_id` baggage を載せ、同一トレースの FastMCP スパンが Langfuse 一覧の追加ルートにならないようにする（[インフラ](/current/infrastructure.md)、[ADR-0004](/decisions/ADR-0004-langfuse-mcp-meta-tracing.md)）
- **Changed**: Langfuse へ FastMCP と asyncpg クライアントスパンを export する（[アーキテクチャ](/current/architecture.md)、[ADR-0004](/decisions/ADR-0004-langfuse-mcp-meta-tracing.md)）
- **Added**: Chainlit 内蔵 MCP 接続 UI で Streamable HTTP / SSE サーバを追加接続でき、既定の knowledge-mcp が一覧に表示される（[UI 機能](/current/features/ui.md)、[ADR-0003](/decisions/ADR-0003-chainlit-traced-client.md)）
- **Added**: `search_knowledge` と `get_document` ツールを持つ FastMCP ベクトル検索サーバー（[API 契約](/current/features/api.md)）
- **Added**: traced FastMCP クライアント付き Chainlit チャット UI（[UI 機能](/current/features/ui.md)）
- **Added**: アプリスタック用 Docker compose とピン留め Langfuse 公式 compose（[インフラ](/current/infrastructure.md)）
- **Added**: FastMCP、pgvector、Chainlit、Langfuse `_meta` トレーシングの ADR（[意思決定](/decisions/index.md)）
- **Added**: e2e トレース伝播の自動テスト（`tests/test_trace_propagation.py`、in-memory OTel）
- **Changed**: MCP ツール input の Langfuse 記録とトレースネスト（`chat.turn` 1 本に統合、[アーキテクチャ](/current/architecture.md)）
