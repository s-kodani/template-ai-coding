---
type: Infrastructure
title: インフラ
description: アプリ、Keycloak、MCP Gateway、Langfuse、任意 Langflow の Docker Compose スタックと CI/CD・DevSecOps 検証。
tags: [docker, langfuse, langflow, postgres, keycloak, gateway, ci, devsecops]
status: stable
generated:
  at: "2026-09-13T12:00:00Z"
  by: process:cursor-agent
---

# インフラ

## Compose スタック

| スタック | パス | 用途 |
|---|---|---|
| Langfuse 公式 | `infra/langfuse/docker-compose.yml` + `network.yml` | トレース UI とストレージ |
| アプリケーション | `infra/app/compose.yml` | FastMCP、MCP Gateway、pgvector Postgres、Chainlit、Keycloak |
| Langflow（任意） | `infra/langflow/compose.yml` | Ingest PoC。`make -C infra langflow-up` |

アプリと Langfuse の共有 Docker ネットワーク: `observability`。Langflow スタックは独立ネットワークであり、このネットワークには参加しない。

アプリの Chainlit / MCP サーバーは、Langfuse Web が実際に待ち受ける `langfuse_default` ネットワークにも接続します（`langfuse-web:3000` への OTLP 送信用）。

## ホストポート

| サービス | ポート |
|---|---|
| Langfuse UI | 3000 |
| Chainlit | 8080 |
| Keycloak | 8081 |
| FastMCP（knowledge-mcp） | 127.0.0.1:8000 |
| FastMCP（web-search-mcp） | 127.0.0.1:8001 |
| MCP Gateway | 非公開（compose 内部のみ） |
| アプリ Postgres | 5433 |
| Langflow UI | 7860 |
| Langflow Postgres | 5434 |

## 起動

```bash
make -C infra up
make -C infra seed
```

Langflow Ingest PoC はデフォルト起動に含まれない。

```bash
make -C infra langflow-up
```

UI は http://localhost:7860 。Langflow の PGVector は専用 Postgres の `langflow_vectors`（ホスト `localhost:5434`）へ書く。ホスト原本からの API Ingest は `make -C infra ingest-langflow`（既定 `docs/`）。Collection からアプリの `documents` へは同コマンドが複製する。複製だけなら `make -C infra import-langflow`。

既存のアプリ volume を Chunk / ライフサイクル列へ更新するには、seed の前に migrate する（`make -C infra seed` は migrate を先に実行する）。

```bash
make -C infra migrate
make -C infra ingest-langflow
make -C infra ingest-langflow FILES='docs/current/features/ingest.md'
make -C infra import-langflow
make -C infra delete-document DOCUMENT_ID=<parent-uuid>
```

Langfuse API キーは初回サインアップ後に手動で作成し、リポジトリルートの `.env` にコピーします。

Langfuse スタック用の `infra/langfuse/.env` では、`ENCRYPTION_KEY` を 64 文字 hex（例: `openssl rand -hex 32`）に設定してください。形式が不正だと http://localhost:3000 が 500 になります。

## トレースエクスポート

Chainlit と FastMCP の両方で、FastMCP を import する **前に** Langfuse Python SDK を初期化します。キーが未設定の場合はトレースは no-op となり、サービスは起動可能です。

**送信メタデータ・観測ツリー・秘匿ルールの正本**は [Langfuse OTEL トレーシング](/current/features/tracing.md)。以下は運用上の要点のみ。

- Langfuse SDK 4 はデフォルトで LLM / Langfuse スパン以外を落とすため、`should_export_span` で `fastmcp` と `opentelemetry.instrumentation.asyncpg` を追加許可する
- MCP `_meta` には `traceparent` / `tracestate` / `baggage`（`langfuse_trace_id` と `propagate_attributes` の属性）を載せる
- プロセス共通の `langfuse.environment` / `langfuse.release` は `LANGFUSE_TRACING_ENVIRONMENT` / `LANGFUSE_RELEASE` で設定する
- OTel Resource の `service.name` は Compose のサービス別 `OTEL_SERVICE_NAME` で設定する（Chainlit: `chainlit`、MCP サーバー: `knowledge-mcp` / `web-search-mcp`）。変更の反映にはコンテナ再作成が必要

## 認証（Keycloak）

Chainlit は Keycloak の `knowledge` realm で OAuth する（[ADR-0011](/decisions/ADR-0011-keycloak-chainlit-oauth.md)）。既定 knowledge-mcp 呼び出しは MCP Gateway が Token Exchange する（[ADR-0012](/decisions/ADR-0012-mcp-gateway-resource-server.md)）。直結 MCP クライアントは Keycloak の認可コード + PKCE（匿名 DCR）で同じ Resource Server を呼ぶ（[ADR-0014](/decisions/ADR-0014-mcp-direct-three-legged-oauth.md)）。シーケンスは [認証認可](/current/features/authentication.md)。

