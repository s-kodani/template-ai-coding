# Transport and State

このreferenceはTransport、Stateless core、Application state、MRTR、Extensionsを判断するときに読む。

## 1. Transport Selection

### Remote service

Cloud APIや共有サービスを公開する場合は、対象SDKがサポートする最新のStreamable HTTPを原則候補とする。

### Local integration

Filesystem、Desktop app、localhost、OS resourceへのアクセスが必要ならstdioまたは対象Hostが推奨するLocal packaging方式を検討する。

Local stdioをDistribution方式として選ぶ場合は、runtime依存・更新方式・install UXも評価する。

## 2. Modern Stateless Core

2026-07-28系ではprotocol coreはstateless。
新規実装を以下へ安易に依存させない。

```text
initialize handshake
Mcp-Session-Id
implicit per-connection state
sticky session
```

Legacy compatibilityが必要な場合だけ、使用SDKの公式migration / compatibility mechanismに従う。

## 3. Stateful Application

ProtocolがstatelessでもApplication stateは保持できる。

状態を跨ぐ場合はopaque handleを明示的に返す。

```text
create_browser
  ↓
browser_id
  ↓
navigate(browser_id, url)
  ↓
close_browser(browser_id)
```

State handleは以下を満たす。

- 推測困難
- 内部構造を露出しない
- lifetime / expiryが定義されている
- authenticated principalへserver-sideでbindされる
- handleの所持だけをAuthorizationとみなさない
- cleanup strategyがある

## 4. Streamable HTTP

SDK対応時はtransport protocolを自前実装しない。
Gateway / Proxyを挟む場合は最新仕様のrouting headerを確認する。

2026-07-28系では `Mcp-Method` / `Mcp-Name` などのheader-based routingが導入されている。
HeaderをAuthorizationやroutingに利用する場合は、Server側でrequest bodyとの整合性を検証する。

Origin validationを実装する。
Local HTTP serverは原則loopbackへbindし、理由なく`0.0.0.0`へ公開しない。

## 5. stdio

stdioではstdoutをMCP protocol専用にする。

```text
stdout = protocol
stderr = logs
```

通常ログをstdoutへ出してProtocol streamを壊さない。

## 6. MRTR

最新仕様と対象ClientがMulti Round-Trip Requestsをサポートする場合、追加入力を必要とする処理に利用できる。

Client capabilityを確認せず必須依存にしない。
Host互換性が必要ならfallbackを設計する。

## 7. Extensions

Tasks、MCP AppsなどのExtensionは、対象SDK・Host・Client supportを確認した上で利用する。

Coreで解ける問題を不要にExtension依存へしない。
Extensionを必須化する場合はsupported clientsを明示する。

## 8. Long-running Operations

長時間処理では以下を検討する。

- timeout
- cancellation
- progress
- task model
- resumability
- idempotency
- polling / re-entry strategy

単一同期requestを無制限に保持しない。
