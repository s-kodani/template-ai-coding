---
name: mcp-server-engineering
description: >
  MCPサーバーの新規実装、既存実装の変更、設計レビュー、Tool/Resource/Prompt設計、
  Transport、Authorization、Security、Testing、Production readinessを扱う際に使用する。
  最新のMCP仕様と公式SDKを確認し、LLMから利用しやすく、安全で、テスト可能かつ運用可能な
  MCPサーバーを設計・実装するための判断フローと品質ゲートを提供する。
version: 0.2.0
---

# MCP Server Engineering

## 目的

MCPサーバーを「動作する」だけでなく、以下を満たす状態まで設計・実装・検証する。

- 最新MCP仕様への準拠
- LLMが正しくToolを選択し、正しいargumentを生成できるInterface設計
- Tool / Resource / Promptの責務分離
- Stateless coreを前提としたスケーラブルな設計
- 最小権限のAuthorizationとMCP固有のSecurity対策
- Schema-drivenな入出力契約
- 回復可能なError handling
- Timeout / Cancellation / Retry / Paginationへの対応
- Observabilityと監査可能性
- 自動テスト、Inspector、実Clientによる検証

MCPの仕様変更は速い。記憶している仕様だけを根拠に実装してはならない。

---

# Progressive Disclosure

このSkillでは必要な情報だけを段階的に読む。

**最初はこの `SKILL.md` だけを読む。**

詳細が必要になった時だけ、以下の対応表から該当するreferenceを読む。全referenceを一括で読み込まない。

| 判断・作業 | 読むreference |
|---|---|
| 最新仕様、SDK version、deprecated機能、Source of Truth | `references/version-and-sources.md` |
| Tool設計、Tool description、inputSchema、property description、outputSchema | `references/tool-design.md` |
| Streamable HTTP、stdio、Stateless core、State handle、MRTR、Extensions | `references/transport-and-state.md` |
| OAuth、scope、token、SSRF、state handle保護、secret | `references/security-and-authorization.md` |
| Unit/Integration/Contract/Security test、Inspector、Observability | `references/testing-and-observability.md` |
| MCP 作業の完了報告・検証記録（共通ワークフローは `AGENTS.md` / implementation-workflow Skill） | `references/mcp-completion-checklist.md` |

同じルールを `SKILL.md` とreferenceの両方に重複して記載しない。

---

# 1. 作業開始時の必須確認

実装やレビューを開始する前に、以下を確認する。

1. リポジトリの `AGENTS.md` とプロジェクト固有ルール（`implementation-workflow` Skill 指定がある場合は着手前に `.agents/skills/implementation-workflow/SKILL.md` を読む）
2. 使用言語とMCP SDK
3. SDK versionと対象MCP specification
4. Transport
5. Authentication / Authorization方式
6. 既存Tool / Resource / Prompt
7. Test / CI構成
8. Deployment方式
9. 関連ドキュメント / ADR
10. 今回の作業を管理する既存GitHub Issueの有無

GitHub Issueについては、**すでに手動作成済みのIssueが存在するかユーザーに確認する。**
既存Issueの有無を確認せず、新規Issueを勝手に作成してはならない。

MCP仕様・SDKの確認方法は `references/version-and-sources.md` を読む。

---

# 2. Version Gate

コード変更前に以下を明示する。

```text
Target MCP specification:
SDK:
SDK version:
Transport:
Target MCP clients/hosts:
Legacy protocol support:
```

SDKが対象Specificationをサポートしていることを公式情報で確認する。
可能な限り公式Tier 1 SDKを利用する。
理由なくMCP protocolを独自実装しない。

---

# 3. Architecture Discovery

実装前に最低限以下を整理する。

## Integration target

何と接続するか。

- SaaS API
- REST / GraphQL API
- Database
- Filesystem
- Local application
- OS / Hardware
- Internal service
- Pure computation

## Users

誰が使うか。

- 個人
- 社内
- 特定Tenant
- SaaS利用者
- Public

## Action surface

小規模な操作面では原則として意味の明確なAction単位にToolを分ける。
大規模APIでは `search/discover + execute` 型も検討する。

単純なendpoint数ではなく、以下で判断する。

- Tool selection精度
- context消費量
- mutationの安全性
- discoverability
- schemaの安定性

Tool設計が主題になったら `references/tool-design.md` を読む。

---

# 4. Primitive Selection

すべてをToolにしない。

```text
Action                  → Tool
Context / browsable data → Resource
Reusable user workflow   → Prompt
```

Toolはモデルが実行するActionに限定する。
ResourceはHostがContextとして取得するデータに向く。
Promptはユーザーが明示的に開始する再利用可能Workflowに向く。

---

# 5. Transport / State

Remote serviceでは原則として最新仕様のStreamable HTTPを検討する。
Local integrationではstdioまたは対象Hostがサポートする配布方式を検討する。

