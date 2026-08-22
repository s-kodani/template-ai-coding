---
type: UI Capability
title: Chainlit チャット UI
description: 1 つの Python プロセス内の開発者向けチャット UI と traced FastMCP クライアント。
tags: [chainlit, ui]
status: stable
---

# Chainlit チャット UI

## エントリポイント

- モジュール: `src/chat_ui/app.py`
- URL: http://localhost:8080

## 動作

- MCP ツールと対応する function tools を持つ OpenAI 互換チャットを維持
- ツール呼び出し時に `MCP_SERVER_URL` へ FastMCP Client で接続
- Chainlit 内蔵 MCP 接続 UI は **使用しない**（`_meta` 注入が保証されないため）
- Langfuse ルート観測 `chat.turn` とネストされた `llm.generate` を作成

## 設定

`CHAT_MODEL`、`OPENAI_API_KEY`、`MCP_SERVER_URL`、Langfuse キーはルートの `.env.example` を参照。
