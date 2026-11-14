---
type: Business Requirements
title: ビジネス要件
description: Keycloak認証付きOpen WebUIでMCP検索とMCP Appsを利用し、Langfuseで分散トレースを検証するローカルスタック。
tags: [requirements, local, auth, mcp-apps]
status: stable
generated:
  at: "2026-11-14T11:36:15Z"
  by: process:codex-agent
---

# ビジネス要件

## 目的

開発者が次の機能を検証できる、ローカル専用スタックを提供する。

1. PostgreSQL + pgvector上のナレッジ検索と、検索対象チャンクの本文取得。
2. KeycloakでログインするOpen WebUI。knowledge-mcpとweb-search-mcpをMCP Gateway経由で呼び出し、接続先ごとに閲覧・実行権限を分離する。
3. MCP Appsによる検索結果の一覧と本文詳細。サーバー側ページ取得で20件を超える結果も閲覧し、5・10・20件の表示件数と前後移動を選べる。
4. 会話、LLM、MCP、embedding、Postgresを同一Langfuseトレースに接続する。後から行うApp内操作は独立した操作トレースにする。
5. 任意のLangflowサイドカーによるファイルIngest。ホスト原本をFiles / Flow APIで処理し、専用Collectionからアプリの`documents`へ複製する。

## 利用者と権限

- MCPの契約、検索品質、Apps表示、トレース伝播、OAuth / Token Exchange / 直結3LOを検証する開発者。
- 開発ユーザー`dev`はknowledgeとWeb検索、`dev2`はWeb検索のみ、`readerless`はどちらのMCPも利用できない。MCP権限がない利用者も通常のチャットにはログインできる。
- MCP接続先は管理者がRegistryへ登録する。利用者による任意URLの追加接続は提供しない。

## 境界

- 詳細表示は検索したチャンクの本文。原本全体の結合や、App内で検索語を変更する機能は含めない。
- 検索結果は類似度順の候補であり、固定の関連度閾値による件数ではない。総件数・総ページ数は表示しない。
- ページ取得は現在のデータを参照する。同時Ingestに対するスナップショットの固定は行わない。

## スコープ外

- 本番公開、マルチテナント、本番用TLSやKeycloakクラスタ。
- Langfuse / LangflowのSSO、トレース以外のmetrics / logsパイプライン。
- MCP経由の文書追加・削除、Prompt、一般用途のResource公開。
- 3つ目以降のGatewayサーバー、CIMD、mTLS、Redisトークンキャッシュ。直結クライアント登録はローカル匿名DCRを使う。

現在の接続境界は[アーキテクチャ](/current/architecture.md)、認証フローは[認証認可](/current/features/authentication.md)、採用理由は[ADR-0015](/decisions/ADR-0015-open-webui-mcp-apps.md)を参照。
