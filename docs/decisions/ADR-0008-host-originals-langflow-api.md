---
type: Decision Record
title: "ADR-0008: 原本はホスト、Langflow Files API は一時転送"
description: 原本の SoT はホストパス。Langflow My Files は Flow 実行のための一時置き場にする。
tags: [decision, langflow, ingest]
status: stable
decision_status: accepted
---

# ADR-0008: 原本はホスト、Langflow Files API は一時転送

## 背景

[ADR-0005](/decisions/ADR-0005-langflow-ingest-sidecar.md) は Langflow を任意サイドカーにし、システムインデックスを `documents` に置いた。Phase 1 の投入は UI の My Files に依存していた。

Langflow を原本管理システムにすると、ファイル所有権と API キーがサイドカー側に残る。GUI で組んだ Ingest Flow は残しつつ、システムからファイルを渡して API 実行したい。

## 決定

1. 原本の Source of Truth はホスト上のパス（既定 `data/ingest/`、または CLI で渡したファイル）とする。
2. Langflow Files API は Flow へ渡すための一時転送だけに使う。実行後に uploaded file を削除する。
3. `documents.source` / `document_id` はホスト相対パスから決める。Langflow 側の `user_id/file_id` は親 ID に使わない。
4. 連携はホストスクリプト（`scripts/run_langflow_ingest.py`）とする。MCP ingest ツールは追加しない。
5. Langflow API キーはルート `.env` のみ。Git / Flow export / compose には置かない。未設定時はローカルの `auto_login` を試す。

## 検討した代替

- Langflow My Files を原本置き場にする — サイドカーへ所有権が移るため不採用
- ホストディレクトリを Langflow コンテナへマウントする — Files API / Flow API の検証にならないため不採用
- MCP ingest ツール — read-only 契約を壊すため不採用

## 結果

- UI 手動アップロードなしで Ingest Flow を実行できる
- 再投入の親 ID はホストパスで安定する（[ADR-0007](/decisions/ADR-0007-document-lifecycle.md)）
- Langflow ストレージに原本が残らない
- 小規模 batch はファイルを順次処理する。キュー / ワーカーは持たない
