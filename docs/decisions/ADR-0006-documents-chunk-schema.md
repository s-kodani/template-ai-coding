---
type: Decision Record
title: "ADR-0006: documents を Chunk 行として進化させる"
description: システム検索インデックス documents を 1 行 = 1 chunk にし、親 ID は source から決定的に生成する。
tags: [decision, postgres, pgvector, ingest]
status: stable
decision_status: accepted
---

# ADR-0006: documents を Chunk 行として進化させる

## 背景

現行 `documents` は 1 文書 = 1 ベクトルで、`source` が UNIQUE である。Langflow Ingest は複数 chunk を出すため、このままではシステムインデックスに載せられない。

[ADR-0005](/decisions/ADR-0005-langflow-ingest-sidecar.md) は、接続時に `documents` を Chunk 対応へ進化させ、LangChain / Langflow Collection をシステムインデックスにしないと決めている。

## 決定

1. **単一テーブル**のまま、1 行を 1 chunk とする。親テーブルは作らない。
2. 行 `id` が MCP の `document_id`（ヒット行 UUID）である。`get_document` はヒット行（chunk）を返す。
3. 親グループ列 `document_id` は、`source` があるとき `uuid5(NAMESPACE_URL, source)` とする。`source` が空のときは行 `id` を親にする。
4. `source UNIQUE` は廃止し、一意制約は `(document_id, chunk_index)` とする。
5. Langflow 出力はホスト script が専用 DB から読み、`documents` へ upsert する。SearchService は Collection を読まない。
6. langflow-postgres はホスト `5434` を公開し、adapter が `seed.py` と同様にホストから接続する。Langflow コンテナはアプリ Postgres に接続しない。

## 検討した代替

- 親 `documents` + 子 `chunks` の 2 テーブル — 親全文結合が未実装のため過剰
- Collection 直読み — [ADR-0005](/decisions/ADR-0005-langflow-ingest-sidecar.md) で不採用
- 親 ID を都度ランダム採番 — 再 seed / 再 import で行が増殖するため不採用
- import 用ワンショットコンテナ — ホスト script + ポート公開の方が seed と揃う

## 結果

- 同一親の複数 chunk を格納できる
- 既存 fixture は `chunk_index = 0` の 1 文書 = 1 chunk として互換維持できる
- 既存 volume は `init.sql` 再実行では更新されないため、明示的な migrate が必要
- chunk 数減少時のゴミ行削除は [ADR-0007](/decisions/ADR-0007-document-lifecycle.md) で、未変更 Skip と `document_id` 単位の削除・再投入として実装する
