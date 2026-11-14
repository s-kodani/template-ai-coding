---
type: Infrastructure
title: インフラ
description: Open WebUI、MCP Apps、Keycloak、Gateway、FastMCP、pgvector、Langfuseと任意LangflowのローカルCompose・移行・検証。
tags: [docker, open-webui, mcp-apps, langfuse, langflow, postgres, keycloak, gateway, ci, devsecops]
status: stable
generated:
  at: "2026-11-14T12:31:53Z"
  by: process:codex-agent
---

# インフラ

## Composeスタック

| スタック | パス | 用途 |
|---|---|---|
| Langfuse公式 | `infra/langfuse/docker-compose.yml` + `network.yml` | トレースUIとストレージ |
| アプリ | `infra/app/compose.yml` | Open WebUI、FastMCP、Gateway、pgvector、Keycloakと認証設定同期 |
| Langflow（任意） | `infra/langflow/compose.yml` | Ingest sidecar。既定の`up`には含めない |

アプリとLangfuseは`observability`を共有する。Open WebUIとMCPサーバーは`langfuse_default`にも接続し、`langfuse-web:3000`へトレースを送る。Langflowは独立ネットワークに置く。

| サービス | ホスト側ポート |
|---|---|
| Open WebUI | 8080 |
| Keycloak | 8081 |
| knowledge-mcp | 127.0.0.1:8000 |
| web-search-mcp | 127.0.0.1:8001 |
| MCP Gateway | 非公開。Compose内部の8082 |
| アプリPostgres | 5433 |
| Langfuse UI | 3000 |
| Langflow UI / Postgres | 7860 / 5434 |

## 起動とビルド

```bash
make -C infra up
make -C infra seed
```

`app-up`は`docker compose up --build --wait`で各サービスのhealthcheckを待つ。Open WebUIのready判定は`/ready`。Keycloak ready後に`keycloak-sync`が専用client / scopeを同期し、完了してからUIを起動する。

Open WebUIは`ghcr.io/open-webui/open-webui:v0.13.0`ベースの派生イメージ。OTel系以外の上流依存をconstraintsで保持し、Langfuse 4.15.1を導入する。OTelは専用requirementsでAPI / SDK / exporterを1.45.2、instrumentation系を0.66b2へ固定する。`pip check`と4ファイルのhash検査付き観測パッチをbuild gateにする。native OTELは無効。上流更新時は同じgateと回帰テストを再検証する。

MCP AppはNode 22 build stageでplain JavaScriptと公式Apps SDKをbundleし、`src/knowledge_mcp/static/search-results.html`をPython runtimeへ含める。ソース変更後のローカル生成は次を実行する。

```bash
make -C infra app-ui
```

実行時のNode、外部CDN、Appからの直接API接続は不要。生成HTMLを含めてからMCP契約テストを実行する。

MCPとGatewayのPython imageは、それぞれの`uv.lock`をコピーし、`uv sync --frozen --no-dev --no-editable`で依存を固定する。FastMCP側のMCP SDK 1.30とGatewayのSDK 2.3を分離する理由は、検証済みadapter契約の互換性であり、旧UIの制約ではない。

## 永続データと既存構成からの移行

- 検索データは既存`postgres_data`を維持する。列更新は`make -C infra migrate`で行う。
- Open WebUIは`open_webui_data`の`/app/backend/data`に会話・OAuth状態とSQLiteを保存する。`OPEN_WEBUI_SECRET_KEY`は固定値を維持する。
- Keycloakのrealmとユーザー識別子は専用`keycloak_data`へ保存する。`app-up`は`preserve-keycloak`から`scripts/persist_keycloak_data.py`を実行し、初回移行時に従来の非volumeコンテナのデータを空のvolumeへ移してから起動する。既存保存データを上書き・削除しない。
- 既に`/opt/keycloak/data`がmountされている場合は、設定したnamed volumeとの完全一致だけを許可する。別volumeやbindの場合はデータやコンテナを変更する前に停止するため、既存の保存先を維持するCompose定義を確認してから起動する。
- realm JSONの初回importだけでは既存realmへclientを追加できない。`keycloak-sync`は`open-webui` clientと専用scope / mapperだけを冪等同期し、既存ユーザー、他client、roleを残す。
- 旧Chainlitの実行コンテナ・Cookie・接続UIは使わない。新UIで再ログインする。旧clientと`chainlit_oauth_tokens`は保持するが、新UIのtoken storeには使わない。
- `docker compose down -v`は永続データを削除するため移行手順に含めない。

初回のKeycloakデータ移行は、成功・失敗のどちらでも表示された`knowledge-keycloak-backup-*`を保持する。バックアップの親と`data`は0700で、移行スクリプトは元コンテナを削除せず、非空の移行先も上書きしない。「Keycloak data preserved」の後でimage buildだけが失敗した場合、`make -C infra app-up`の再実行はこの非空ガードで停止する。保持されたバックアップを残し、次で移行済みvolumeを使った起動だけを再開する。

```bash
docker compose -f infra/app/compose.yml --env-file .env up -d --build --wait --wait-timeout 180
```

