---
type: Business Requirements
title: ビジネス要件
description: トレース付きチャット UI による MCP ベクトル検索と、Langflow から documents への Ingest。
tags: [requirements, local]
status: stable
---

# ビジネス要件

## 目的

以下を検証する **ローカル専用** の開発者向けスタックを提供する。

1. PostgreSQL + pgvector 上の FastMCP ベクトル検索
2. MCP ツールを呼び出し Langfuse ルートトレースを持つ Chainlit チャット UI（追加 MCP サーバを UI から接続可能）
3. Chainlit、MCP クライアント/サーバー、embedding、Postgres クライアントスパンにわたる end-to-end 親子トレース
4. 任意の Langflow サイドカーによるファイル Ingest。専用 Collection から `documents` へ adapter で複製し、Chainlit / FastMCP から検索する

## 利用者

- MCP ツール契約、検索品質、トレース伝播を検証する開発者

## スコープ外

- 本番公開、OAuth、マルチテナント運用
- Langfuse トレース以外の metrics / logs パイプライン
- MCP Resource / Prompt、MCP 経由の ingest 変更
