# MCP ベクトル検索 + Chainlit + Langfuse

FastMCP ベクトル検索、Chainlit チャット UI、Langfuse トレーシングのローカル検証スタックです。

## クイックスタート

1. 環境ファイルをコピーします。

```bash
cp .env.example .env
cp infra/langfuse/env.example infra/langfuse/.env
```

2. `.env` に `OPENAI_API_KEY` を設定します。

3. スタックを起動します。

```bash
make -C infra up
```

4. ナレッジベースを投入します（ホストから `localhost:5433` の Postgres に接続。`POSTGRES_*` と `OPENAI_API_KEY` を使用）。

```bash
make -C infra seed
```

5. Chainlit は http://localhost:8080 を開き、Keycloak でログインします（開発ユーザー `dev` / `dev`）。Langfuse は http://localhost:3000 です。MCP プラグインの一覧に knowledge-mcp が表示されます。追加の Streamable HTTP / SSE サーバも、`.chainlit/config.toml` の URL allowlist 内であればここから接続できます（stdio は無効）。Keycloak 管理 UI は http://localhost:8081（`admin` / `admin`）です。

6. Langfuse でサインアップ後、`LANGFUSE_PUBLIC_KEY` と `LANGFUSE_SECRET_KEY` を `.env` に追加し、アプリサービスを再起動します。

## Langflow クイックスタート（任意）

Langflow はデフォルトの `make -C infra up` には含まれません。詳細は [Langflow Ingest](docs/current/features/ingest.md) と [インフラ](docs/current/infrastructure.md) を参照してください。

1. 本体クイックスタートの 1–2（`.env` と `OPENAI_API_KEY`）が済んでいることを確認します。アプリスタックの起動は不要です。

2. Langflow を起動します。

```bash
make -C infra langflow-up
```

3. http://localhost:7860 を開きます。未 import なら `infra/langflow/flows/Ingest.json` と `infra/langflow/flows/QueryPgVector.json` を import します。

4. UI で `Ingest` を実行し、専用 DB の Collection へ書き込みます。ホスト原本の置き場は `data/ingest/` です（Langflow My Files ではありません）。

5. UI で `QueryPgVector` を実行し、Collection の類似検索を確認します。

6. （任意）アプリスタックが起動済みなら、Collection をアプリの `documents` へ複製できます。

```bash
make -C infra import-langflow
```

API で投入と複製を一度に行う場合は `make -C infra ingest-langflow`（既定 `data/ingest/`）。アプリ Postgres が必要です。

7. 停止します。

```bash
make -C infra langflow-down
```

## サービス

| サービス | URL |
|---|---|
| Chainlit | http://localhost:8080 |
| Keycloak | http://localhost:8081 |
| FastMCP | http://127.0.0.1:8000/mcp |
| Langfuse | http://localhost:3000 |
| アプリ Postgres | localhost:5433 |
| Langflow（任意） | http://localhost:7860 |
| Langflow Postgres | localhost:5434 |

## 開発

```bash
uv sync --extra dev
uv run pytest
```

## MCP Inspector

```bash
npx @modelcontextprotocol/inspector
```

`http://127.0.0.1:8000/mcp`（Streamable HTTP）に接続します。