- 管理 UI: http://localhost:8081 （`admin` / `admin`）
- チャットログイン: Chainlit の Keycloak ボタンから。開発ユーザーは `dev` / `dev`（knowledge + web-search）、`dev2` / `dev2`（web-search のみ）、`readerless` / `readerless`（MCP reader role なし）
- Chainlit コンテナはアプリ Postgres の `DATABASE_URL` を使わない（Chainlit 内蔵 data layer の `User` テーブルは持たない）。refresh token は `TOKEN_STORE_DATABASE_URL` で同じ Postgres の `chainlit_oauth_tokens` に保存する
- MCP Gateway はホストポートを公開しない。Chainlit は Registry `gateways[].url`（既定 `http://mcp-gateway:8082`）へ到達する。カタログ `url` は各 Gateway の `PUBLIC_BASE_URL`
- knowledge-mcp は `MCP_JWKS_URI` 設定時に Bearer 必須。直結クライアントは PRM（`/.well-known/oauth-protected-resource/mcp`）から Keycloak を発見し、認可コード + PKCE でトークンを取る。非対話フォールバックは `uv run python scripts/mcp_dev_token.py`
- realm 定義は `infra/app/keycloak/knowledge-realm.json`。変更後は Keycloak コンテナを再作成する
- セッション寿命は realm の `ssoSessionIdleTimeout` / `ssoSessionMaxLifespan` と `.chainlit/config.toml` の `user_session_timeout` の組で決まる。現行値と失効時の挙動は [認証認可](/current/features/authentication.md)
- Token Exchange（Keycloak 26 V2）は `audience` を送らない。knowledge-mcp の `aud` は `mcp-tools` の custom audience mapper が付ける

## 手動検証

1. **MCP Inspector（3LO）**: `http://127.0.0.1:8000/mcp` を OAuth 付きで開く。401 の `resource_metadata` から Keycloak へ飛び、`dev` / `dev` でログインする。web-search は `:8001/mcp`
2. **MCP Inspector（フォールバック）**: `uv run python scripts/mcp_dev_token.py` の出力を Bearer にし、同じ URL に接続
3. **Chainlit**: Keycloak でログインし、`search_knowledge` が呼ばれる質問を送信。同じスモークは Playwright e2e（下記）でも実行できる
4. **Langfuse**: チャット 1 ターンあたり 1 本のトレースに、クライアント/サーバーのツールスパンがネストされていることを確認（属性一覧は [Langfuse OTEL トレーシング](/current/features/tracing.md)）

### Playwright e2e スモーク

ブラウザで Keycloak ログインからチャット応答までを確認する。PR の `quality` ジョブでは実行しない。テストは `e2e/` に置き、既定の `uv run pytest`（`testpaths = ["tests"]`）では収集しない。

| ファイル | 内容 |
|---|---|
| `test_chat_smoke.py` | `dev` ログイン + チャット 1 ターン（非空応答） |
| `test_auth_flow.py` | 未ログイン gate、ログアウト → 再ログイン |
| `test_chat_knowledge.py` | Gateway MCP 接続、`search_knowledge` / `get_document` と seed 固定文言 |
| `test_chat_rbac.py` | `dev2` / `readerless` が seed ナレッジを取得できない |
| `test_chat_web_search.py` | `dev2` + `search_web`（URL 断言）。Brave key 未設定エラー経路 |
| `test_mcp_gateway_lifecycle.py` | 両 MCP POST、disconnect → 失敗 → reconnect → 成功 |
| `test_chat_session.py` | マルチターン会話（ツール不要） |
| `test_mcp_catalog_ui.py` | `dev2` の knowledge 接続 403、reload 再接続 |

前提: `make -C infra up && make -C infra seed`、`.env` の `OPENAI_API_KEY`。`search_web` 正系は `BRAVE_SEARCH_API_KEY` も必要（未設定時 skip）。Brave key 未設定エラー経路はホスト env に key が**ない**ときのみ実行（ある場合 skip）。スタック未起動は失敗。

```bash
uv sync --extra e2e
uv run playwright install chromium   # システムに Google Chrome がある場合は不要
make -C infra e2e
```

ベース URL は `E2E_BASE_URL`（既定 `http://localhost:8080`）。ログインユーザーは `E2E_USERNAME` / `E2E_PASSWORD`（既定 `dev` / `dev`）。RBAC 用に `E2E_DEV2_*`（既定 `dev2` / `dev2`）、`E2E_READERLESS_*`（既定 `readerless` / `readerless`）を上書き可能。ブラウザは `E2E_BROWSER_CHANNEL`（未設定時は `google-chrome` があれば `chrome`、なければ Playwright 同梱 Chromium）。

