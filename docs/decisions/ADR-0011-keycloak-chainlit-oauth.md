---
type: Decision Record
title: "ADR-0011: Keycloak を Chainlit のローカル IdP にする"
description: ローカル検証スタックの Chainlit 認証に Keycloak OAuth / OIDC を使う。
tags: [decision, architecture, authentication, keycloak, chainlit]
status: stable
decision_status: accepted
generated:
  at: "2026-08-29T14:30:00Z"
  by: process:cursor-agent
---

# ADR-0011: Keycloak を Chainlit のローカル IdP にする

## 背景

Chainlit は認証なしでホストに公開されていた。ローカルでも IdP を含む OAuth フローを検証するため、専用の Identity Provider が必要になった。

候補は次のとおり。

- Chainlit のパスワード認証のみ
- GitHub / Google など外部 IdP
- Keycloak を Compose に載せる

外部 IdP は開発者アカウントとインターネット到達性に依存する。パスワード認証だけでは OIDC クライアントとしての検証にならない。

## 決定

- ローカル IdP として **Keycloak**（`keycloak/keycloak:26.4.5`、`start-dev --import-realm`）をアプリ Compose に含める
- Chainlit は組み込みの **generic OAuth provider** を使う（`OAUTH_GENERIC_NAME=keycloak`）。組み込み Keycloak provider は単一 `BASE_URL` のためブラウザ向けホストとコンテナ DNS を分けられないので、`OAUTH_KEYCLOAK_NAME=unused` で id 衝突を避ける
- ブラウザの認可 URL は `http://localhost:8081`、Chainlit コンテナからの token / userinfo は Compose DNS の `http://keycloak:8080` を使う
- 対象は Chainlit のみ。FastMCP、Langfuse、Langflow の SSO は導入しない
- 認可は「Keycloak でログインできた利用者はチャット可能」とし、RBAC は持たない
- realm / client / 開発ユーザーは Git 上の realm JSON を Source of Truth とし、専用 Postgres は持たない

## 改訂

knowledge-mcp を Keycloak Resource Server とし、Chainlit トークンのパススルーを禁止する決定は [ADR-0012](/decisions/ADR-0012-mcp-gateway-resource-server.md)。Chainlit ログインの IdP としての Keycloak 採用は本 ADR のまま。

## 結果

- `make -C infra up` で Keycloak と Chainlit が揃い、未ログインではチャットできない
- ホストから Keycloak 管理 UI（`:8081`）と Chainlit（`:8080`）に到達できる
- Chainlit はアプリ Postgres を data layer に使わない（`DATABASE_URL` を空にする）。認証後に存在しない `User` テーブルへ問い合わせない
- start-dev のためデータはコンテナ再作成で消える。realm 定義を変えたあとは Keycloak コンテナを再作成する
- クライアントシークレットと管理者パスワードはローカル開発用プレースホルダであり、本番秘密ではない
