# Testing and Observability

このreferenceは実装検証、CI、Inspector、Production readinessを確認するときに読む。

## 1. Unit Test

Application LogicをMCP TransportなしでTest可能にする。

最低限:

- normal path
- boundary
- invalid input
- upstream failure mapping
- authorization decision
- cancellation / timeout behavior（該当時）

## 2. Schema Test

Tool input/output schemaについて確認する。

- valid input
- missing required
- invalid enum
- boundary minimum / maximum
- unexpected property
- invalid format
- invalid output
- cross-field constraint

## 3. Tool Contract Test

次が意図せず変化していないことを確認する。

- Tool name
- Tool description
- inputSchema
- property descriptions
- outputSchema
- annotations
- deterministic ordering

SchemaはPublic Interfaceとして扱う。

## 4. Integration Test

実際のMCP Client / SDK test clientから、提供機能に応じて確認する。

```text
tools/list
tools/call
resources/list
resources/read
prompts/list
prompts/get
```

## 5. Transport Test

### stdio

- process startup
- stdout contaminationなし
- stderr logging
- graceful shutdown
- cancellation

### Streamable HTTP

- protocol version
- required headers
- header/body mismatch
- Origin validation
- authentication
- concurrent requests
- cancellation
- timeout

## 6. Authorization Test

最低限:

- no token
- malformed token
- expired token
- wrong issuer
- wrong audience
- insufficient scope
- correct scope
- tenant mismatch
- cross-user state handle

## 7. Security Test

変更内容に応じて確認する。

- malformed input
- oversized input
- injection-like input
- unauthorized mutation
- secret leakage
- rate limit
- SSRF
- redirect abuse
- idempotency abuse

## 8. MCP Inspector

Inspectorでは最低限以下を手動確認する。

- discovery / list
- Tool schema
- property descriptions
- tools/call
- structured output
- errors
- resources / prompts（提供時）
- authentication

Inspectorが動くことだけで自動テストを置き換えない。

## 9. Conformance

公式Conformance Testが利用可能なら実行する。
特にcustom transport、gateway、proxy、protocol implementationでは優先度を上げる。

## 10. Real Client Smoke Test

対象Hostが明確なら実Clientでも確認する。

確認する。

- Tool selection
- argument generation
- sibling Toolの使い分け
- structured output interpretation
- error recovery
- auth UX
- capability compatibility

## 11. Tool Usability Evaluation

Protocol上正しいだけでは不十分。
代表タスクをLLMへ与えて以下を評価する。

- 正しいToolを選ぶか
- 正しいargumentを作るか
- 不要なToolを呼ばないか
- Tool sequenceが適切か
- Errorから自己修正できるか

問題があればLLM promptで無理に補正する前に以下を見直す。

- Tool boundary
- Tool name
- Tool description
- input schema
- property description
- output schema
- error message

## 12. Observability

最低限観測する。

- request count
- tool invocation count
- latency
- error rate
- upstream latency
- upstream error
- authorization failure
- rate-limit event
- cancellation

可能ならW3C Trace Context / OpenTelemetryと統合する。
Correlation ID / trace IDをMCP requestからupstreamまで伝播する。

Secretや不要なTool input全文をlogに残さない。
