---
type: Decision Record
title: "ADR-0002: アプリデータに PostgreSQL pgvector"
description: embedding を pgvector 付き専用 Postgres に保存する。
tags: [decision, postgres, pgvector]
status: stable
decision_status: accepted
---

# ADR-0002: アプリデータに PostgreSQL pgvector

## 背景

ベクトル検索には、Langfuse インフラ DB とは分離した永続ストレージが必要。

## 決定

- アプリ文書と embedding には **PostgreSQL 17 + pgvector** を使用する
- 公式 compose スタックの Langfuse Postgres とは **分離** する
- cosine 距離と HNSW インデックスを使用し、embedding 次元は 1536（`text-embedding-3-small`）で固定

## 結果

- Qdrant / Chroma を導入せず、ローカル検証用の単一データストアで運用可能
- モデル変更時は自動再インデックスではなく re-seed が必要
