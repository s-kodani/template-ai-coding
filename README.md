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

5. Chainlit は http://localhost:8080、Langfuse は http://localhost:3000 を開きます。

6. Langfuse でサインアップ後、`LANGFUSE_PUBLIC_KEY` と `LANGFUSE_SECRET_KEY` を `.env` に追加し、アプリサービスを再起動します。

## サービス

| サービス | URL |
|---|---|
| Chainlit | http://localhost:8080 |
| FastMCP | http://127.0.0.1:8000/mcp |
| Langfuse | http://localhost:3000 |
| アプリ Postgres | localhost:5433 |

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
