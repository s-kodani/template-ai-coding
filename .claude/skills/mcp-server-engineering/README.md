# mcp-server-engineering Skill

MCP Serverの実装・レビューを、最新仕様、Tool usability、Security、Testing、運用性まで含めて品質ゲート化するSkillです。

## Structure

```text
mcp-server-engineering/
├── SKILL.md
└── references/
    ├── version-and-sources.md
    ├── tool-design.md
    ├── transport-and-state.md
    ├── security-and-authorization.md
    ├── testing-and-observability.md
    └── mcp-completion-checklist.md
```

`SKILL.md` は判断フローだけを保持し、詳細は必要なときだけ `references/` から読む設計です。

特に `references/tool-design.md` には、`inputSchema.properties.*.description` をLLM向けInterface metadataとして扱うルールを追加しています。
