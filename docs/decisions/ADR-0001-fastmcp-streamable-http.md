---
type: Decision Record
title: "ADR-0001: FastMCP Streamable HTTP"
description: ナレッジ MCP サーバーに stateless Streamable HTTP の FastMCP を採用する。
tags: [decision, mcp, fastmcp]
status: stable
decision_status: accepted
---

# ADR-0001: FastMCP Streamable HTTP

## 背景

Chainlit と MCP Inspector からローカルで呼び出せる、ベクトル検索用 MCP サーバーが必要。

## 決定

- サーバーは **FastMCP**（Python 公式 SDK エコシステム）で実装する
- **Streamable HTTP** を `/mcp` で **stateless** モードで公開する
- レガシー HTTP+SSE およびプロトコルレベルのセッションはサポートしない

## 結果

- ローカル検証が簡素化され、MCP 2026-07-28 系の方向性と整合する
- Inspector と FastMCP Client が同一トランスポート設定を共有可能
