---
type: UI Capability
title: Langflow Ingest PoC
description: 任意サイドカーの Langflow でファイル投入と PoC 用ベクトル登録を検証する。
tags: [langflow, ingest]
status: stable
---

# Langflow Ingest PoC

## エントリポイント

- URL: http://localhost:7860
- 起動: `make -C infra langflow-up`
- 停止: `make -C infra langflow-down`

デフォルトの `make -C infra up` には含まれない。

## 動作

- Langflow UI からファイルをアップロードし、Ingest Flow を実行する
- 初期 Flow: Read File → Split Text（size 1000 / overlap 200）→ OpenAI Embeddings（`text-embedding-3-small`）→ PGVector
- PGVector の接続先は Langflow 専用 DB の `langflow_vectors`（collection `knowledge_documents_v1`）
- 投入結果は Langflow 上の Similarity Search で確認する。Chainlit / FastMCP の検索対象にはならない
- 確認済み Flow は `infra/langflow/flows/Ingest.json`。API キーと DB URL は空（環境変数 / UI Credential を使う）

## 接続例（Langflow コンテナ内）

```text
postgresql://langflow:langflow@langflow-postgres:5432/langflow_vectors
```

OpenAI API キーはルート `.env` の `OPENAI_API_KEY` をコンテナへ渡す。Flow へ埋め込まない。

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

保存して PGVector の Run を再実行する。Chainlit / FastMCP 側の検索には影響しない。

確認済みの Ingest PGVector（`Ingest.json`）にはこの回避が入っている。検索用 PGVector には不要。既存の Chainlit / FastMCP 検索は、この PoC の有無で変わらないことを確認した。
