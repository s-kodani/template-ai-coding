---
type: Infrastructure
title: インフラ
description: アプリ、Langfuse、任意 Langflow の Docker Compose スタック。
tags: [docker, langfuse, langflow, postgres]
status: stable
---

# インフラ

## Compose スタック

| スタック | パス | 用途 |
|---|---|---|
| Langfuse 公式 | `infra/langfuse/docker-compose.yml` + `network.yml` | トレース UI とストレージ |
| アプリケーション | `infra/app/compose.yml` | FastMCP、pgvector Postgres、Chainlit |
| Langflow（任意） | `infra/langflow/compose.yml` | Ingest PoC。`make -C infra langflow-up` |

アプリと Langfuse の共有 Docker ネットワーク: `observability`。Langflow スタックは独立ネットワークであり、このネットワークには参加しない。

アプリの Chainlit / MCP サーバーは、Langfuse Web が実際に待ち受ける `langfuse_default` ネットワークにも接続します（`langfuse-web:3000` への OTLP 送信用）。

## ホストポート

| サービス | ポート |
|---|---|
| Langfuse UI | 3000 |
| Chainlit | 8080 |
| FastMCP | 127.0.0.1:8000 |
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

UI は http://localhost:7860 。Langflow の PGVector は専用 Postgres の `langflow_vectors`（ホスト `localhost:5434`）へ書く。ホスト原本からの API Ingest は `make -C infra ingest-langflow`（既定 `data/ingest/`）。Collection からアプリの `documents` へは同コマンドが複製する。複製だけなら `make -C infra import-langflow`。

既存のアプリ volume を Chunk / ライフサイクル列へ更新するには、seed の前に migrate する（`make -C infra seed` は migrate を先に実行する）。

```bash
make -C infra migrate
make -C infra ingest-langflow
make -C infra ingest-langflow FILES='data/ingest/notes.md'
make -C infra import-langflow
make -C infra delete-document DOCUMENT_ID=<parent-uuid>
```

Langfuse API キーは初回サインアップ後に手動で作成し、リポジトリルートの `.env` にコピーします。

Langfuse スタック用の `infra/langfuse/.env` では、`ENCRYPTION_KEY` を 64 文字 hex（例: `openssl rand -hex 32`）に設定してください。形式が不正だと http://localhost:3000 が 500 になります。

## トレースエクスポート

Chainlit と FastMCP の両方で、FastMCP を import する **前に** Langfuse Python SDK を初期化します。キーが未設定の場合はトレースは no-op となり、サービスは起動可能です。

Langfuse SDK 4 はデフォルトで LLM / Langfuse スパン以外を落とすため、`should_export_span` で `fastmcp` と `opentelemetry.instrumentation.asyncpg` を追加許可します。httpx などの汎用クライアントスパンは送りません。

MCP `_meta` には FastMCP 既定の `traceparent` に加え、Langfuse の `langfuse_trace_id` baggage を載せます。これがないと、mcp-server プロセス側の FastMCP スパンが同一 `traceId` でもトレース一覧の追加ルートになります。

## 手動検証

1. **MCP Inspector**: `http://127.0.0.1:8000/mcp` に接続
2. **Chainlit**: `search_knowledge` が呼ばれる質問を送信
3. **Langfuse**: チャット 1 ターンあたり 1 本のトレースに、クライアント/サーバーのツールスパンがネストされていることを確認

### トレース検証チェックリスト（1 ターン = 1 trace）

| 確認項目 | 期待結果 |
|---|---|
| Langfuse トレース一覧 | `chat.turn` が **1 行** のみ（同一 `traceId` の FastMCP / ツールスパンはルートに出ない） |
| トレース詳細 | `llm.generate` が `chat.turn` の子 |
| ツール呼び出し | `search_knowledge` / `get_document` の input が tool observation に記録 |
| MCP サーバー | `tools/call …` SERVER span 配下に `search.embed` / `search.query` |
| Postgres | `search.query` 近傍に asyncpg クライアントスパン（CONNECT / SELECT 等） |
| 自動テスト | `uv run pytest tests/test_trace_propagation.py tests/test_langfuse_span_export.py` |
