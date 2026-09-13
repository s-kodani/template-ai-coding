---
type: Decision Record
title: "ADR-0014: 直結 MCP クライアントの 3LO は Keycloak AS + MCP RS"
description: Inspector / Cursor 等の直結クライアントは Keycloak の認可コード + PKCE（DCR）でトークンを取り、MCP は既存の JWT 検証を共用する。Gateway Token Exchange は残す。
tags: [decision, architecture, authentication, mcp, keycloak, oauth]
status: stable
decision_status: accepted
generated:
  at: "2026-09-13T08:20:00Z"
  by: process:cursor-agent
---

# ADR-0014: 直結 MCP クライアントの 3LO は Keycloak AS + MCP RS

## 背景

[ADR-0012](/decisions/ADR-0012-mcp-gateway-resource-server.md) は Chainlit トークンのパススルーを禁止し、Gateway が Token Exchange して knowledge-mcp / web-search-mcp を Resource Server として呼ぶと決めた。Chainlit 自身の Keycloak ログインは認可コード（3LO）だが、直結 MCP クライアント（MCP Inspector、Cursor、Claude Desktop）は password grant + Token Exchange（`scripts/mcp_dev_token.py`）だった。

MCP Authorization は OAuth 2.1 の認可コード + PKCE を正規フローとする。クライアントは RFC 9728 Protected Resource Metadata から Authorization Server を知り、トークンの `aud` を MCP resource URL に束縛する。Inspector のコールバックはランダムな localhost ポートなので、固定 `redirectUris` の confidential クライアントだけでは足りない。

## 決定

- **MCP サーバーは Resource Server のまま**（FastMCP `JWTVerifier` + `RemoteAuthProvider`）。PRM の `authorization_servers` は Keycloak realm。`OIDCProxy` / `OAuthProxy` は使わない
- **Keycloak を 26.6.x に上げ**、ローカル realm で **匿名 DCR**（RFC 7591）を有効にする。trusted hosts は `localhost` / `127.0.0.1`。動的クライアントは optional scope として `mcp-tools` / `web-search-mcp-tools` を要求できる
- 直結 3LO で発行する JWT も、Gateway 交換後 JWT も **同じ検証**（`iss`、resource `aud`、必須 scope、realm role）。`azp=chainlit` を MCP 側で要求しない（要求すると Token Exchange 経路以外が壊れる）
- Chainlit → Gateway の Token Exchange（`authentication.mode=keycloak_token_exchange`、`azp=chainlit`）は [ADR-0012](/decisions/ADR-0012-mcp-gateway-resource-server.md) のまま
- CIMD は対象外のまま。MCP 仕様 2026-07-28 は DCR を非推奨とするが、ローカル HTTP と Inspector の localhost コールバックには DCR が合う。CIMD は HTTPS の `client_id` URL が前提
- password grant + Token Exchange の `scripts/mcp_dev_token.py` は非対話フォールバックとして残す
- ローカル HTTP を許容する。TLS / mTLS / Gateway ホスト公開はこの決定の対象外

## 代替

- **FastMCP OIDCProxy**: MCP が AS になり Keycloak へ代理する。Gateway が渡す Keycloak JWT と発行元が分かれ、`MultiAuth` が必要になるため不採用
- **固定 public クライアント**: Inspector のランダム redirect に合わない
- **Chainlit 経路も 3LO に置換**: 機密ホストの On-Behalf-Of として Token Exchange が適切。パススルー禁止を維持する

## 結果

- 直結クライアントは 401 の `WWW-Authenticate: resource_metadata=...` → PRM → Keycloak DCR → 認可コード + PKCE で接続できる
- 既定ツールは引き続き Gateway 経由。Chainlit トークンは MCP に届かない
- 現行シーケンスは [認証認可](/current/features/authentication.md)
- 匿名 DCR はローカル検証用。本番では登録ポリシーまたは CIMD が別途必要

## 関連

- 改訂先: [ADR-0012](/decisions/ADR-0012-mcp-gateway-resource-server.md)（直結 3LO を本 ADR へ委譲。CIMD は引き続き対象外）
- IdP: [ADR-0011](/decisions/ADR-0011-keycloak-chainlit-oauth.md)（Keycloak イメージを 26.6.x へ）
