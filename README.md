# MCP Apps ベクトル検索 + Open WebUI + Langfuse

FastMCP ベクトル検索、MCP Apps、Open WebUI、Langfuse トレーシングのローカル検証スタックです。

## クイックスタート

ホストに Docker Compose、uv、Node.js 22以上とnpmが必要です（Nodeの固定版は `.tool-versions`）。`make -C infra up` は、ホスト側のPython処理を始める前にMCP Appを自動buildします。

1. 環境ファイルをコピーします。

```bash
cp .env.example .env
cp infra/langfuse/env.example infra/langfuse/.env
```

2. `.env` に `OPENAI_API_KEY` を設定します。あわせて次のコマンドで 64 文字の hex を生成し、`infra/langfuse/.env` の `ENCRYPTION_KEY` をその値へ置き換えます。プレースホルダーのまま起動すると Langfuse UI は 500 になります。

```bash
openssl rand -hex 32
```

3. スタックを起動します。

```bash
make -C infra up
```

4. ナレッジベースを投入します（ホストから `localhost:5433` の Postgres に接続。`POSTGRES_*` と `OPENAI_API_KEY` を使用）。

```bash
make -C infra seed
```

5. Open WebUI は http://localhost:8080 を開き、初回は「はじめる」、続いて Keycloak でログインします。開発ユーザーは `dev` / `dev`（knowledge + web-search）、`dev2` / `dev2`（web-search のみ）、`readerless` / `readerless`（MCP reader role なし）。「search_knowledge で Architecture Overview を調べて」と送ると検索結果のMCP Appが表示され、タイトルからチャンク本文を取得できます。「前へ／次へ」と5・10・20件の切替でページごとにサーバーへ問い合わせます。Appからのツール呼び出しにはOpen WebUI標準の確認ダイアログが表示されます。

   MCP接続先は管理者が `infra/app/gateway-registry.yml` で管理します。既定接続は起動時に設定済みです。Web検索には `.env` の `BRAVE_SEARCH_API_KEY` が必要です。Langfuseは http://localhost:3000、Keycloak管理UIは http://localhost:8081（ローカル既定 `admin` / `admin`）です。

6. Langfuse でサインアップ後、`LANGFUSE_PUBLIC_KEY` と `LANGFUSE_SECRET_KEY` を `.env` に追加し、アプリサービスを再起動します。

## 既存スタックからの移行

`make -C infra up` は旧Keycloakコンテナのデータを停止中に空の専用volumeへ引き継ぎ、既存realmへOpen WebUI専用clientとscopeを冪等に追加します。既存の文書・realm・旧トークンテーブルは削除しません。旧Keycloakと移行先volumeの両方にデータがある場合は上書きせず停止するため、表示されたバックアップとvolumeを確認してください。

既存Keycloakが別volumeやbindで保存されている場合も、保存先を切り替えずに停止します。既存データを使うCompose定義を確認してから起動してください。

Open WebUIの会話・OAuth状態は `open_webui_data`、KeycloakのIDは `keycloak_data` に保存します。`.env` の `OPEN_WEBUI_SECRET_KEY` と `OPEN_WEBUI_OAUTH_CLIENT_SECRET` は再作成時も固定してください。既存 `.env` には `.env.example` の同名設定を追加できます。旧Chainlitのログインセッションは引き継がず、Keycloakで再ログインします。

realm設定だけの再同期は `make -C infra sync-auth` です。手動で追加したMCP接続もRegistryへ反映してUIサービスを再作成してください。

## Langflow クイックスタート（任意）

Langflow はデフォルトの `make -C infra up` には含まれません。詳細は [Langflow Ingest](docs/current/features/ingest.md) と [インフラ](docs/current/infrastructure.md) を参照してください。

1. 本体クイックスタートの 1–2（`.env` と `OPENAI_API_KEY`）が済んでいることを確認します。アプリスタックの起動は不要です。

2. Langflow を起動します。

```bash
make -C infra langflow-up
```

3. http://localhost:7860 を開きます。未 import なら `infra/langflow/flows/Ingest.json` と `infra/langflow/flows/QueryPgVector.json` を import します。

4. UI で `Ingest` を実行し、専用 DB の Collection へ書き込みます。ホスト原本の置き場は `docs/` です（Langflow My Files ではありません）。

5. UI で `QueryPgVector` を実行し、Collection の類似検索を確認します。

6. （任意）アプリスタックが起動済みなら、Collection をアプリの `documents` へ複製できます。

```bash
make -C infra import-langflow
```

API で投入と複製を一度に行う場合は `make -C infra ingest-langflow`（既定 `docs/`）。アプリ Postgres が必要です。

7. 停止します。

```bash
make -C infra langflow-down
```

## サービス

| サービス | URL |
|---|---|
| Open WebUI | http://localhost:8080 |
| Keycloak | http://localhost:8081 |
| knowledge-mcp（FastMCP） | http://127.0.0.1:8000/mcp |
| web-search-mcp（FastMCP） | http://127.0.0.1:8001/mcp |
| MCP Gateway | compose 内部のみ（ホスト非公開） |
| Langfuse | http://localhost:3000 |
| アプリ Postgres | localhost:5433 |
| Langflow（任意） | http://localhost:7860 |
| Langflow Postgres | localhost:5434 |

## 開発

生成HTMLはgit管理外です。clean checkoutでは、editable installも含めて `uv sync` / `uv run` / `uv build` の前にAppをbuildしてください。`make -C infra app-ui` でも同じbuildを実行できます。CIとCloud Agentのinstallもこの順序でセットアップします。

```bash
# Node.js 22以上。生成HTMLをPythonパッケージに同梱するため先にbuildする。
npm --prefix apps/knowledge-search ci
npm --prefix apps/knowledge-search test
npm --prefix apps/knowledge-search run build
uv sync --frozen --extra dev
uv sync --directory gateway --frozen --extra dev
uv run ruff check src tests scripts gateway e2e
uv run pytest
uv run --directory gateway pytest
uv run python scripts/validate_okf.py
```

Open WebUIのSSO・権限・MCP Apps・チャットは Playwright スモーク（`e2e/`。PR CI では走らない）。スタック起動と seed のあと:

```bash
uv sync --extra e2e
uv run playwright install chromium   # システムに Google Chrome がある場合は不要
make -C infra e2e
```

## MCP Inspector

直結は Keycloak の認可コード + PKCE（OAuth）が正です。Inspector で `http://127.0.0.1:8000/mcp`（web-search は `:8001/mcp`）を Streamable HTTP として開き、OAuth 接続します。401 の `resource_metadata` から Keycloak へ飛び、`dev` / `dev` でログインしてください。シーケンスは [認証認可](docs/current/features/authentication.md) です。

非対話フォールバック（password grant + Token Exchange）:

```bash
uv run python scripts/mcp_dev_token.py
npx @modelcontextprotocol/inspector
```

1 行目の出力を `Bearer` にして同じ URL に接続します。web-search は `uv run python scripts/mcp_dev_token.py --target web-search --username dev2` で `:8001/mcp` です。
