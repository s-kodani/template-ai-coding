---
type: Business Requirements
title: ビジネス要件
description: Keycloak 認証付きチャット UI による MCP ベクトル検索と、Langflow から documents への Ingest。
tags: [requirements, local, auth]
status: stable
generated:
  at: "2026-09-13T08:20:00Z"
  by: process:cursor-agent
---

# ビジネス要件

## 目的

以下を検証する **ローカル専用** の開発者向けスタックを提供する。

1. PostgreSQL + pgvector 上の FastMCP ベクトル検索
2. Keycloak OAuth でログインしたうえで、MCP Gateway 経由で knowledge-mcp（ベクトル検索）および web-search-mcp（Web 検索）ツールを呼び出し、Langfuse ルートトレースを持つ Chainlit チャット UI（追加 MCP サーバを UI から接続可能）
3. Chainlit、MCP Gateway、MCP クライアント/サーバー、embedding、Postgres クライアントスパンにわたる end-to-end 親子トレース
4. 任意の Langflow サイドカーによるファイル Ingest。ホスト原本を Files / Flow API で投入し、専用 Collection から `documents` へ adapter で複製して Chainlit / FastMCP から検索する

## 利用者

- MCP ツール契約、検索品質、トレース伝播、ローカル OAuth / Token Exchange / 直結 3LO を検証する開発者。認証の現行シーケンスは [認証認可](/current/features/authentication.md)

## スコープ外

- 本番公開、マルチテナント、本番用 TLS や Keycloak クラスタ
- Langfuse / Langflow の SSO
- Langfuse トレース以外の metrics / logs パイプライン
- MCP Resource / Prompt、MCP 経由の ingest 変更
- 3 つ目以降の Gateway MCP サーバー、CIMD、mTLS、Redis トークンキャッシュ。直結 MCP のクライアント登録はローカル匿名 DCR（[ADR-0014](/decisions/ADR-0014-mcp-direct-three-legged-oauth.md)）
