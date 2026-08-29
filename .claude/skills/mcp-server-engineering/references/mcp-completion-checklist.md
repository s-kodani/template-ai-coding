# MCP Completion Checklist

MCP サーバーの実装・変更作業で、**完了報告と検証記録に追加する MCP 固有項目**です。

## 共通ワークフロー（先に読む）

このリポジトリでは、着手前・Issue 運用・Checkpoint・OKF 整合・Release Log は
[implementation-workflow](/.agents/skills/implementation-workflow/SKILL.md) と `AGENTS.md` に従います。
本ファイルは MCP 作業の**追加チェックリスト**であり、共通ワークフローの代替ではありません。

`AGENTS.md` と本体 Skill が競合する場合は、`AGENTS.md` を優先します。

---

## Issue への追記（MCP 作業時）

標準 Issue 本文に加え、必要に応じて以下を記録します。

- MCP specification / SDK version
- Transport（stdio / Streamable HTTP 等）
- Tool / Resource / Prompt の変更概要
- Security considerations（認可、token、SSRF 等）
- Test plan（Inspector、実 Client 含む）

進捗・Checkpoint・検証結果は Issue **コメント**へ追記します（本文を進捗メモで肥大化させない）。

---

## 完了報告テンプレート（Issue コメント / PR 補足）

```markdown
## MCP Design

Specification:
SDK:
SDK version:
Transport:
Authentication:
Primitives:
State model:

## Implemented
- ...

## Verification
- Unit:
- Contract:
- Integration:
- Inspector:
- Security:
- Real client:

## Remaining Risks
- ...

## Compatibility
- Supported MCP versions:
- Supported clients:
- Known limitations:
```

未実施のテストを成功と記載しない。

---

## 完了前チェック（MCP 固有）

- [ ] 最新 MCP Specification と SDK compatibility を確認した
- [ ] Transport 選択理由を説明できる
- [ ] Tool Schema と parameter description が LLM 向けに十分
- [ ] Server-side authorization と secret 漏洩対策を確認した
- [ ] 必要な自動テストが通っている
- [ ] MCP Inspector で確認した（該当時）
- [ ] 対象 Host で Smoke Test した（該当時）
- [ ] 残課題を別 Issue 化または明示した

詳細な品質ゲートは `references/testing-and-observability.md` と `SKILL.md` の Verification Gate を参照。