ナレッジ系テストは LLM 全文一致ではなく `scripts/seed.py` の固定文言（例: `FastMCP`, `pgvector`, `semantic search`）または否定断言（RBAC）で安定化する。スモークのみ非空応答まで。

### トレース検証チェックリスト（1 ターン = 1 trace）

[Langfuse OTEL トレーシング](/current/features/tracing.md) の「検証」節と同一。要点:

| 確認項目 | 期待結果 |
|---|---|
| Langfuse トレース一覧 | `chat.turn` が **1 行** のみ（同一 `traceId` の FastMCP / ツールスパンはルートに出ない） |
| トレース属性 | `user.id`（Keycloak sub 等）、`session.id`（Chainlit セッション）、`langfuse.environment` / `langfuse.release`（設定時） |
| OTel Resource | `service.name` が Chainlit span では `chainlit`、MCP サーバー span では `knowledge-mcp` または `web-search-mcp`（`unknown_service` ではない） |
| トレース詳細 | `llm.generate` が `chat.turn` の子（type=generation、model / usage 付き） |
| Embedding | `search.embed` が embedding observation（model / usage 付き） |
| ツール呼び出し | `search_knowledge` / `get_document` の input / output が tool observation に記録。metadata に `tool.route` / `tool.server_id` 等 |
| MCP サーバー | `tools/call …` SERVER span 配下に `search.query` / `get_document.fetch` |
| Postgres | `search.query` 近傍に asyncpg クライアントスパン（CONNECT / SELECT 等） |
| 自動テスト | `uv run pytest tests/test_trace_propagation.py tests/test_langfuse_span_export.py tests/test_tracing_metadata.py tests/test_tool_trace_output.py` |

## CI/CD と DevSecOps

[ADR-0010](/decisions/ADR-0010-devsecops-pattern-a.md) に従い、パターンA（OSS Shift Left）で PR / `main` push 時に自動検証する。

### GitHub Actions

| ワークフロー | ジョブ | 内容 |
|---|---|---|
| `.github/workflows/ci.yml` | quality | `ruff check`（`e2e/` 含む）、`pytest`（ルート `tests/` と `gateway/`。Playwright e2e は実行しない）、各環境の `uv sync --frozen --extra dev`、自前 Skill / Agent の展開一致（`scripts/check_skill_deploy.py`） |
| | security | Bandit, `uv audit`, gitleaks |
| | build-and-scan | `docker compose build`, Trivy（mcp-server / chainlit / mcp-gateway / web-search-mcp イメージ、`scanners: vuln`） |
| `.github/workflows/pr-workflow.yml` | workflow | PR 本文の Issue 紐付け（`src/` 変更時）、Release Log 更新要否（`src/` / `infra/` 変更時） |
| `.github/workflows/okf.yml` | okf | OKF bundle 検証 |

### ローカル検証

```bash
uv sync --frozen --extra dev
uv sync --directory gateway --frozen --extra dev
uv run ruff check src tests scripts gateway e2e
uv run pytest
uv run --directory gateway pytest
uv run bandit -r src scripts gateway/src -c pyproject.toml
uv audit --preview-features audit-command
uv run pre-commit run --all-files
uv run python scripts/validate_okf.py
uv run python scripts/check_skill_deploy.py --check
docker compose -f infra/app/compose.yml build
```

pre-commit はコミット前の Shift Left 用。初回は `uv run pre-commit install` でフックを有効化する。

### 依存更新

- `uv.lock` を Source of Truth とし、Dependabot（`.github/dependabot.yml`）が pip と GitHub Actions を週次更新する。
- Trivy は CRITICAL/HIGH かつ修正版ありの CVE で CI を失敗させる（`ignore-unfixed: true`）。

### Branch protection（`main`）

`main` へのマージ前に CI 成功を必須とする。Repository rulesets で以下の status check を要求する。

| チェック名 | ワークフロー / ジョブ |
|---|---|
| `quality` | CI / quality |
| `security` | CI / security |
| `build-and-scan` | CI / build-and-scan |
| `okf` | OKF Validation / okf |

`strict`（最新 `main` との同期必須）を有効にする。

リポジトリ管理者権限を持つトークンで以下を実行する（冪等）。

```bash
./scripts/configure_main_branch_protection.sh
```

GitHub UI から設定する場合: **Settings → Rules → Rulesets → New branch ruleset** で `refs/heads/main` を対象に、上記 4 チェックを必須化する。
