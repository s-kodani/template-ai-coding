---
type: Decision Record
title: "ADR-0003: traced MCP クライアント UI として Chainlit"
description: Chainlit がチャット UI、Langfuse ルートトレース、FastMCP クライアントを同一プロセスで担う。
tags: [decision, chainlit, ui]
status: stable
decision_status: accepted
---

# ADR-0003: traced MCP クライアント UI として Chainlit

## 背景

end-to-end トレーシングには、ツール呼び出し時の MCP `_meta` トレース伝播が必要。LibreChat は SEP-414 `_meta` を注入せず、Mongo / Redis / Meilisearch を追加してもトレース要件を満たさない。

## 決定

- 検証用チャット UI として **Chainlit** を採用する
- MCP ツールは **アプリケーションコード** から FastMCP Client で呼び出す（Chainlit 内蔵 MCP UI は使わない）
- 同一プロセス内で FastMCP import より前に Langfuse を初期化する

## 結果

- 開発者向け UI でローカル検証に十分
- プロセスが分離された環境（Docker compose）では、ツール呼び出しをまたいだ親子トレース結合が機能する