手動で認証設定だけを同期する場合は、Keycloak起動後に次を実行する。環境変数の管理者資格情報と`OPEN_WEBUI_OAUTH_CLIENT_SECRET`を使い、tokenやsecretをログへ出さない。

```bash
make -C infra sync-auth
```

`.env`は`.env.example`を参照。通常のチャットとembeddingには`OPENAI_API_KEY`、必要時は`OPENAI_BASE_URL`と`CHAT_MODEL`。Web検索には`BRAVE_SEARCH_API_KEY`を設定する。Gateway secretとOpen WebUI secretはコンテナ再作成時も揃える。

## 認証とMCP接続の設定

- Open WebUIのKeycloak SSOボタンからログインする。開発ユーザーは`dev` / `dev`、`dev2` / `dev2`、`readerless` / `readerless`。
- Keycloak管理UIはhttp://localhost:8081。ローカル既定は`admin` / `admin`。
- 接続先の正本は`infra/app/gateway-registry.yml`。起動処理が`system_oauth`、接続先ID、group grant、既定モデルとnative function callingを生成する。管理画面のDB設定より環境設定を優先する。
- 初回の`CHAT_MODEL`はモデルDBへも登録し、認証済み利用者へのread grant、native params、MCP tool metadataとusage capabilityを設定する。一般利用者向けのモデル公開にproviderの`/models` discoveryは不要。既存の管理者所有モデルは上書きせず、管理対象モデルの編集済みmetadata / paramsも保持する。
- `mcp_roles`をOpen WebUIグループへ同期し、表示権限とGatewayのJWT role検証を揃える。接続先を増やす場合はRegistry・Keycloak role・起動時グループ定義を合わせて更新する。
- Tool / UI Resource取得は同じ利用者のSSO tokenでGatewayへ接続し、下流ではToken Exchange後のtokenだけを使う。任意URLをブラウザから追加する機能は提供しない。
- 直結MCPはPRMからKeycloakを発見し、認可コード + PKCEを使う。非対話検証は`scripts/mcp_dev_token.py`。

claim、セッション期限、失効時、URI allowlistの正本は[認証認可](/current/features/authentication.md)。

## Langflowと検索データ

Langflowは任意で起動する。

```bash
make -C infra langflow-up
make -C infra migrate
make -C infra ingest-langflow
make -C infra ingest-langflow FILES='docs/current/features/ingest.md'
make -C infra import-langflow
make -C infra delete-document DOCUMENT_ID=<parent-uuid>
```

Langflow UIはhttp://localhost:7860、Collectionは専用Postgresの`langflow_vectors`（ホスト5434）。`ingest-langflow`はホスト原本をAPIで投入し、アプリ`documents`へ複製する。`import-langflow`は複製だけを行う。SearchServiceはCollectionを直接読まない（[Ingest](/current/features/ingest.md)）。

## トレース設定と手動確認

Langfuse初回サインアップ後にAPIキーを作成し、ルート`.env`へ`LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`を設定する。`infra/langfuse/.env`の`ENCRYPTION_KEY`は64文字hexを使う。キー未設定時は観測をno-opにする。

`service.name`は`open-webui`、`knowledge-mcp`、`web-search-mcp`。environment / releaseは`LANGFUSE_TRACING_ENVIRONMENT` / `LANGFUSE_RELEASE`。観測単位と秘匿ルールの正本は[トレーシング](/current/features/tracing.md)。

次は確認手順であり、実施済みの検証記録ではない。

1. Open WebUIへ`dev`でログインし、ナレッジ検索を指示する。会話内にAppの一覧、出典、類似度が表示されることを確認する。
2. タイトルを選択し、HostのTool確認後にチャンク本文が表示されることを確認する。十分なチャンクを用意し、前後移動、5・10・20件切替、20件を超えるページ、終端を確認する。
3. `dev2`にはWeb検索だけ、`readerless`にはMCPが表示されないことを確認する。Gateway直呼びでもrole不足を拒否する。
4. Inspectorで`:8000/mcp`または`:8001/mcp`へOAuth接続し、Tool契約を確認する。knowledgeでは`resources/list` / `resources/read`とApps MIME / HTMLも確認する。
5. Langfuseで通常の1ターンが1本の`chat.turn`になり、generationのmodel / usage、Tool、MCP、embedding、DBが同一traceへつながることを確認する。後から行うApp操作は別の`mcp.app`に記録される。

## Playwright E2E

`e2e/`は起動済みスタックを使う。既定の`uv run pytest`は`tests/`のみを収集する。PRのqualityジョブではブラウザE2Eを実行しない。

| 対象 | 検証内容 |
|---|---|
| auth / reauth | 未ログインgate、SSO、ログアウト、無効なUI credentialと再ログイン |
| knowledge / Apps | seed検索、チャンク本文、Apps一覧・ページ切替 |
| Web検索 | role付き接続、検索結果URL、Brave key未設定時のエラー |
| MCP catalog / lifecycle / RBAC | user別grant、Tool discovery、reload後の認証接続 |
| chat session / smoke | 通常応答と複数ターンの文脈 |
| helper tests | ログインと新しい応答の待機処理（スタック不要） |

