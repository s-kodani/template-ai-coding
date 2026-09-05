# リリースログ

## v?.?.? (未確定)

- **Changed**: Gateway MCP の接続 / 実行を Chainlit 標準 MCP セッション + サーバー側 JWT 注入（`gateway_mcp_connect.py`）に統一。`/gateway-mcp` と `gateway_disabled` モデルを廃止。チャット開始時 auto-connect、401 時 reconnect（[UI 機能](/current/features/ui.md)、[認証認可](/current/features/authentication.md)、[ADR-0012](/decisions/ADR-0012-mcp-gateway-resource-server.md)、[ADR-0013](/decisions/ADR-0013-mcp-gateway-per-server-streamable-http.md)）
- **Fixed**: Gateway MCP 再接続時の `POST /gateway-mcp` 422 を解消し、MCP プラグ UI の接続数バッジが正しく表示されるようにした。localStorage seed から `clientType` を除去し、転送 body を `{ sessionId, name }` のみに正規化。`/gateway-mcp` の `CurrentUser` 依存をモジュールスコープへ移動（FastAPI が query param と誤解釈していた）（[UI 機能](/current/features/ui.md)）
- **Changed**: Langfuse OTEL メタデータを一通り設定 — `user.id` / `session.id` / tags / metadata の `propagate_attributes`（MCP `_meta` baggage 伝播含む）、`llm.generate` を generation 型 + model / usage、`search.embed` を embedding observation + usage、ツール observation に route / server_id、環境変数 `LANGFUSE_TRACING_ENVIRONMENT` / `LANGFUSE_RELEASE`（[トレーシング](/current/features/tracing.md)、[インフラ](/current/infrastructure.md)）
- **Added**: Current-state に [Langfuse OTEL トレーシング](/current/features/tracing.md) を追加し、送信メタデータの正本を集約。`architecture.md` / `ui.md` / `api.md` / `infrastructure.md` / trace-validation Skill を cross-link で整合
- **Added**: レビュー用サブエージェント `review` を APM のプロジェクト primitive（`.apm/agents/`）として追加する。`apm install` で `.cursor/agents/` と `.claude/agents/` へ展開し、Codex は `.codex/agents/review.toml` へ変換する。CI は `scripts/check_skill_deploy.py` で Skill と合わせて一致を検証する（[インフラ](/current/infrastructure.md)）
- **Changed**: 自前 Agent Skill の正本を `.apm/skills/` にし、`apm install` で `.agents/skills/` と `.claude/skills/` へ展開する。CI は `scripts/check_skill_deploy.py` で一致を検証する（[インフラ](/current/infrastructure.md)）
- **Changed**: Chainlit と MCP Gateway のツール list/call を REST からサーバー単位 Streamable HTTP（`POST /mcp/{server_id}`）にした。発見は `GET /v1/mcp` の `{id, name, tools, url}` のまま（[API 契約](/current/features/api.md)、[認証認可](/current/features/authentication.md)、[ADR-0013](/decisions/ADR-0013-mcp-gateway-per-server-streamable-http.md)）
- **Changed**: knowledge-mcp の realm role を `mcp-reader` から `knowledge-mcp-reader` に改名した。次の Gateway MCP は別 role を Registry `required_roles` に書く（[認証認可](/current/features/authentication.md)、[ADR-0012](/decisions/ADR-0012-mcp-gateway-resource-server.md)）
- **Changed**: プラグ UI で Gateway MCP を切断すると、そのサーバーのツールを LLM / 実行から外す。再接続で戻る（[UI 機能](/current/features/ui.md)、[ADR-0012](/decisions/ADR-0012-mcp-gateway-resource-server.md)）
- **Changed**: Gateway LLM ツール名を `{server_id}__{mcp_tool_name}` にした。Token Exchange は Registry の `authentication.mode` / `resource` / `scopes` を必須とし、knowledge 向けデフォルトは使わない（[UI 機能](/current/features/ui.md)、[API 契約](/current/features/api.md)、[ADR-0012](/decisions/ADR-0012-mcp-gateway-resource-server.md)）
- **Added**: ログインから Gateway Token Exchange、knowledge-mcp 検証までの認証認可シーケンスを Current-state に記録（[認証認可](/current/features/authentication.md)）
- **Changed**: `GET /v1/mcp` は JWT の realm role が `authorization.required_roles` を満たすサーバーだけ返す（[API 契約](/current/features/api.md)、[ADR-0012](/decisions/ADR-0012-mcp-gateway-resource-server.md)）
- **Changed**: Chainlit の Gateway ツール配線を Registry / `GET /v1/mcp` ベースにした。LLM schema は knowledge 専用ハードコードではない（[UI 機能](/current/features/ui.md)、[ADR-0012](/decisions/ADR-0012-mcp-gateway-resource-server.md)）
- **Changed**: Chainlit のプラグ UI に knowledge-mcp を Gateway 表示専用で載せる。実 MCP セッションは張らない（[UI 機能](/current/features/ui.md)、[ADR-0012](/decisions/ADR-0012-mcp-gateway-resource-server.md)）
- **Added**: MCP Gateway を導入し、Chainlit の既定 knowledge-mcp 呼び出しを Keycloak Token Exchange 経由にした。knowledge-mcp は Resource Server として JWT を検証する（[アーキテクチャ](/current/architecture.md)、[ADR-0012](/decisions/ADR-0012-mcp-gateway-resource-server.md)）
- **Fixed**: Keycloak 26 standard token exchange（V2）では `audience=knowledge-mcp` を送らず、`mcp-tools` の custom audience mapper で `aud=http://localhost:8000/mcp` を付ける。realm import が `basic` / `profile` / `email` / `roles` を消さないようにした
- **Fixed**: refresh token が無いとき Postgres の token store が `AmbiguousParameterError` になる問題（`$5::text`）
- **Added**: Cloud Agent 向けホスト CONNECT プロキシ（`.cursor/egress-proxy.py`）。ネスト Docker ではコンテナから `api.openai.com` へ直接出られない
- **Added**: Keycloak をアプリ Compose に追加し、Chainlit を OAuth ログイン必須にした（[UI 機能](/current/features/ui.md)、[インフラ](/current/infrastructure.md)、[ADR-0011](/decisions/ADR-0011-keycloak-chainlit-oauth.md)）
- **Changed**: APM 管理 Skill（`ponytail`、`test-driven-development`）を upstream 内容へ復元。リポジトリ固有ルールは `AGENTS.md` / `test-strategy` へ集約
- **Changed**: `AGENTS.md` の workflow / OKF 共通ルールを `implementation-workflow` references へ委譲し、リポジトリ固有設定に slim 化（~496行 → ~220行）
- **Changed**: `implementation-workflow` Skill を Progressive Disclosure 構成へ再編（`SKILL.md` 入口 + `references/` 8 本、`mcp-server-engineering` と同パターン）
- **Added**: Agent Skill 構成整理 — テスト方針統一（`test-strategy` 正本）、workflow 3 段階簡略化、`project-verification` Skill、`.agents` → `.claude` Skill 同期（`scripts/sync_skills.py`）、PR Release Note 要否宣言（`validate_pr_workflow.py`）、Git/PR `delivery-reference.md`
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
