---
type: Decision Record
title: "ADR-0007: document_id / content_hash による冪等な再 Ingest"
description: 未変更は Skip、変更時は document_id 配下を削除してから再投入する。
tags: [decision, ingest, postgres]
status: stable
decision_status: accepted
---

# ADR-0007: document_id / content_hash による冪等な再 Ingest

## 背景

[ADR-0006](/decisions/ADR-0006-documents-chunk-schema.md) は `(document_id, chunk_index)` で upsert する。chunk 数が減った再投入では、使われなくなった行が残る。

`documents` は原本ではなく検索インデックスである。本運用前に、同一文書の再投入で行が増殖しないライフサイクルが必要になる。

## 決定

1. 各 chunk は `document_id`（親）、`id`（chunk_id / MCP ヒット行 UUID）、`content_hash`、`ingested_at`、`embedding_model` を持つ。
2. `content_hash` は chunk 本文の SHA-256（UTF-8 hex）とする。
3. 同一 `document_id` について、`chunk_index` 順の hash 列と `embedding_model` が一致すれば **Skip**（embedding 再計算もしない）。
4. 一致しなければ当該 `document_id` の全 chunk を削除してから再 Insert する。
5. 文書単位削除は `DELETE WHERE document_id = $1`。MCP ツールは read-only のまま。操作は `scripts/delete_document.py`。
6. 障害調査用 metadata は `source` / `chunk_index` / `ingest_version` を必ず載せる。
7. seed と Langflow import は同じライフサイクル関数を使う。

## 検討した代替

- `(document_id, chunk_index)` upsert のみ — chunk 数減少時のゴミ行が残るため不採用
- 原本ファイル全体の hash だけを見る — seed fixture はインライン本文であり、chunk 列の一致を直接検証できないため不採用
- MCP ingest / delete ツール — read-only 契約を壊すため不採用

## 結果

- 未変更の再 seed / 再 import で chunk 行が増えない
- 変更時は旧 chunk が残らない
- 再投入するとヒット行 UUID（`id`）は採番し直される。`get_document` は親全文結合をしない（[API](/current/features/api.md)）
- Embedding モデル混在は同一インデックスで禁止。自動切替はしない