```bash
uv sync --extra dev --extra e2e
uv run playwright install chromium
make -C infra e2e
make -C infra e2e-smoke
```

通常応答には`OPENAI_API_KEY`が必要。Web検索の正系には`BRAVE_SEARCH_API_KEY`も必要で、未設定なら該当ケースをskipする。Brave空キーのエラー検証はホストenvも空の場合に実行する。

`E2E_BASE_URL`（既定http://localhost:8080）、`E2E_USERNAME` / `E2E_PASSWORD`、`E2E_DEV2_*`、`E2E_READERLESS_*`で検証先を上書きできる。ブラウザは`E2E_BROWSER_CHANNEL`、またはPlaywright Chromiumを使う。

`.github/workflows/e2e-nightly.yml`はscheduleと`workflow_dispatch`で全体およびBrave空キーの経路を検証する。スタックready・seed後に実行し、失敗時はOpen WebUI / Gateway / MCPのログを保存する。

## CI/CD と DevSecOps

[ADR-0010](/decisions/ADR-0010-devsecops-pattern-a.md) に従い、パターンA（OSS Shift Left）で PR / `main` push 時に自動検証する。

Python依存の正本は`uv.lock`と`gateway/uv.lock`。ルートはdnspython 2.9.2、OpenTelemetry API / SDK 1.45.2とinstrumentation / asyncpg / semantic-conventions 0.66b2を使用し、GatewayのOpenTelemetry APIも1.45.2に固定する。dnspythonの過大なメモリ・CPU消費（[GHSA-vvf4-9x63-8xvv](https://github.com/advisories/GHSA-vvf4-9x63-8xvv)）とOpenTelemetryのtraceparent解析によるDoS（[GHSA-mf5v-w3w3-f6cg](https://github.com/advisories/GHSA-mf5v-w3w3-f6cg)）の修正版を含む。

### GitHub Actions

| ワークフロー | ジョブ | 内容 |
|---|---|---|
| `.github/workflows/ci.yml` | quality | `ruff check`（`e2e/` 含む）、`pytest`（ルート `tests/` と `gateway/`。Playwright e2e は実行しない）、Node 22でAppのnpm test / build、各環境の `uv sync --frozen --extra dev`、自前 Skill / Agent の展開一致（`scripts/check_skill_deploy.py`） |
| `.github/workflows/e2e-nightly.yml` | e2e-full / e2e-brave-empty | Playwright e2e（schedule + `workflow_dispatch`。Secrets 必須） |
| | security | Bandit, `uv audit`, gitleaks |
| | build-and-scan | `docker compose build`, Trivy（mcp-server / open-webui / mcp-gateway / web-search-mcp イメージ、`scanners: vuln`） |
| `.github/workflows/pr-workflow.yml` | workflow | PR 本文の `Refs #<issue>`（`src/` `tests/` `scripts/` `infra/` `e2e/` `gateway/` `.apm/` のアプリケーション変更時。`pyproject.toml` / `uv.lock` のみの変更は対象外。`Closes` / `Fixes` / `Resolves` は禁止。Issue 存在確認あり）、Release Log 更新要否（`src/` / `infra/` 変更時） |
| `.github/workflows/okf.yml` | okf | OKF bundle 検証 |

### ローカル検証

```bash
make -C infra app-ui
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
- `uv audit` はルート `uv.lock` を対象にする。既知 CVE は CI 失敗。修正版があるパッケージは lock を上げて解消する。
- Trivy は CRITICAL/HIGH かつ修正版ありの CVE で CI を失敗させる（`ignore-unfixed: true`）。

### Branch protection（`main`）

`main` へのマージ前に CI 成功と人間レビュー 1 件を必須とする。適用は管理者が `./scripts/configure_main_branch_protection.sh` を実行する（Cloud Agent は適用しない）。未実行の間、ruleset はリポジトリに存在しない。

Repository rulesets で以下を要求する。

| チェック名 | ワークフロー / ジョブ |
|---|---|
| `quality` | CI / quality |
| `security` | CI / security |
| `build-and-scan` | CI / build-and-scan |
| `okf` | OKF Validation / okf |
| `workflow` | PR Workflow / workflow |

加えて `pull_request` ルール: 承認 1、CODEOWNERS レビュー、stale review の破棄、`strict`（最新 `main` との同期必須）。

`.github/CODEOWNERS` は `src/` `infra/` `gateway/` `scripts/` `.apm/` `docs/current/` `docs/decisions/` `.github/` `.pre-commit-config.yaml` `uv.lock` を `@s-kodani` に割り当てる。CODEOWNERS レビューは上記 ruleset 適用後に実効化する。

パブリックリポジトリでは GitHub Free でも ruleset を強制できる。プライベートでは GitHub Pro / Team / Enterprise が必要で、Free のままでは ruleset は enforce されない。

リポジトリ管理者権限を持つトークンで以下を実行する（冪等）。

```bash
./scripts/configure_main_branch_protection.sh
```

GitHub UI から設定する場合: **Settings → Rules → Rulesets → New branch ruleset** で `refs/heads/main` を対象に、上記 5 チェックと pull request レビューを必須化する。
