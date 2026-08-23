---
type: UI Capability
title: Langflow Ingest
description: 任意サイドカーの Langflow でファイルを chunk 化し、adapter 経由で documents へ載せる。
tags: [langflow, ingest]
status: stable
---

# Langflow Ingest

## エントリポイント

- URL: http://localhost:7860
- 起動: `make -C infra langflow-up`
- 停止: `make -C infra langflow-down`
- システムインデックスへ複製: `make -C infra import-langflow`（ホスト `localhost:5434`。ポートが開かない場合は `langflow-down` のあと `langflow-up` で作り直す）

デフォルトの `make -C infra up` には含まれない。

## 動作

- Langflow UI からファイルをアップロードし、Ingest Flow を実行する
- 初期 Flow: Read File → Split Text（size 1000 / overlap 200）→ OpenAI Embeddings（`text-embedding-3-small`）→ PGVector
- PGVector の接続先は Langflow 専用 DB の `langflow_vectors`（collection `knowledge_documents_v1`）
- Langflow コンテナはアプリ Postgres に接続しない
- `scripts/import_langflow.py` が Collection を読み、アプリの `documents` へ chunk として upsert する
- SearchService / FastMCP / Chainlit は `documents` だけを検索する。Collection は直読みしない
- 確認済み Flow は `infra/langflow/flows/Ingest.json`。API キーと DB URL は空（環境変数 / UI Credential を使う）

## 接続例

Langflow コンテナ内（PGVector コンポーネント）:

```text
postgresql://langflow:langflow@langflow-postgres:5432/langflow_vectors
```

ホスト上の adapter:

```text
postgresql://langflow:langflow@localhost:5434/langflow_vectors
```

OpenAI API キーはルート `.env` の `OPENAI_API_KEY` をコンテナへ渡す。Flow へ埋め込まない。

再 Ingest で chunk 数が減った場合のゴミ行削除は行わない。

## 既知の制約: PGVector metadata の JSON 化

`Read File` → `Split Text` の Chunk metadata には、Langflow 内部の `Properties` オブジェクトが残ることがある。1.11.4 の `PGVector` はこれをそのまま `cmetadata` へ書くため、次のエラーで Ingest が失敗する。

```text
TypeError: Object of type Properties is not JSON serializable
INSERT INTO langchain_pg_embedding ... cmetadata
```

上流の修正 PR は未マージである（[langflow#10213](https://github.com/langflow-ai/langflow/issues/10213)）。PoC では PGVector コンポーネントの Code を開き、`to_lc_document()` の直後で metadata を JSON 化する。

```python
from langflow.serialization import serialize

# build_vector_store 内、Data を Document にした直後
documents.append(_input.to_lc_document())
documents[-1].metadata = serialize(documents[-1].metadata, to_str=True)
```

`from langflow.serialization import serialize` が失敗する場合は `from lfx.serialization import serialize` を使う。

保存して PGVector の Run を再実行する。確認済みの Ingest PGVector（`Ingest.json`）にはこの回避が入っている。
