---
type: UI Capability
title: Langflow Ingest
description: ホスト原本を Langflow Files / Flow API で Ingest し、adapter 経由で documents へ載せる。
tags: [langflow, ingest]
status: stable
---

# Langflow Ingest

## エントリポイント

- URL: http://localhost:7860
- 起動: `make -C infra langflow-up`
- 停止: `make -C infra langflow-down`
- システムインデックスへ複製: `make -C infra import-langflow`（ホスト `localhost:5434`。ポートが開かない場合は `langflow-down` のあと `langflow-up` で作り直す）
- API Ingest: `make -C infra ingest-langflow`（既定 `data/ingest/`。個別指定は `FILES='path1 path2'`）

デフォルトの `make -C infra up` には含まれない。

## 原本

原本の所在はホスト側である（[ADR-0008](/decisions/ADR-0008-host-originals-langflow-api.md)）。Langflow My Files は原本置き場ではない。

- 置き場: `data/ingest/`、または `make -C infra ingest-langflow FILES='...'` で渡すパス
- `scripts/run_langflow_ingest.py` が Files API（`/api/v2/files`）へアップロードし、Flow API（`/api/v1/run/{flow}`）で Ingest を実行し、終わったら uploaded file を削除する
- `documents.source` と親 `document_id` はホスト相対パスから決める。`title` は metadata に実名がなければホストファイル名を使う（`Untitled` は source が無い行のフォールバック）
- 複数ファイルは順次処理する（キューは持たない）

## 動作

- UI から手動アップロードして Ingest Flow を実行することもできる
- 初期 Flow: Read File（`File-ifAAu`）→ Split Text（size 1000 / overlap 200）→ OpenAI Embeddings（`text-embedding-3-small`）→ PGVector
- PGVector の接続先は Langflow 専用 DB の `langflow_vectors`（collection `knowledge_documents_v1`）
- Langflow コンテナはアプリ Postgres に接続しない
- `scripts/import_langflow.py` が Collection を読み、アプリの `documents` へ [ライフサイクル](/decisions/ADR-0007-document-lifecycle.md) で載せる
- SearchService / FastMCP / Chainlit は `documents` だけを検索する。Collection は直読みしない
- 確認済み Flow は UI から Export した次の 2 本。API キーと DB URL は空（環境変数 / UI Credential を使う）
  - `infra/langflow/flows/Ingest.json`（name `Ingest`）— 書き込み。PGVector は `ext:pgvector:PGVectorStoreComponent@official-mB2mI` 1 つ
  - `infra/langflow/flows/QueryPgVector.json`（name `QueryPgVector`）— Collection の類似検索確認。Embedding Model → PGVector（`official-JGTq0`）。アプリの SearchService は使わない
- API Ingest は `Ingest` だけを実行する。UI 上に同名 Flow が無ければ `Ingest.json` を import するか `LANGFLOW_FLOW_ID` を設定する。`QueryPgVector` は UI 確認用で、`ingest-langflow` からは呼ばない
- `/api/v1/run` は書き込み用 PGVector を出力対象にする。`output_type=debug` は Embedding の `httpx.Client` をシリアライズできずタイムアウトするため使わない
- `LANGFLOW_API_KEY` はルート `.env` のみ。未設定時は `auto_login` を試す。Git / Flow / compose には置かない

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

同一 `document_id` の本文 hash 列と embedding モデルが変わっていなければ Skip する。変わっていれば当該親の旧 chunk を削除してから再投入する。文書単位削除は `make -C infra delete-document DOCUMENT_ID=<uuid>`（`scripts/delete_document.py`）。

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