新規実装を古いsession前提へ安易に寄せない。
Application stateが必要な場合は、opaqueなstate handleとして明示的に扱う。

Transport、State、MRTR、Extensionsの詳細判断が必要になったら `references/transport-and-state.md` を読む。

---

# 6. MCP Interface Quality Gate

ToolはAPI定義であると同時にLLM向けInterfaceである。
以下を一体として設計する。

```text
Tool name             → どのToolを選ぶか
Tool description      → いつ使うか / 何ができるか
inputSchema           → どう呼び出すか
property.description  → 各argumentに何を入れるか
outputSchema          → 結果をどう解釈するか
```

LLMがToolやparameterの意味を推測しなければならない状態を未完成とみなす。

詳細なTool設計ルールは `references/tool-design.md` を読む。

---

# 7. Security Gate

Remote / authenticated MCP Serverでは、Securityを後付けにしない。
最低限以下を設計時に確認する。

- Server-side authorization
- Least privilege scopes
- Token audience / issuer / expiry validation
- Token passthrough禁止
- State handle ownership validation
- Secret管理
- Input validation
- Output sanitization
- Rate limiting
- SSRF対策（外部URL取得がある場合）
- Destructive operationの保護

Authorizationや外部アクセスを実装する場合は `references/security-and-authorization.md` を読む。

---

# 8. Implementation Architecture

可能な限り以下を分離する。

```text
Transport Layer
      ↓
MCP Interface Layer
      ↓
Application Service
      ↓
Domain / Integration Layer
      ↓
External API / DB
```

Tool handlerへBusiness Logicを詰め込まない。
Tool handlerは主に次を担当する。

- validate
- authorize
- delegate
- result mapping
- error mapping

Protocolを介さずApplication LogicをUnit Testできる構造を優先する。

---

# 9. Runtime Resilience

External I/Oにはtimeoutを設定する。
Cancellationは可能な限り下位層まで伝播させる。

Mutationは無条件retryしない。
必要に応じてidempotency key / request ID / deduplicationを使う。

大量結果は1回で返さずPaginationを検討する。

Long-running operationでは、対象仕様・SDK・Clientが対応している場合にTask / progress / resumabilityを検討する。

---

# 10. Verification Gate

実装完了前に、変更内容に応じて以下を実施する。

- Unit Test
- Schema Test
- Tool Contract Test
- Integration Test
- Transport Test
- Authorization Test
- Security Test
- MCP Inspector
- Conformance Test（利用可能な場合）
- Real Client Smoke Test（対象Hostがある場合）
- Tool Usability Evaluation

詳細な観点と最低ケースは `references/testing-and-observability.md` を読む。

実行していないテストを成功と報告してはならない。

---

# 11. Definition of Done

以下を満たさない限り完了とみなさない。

- 最新MCP Specificationを確認した
- SDK compatibilityを確認した
- Transport選択理由を説明できる
- Tool / Resource / Promptの責務が整理されている
- Tool Schemaが明示されている
- Parameter semanticsが必要十分にdescription化されている
- Input validationがある
- AuthorizationがServer-sideで実施されている
- Token passthroughをしていない
- State handleが適切に保護されている
- SecretがProtocol / logへ漏れない
- ErrorがProtocol / Executionで適切に分類されている
- Timeout / Cancellation / Retryを考慮した
- 大量結果にPaginationを考慮した
- Observabilityがある
- 必要な自動テストが通っている
- Inspectorで確認した
- 対象Hostがある場合Smoke Testした
- GitHub Issue / checkpointが最新状態になっている
- 実施した検証結果と残課題を報告できる

---

# 12. 禁止事項

- 最新Specificationを確認せず実装する
- 古いBlogやSampleを最新仕様として扱う
- 理由なくMCP protocolを自前実装する
- 新規Serverをimplicit session前提で設計する
- 巨大な万能Toolを安易に作る
- Tool argumentを無制約な自由形式stringだけで定義する
- Parameter semanticsが曖昧なままdescriptionを省略する
- Read / Write / Deleteを不用意に1 Toolへ統合する
- Tool annotationをAuthorizationとして扱う
- MCP tokenをUpstreamへpassthroughする
- State handleをAuthenticationとして扱う
- SecretをTool output / Resource / Prompt / logへ出す
- stdioでstdoutへ通常ログを出す
- External I/Oをtimeoutなしで実行する
- Mutationを無条件retryする
- Client support未確認のExtensionへ必須依存する
- Deprecated featureを新規設計で無条件採用する
- InspectorだけでProduction readinessを判断する
- 未実施テストを成功として報告する

---

# 13. 設計原則

迷った場合は以下を優先する。

```text
Explicit > Implicit
Typed > Free-form
Stateless > Connection state
Least privilege > Convenience
Narrow tools > Ambiguous tools
Structured output > Text parsing
Deterministic > Dynamic
Recoverable errors > Generic failures
Official SDK > Hand-written protocol
Current specification > Old examples
Server-side enforcement > Client trust
```
