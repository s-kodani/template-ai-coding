# Security and Authorization

このreferenceは認証済みRemote MCP、外部API、State handle、Secret、SSRFを扱うときに読む。

## 1. Server-side Authorization

AuthorizationをClientやTool annotationへ委譲しない。
Tool execution時にServer-sideで毎回検証する。

確認項目:

- principal
- issuer
- audience
- expiration
- scope
- tenant / resource ownership

## 2. OAuth / Authorization Metadata

Protected Remote MCP Serverでは、作業時点の最新MCP Authorization Specificationを確認する。

OAuth 2.1ベースのResource Serverとして設計し、必要に応じて以下を確認する。

- Protected Resource Metadata
- Authorization Server discovery
- PKCE
- Resource Indicators
- issuer validation
- audience validation
- scopes
- Client metadata documents

Deprecated registration mechanismを新規設計へ無条件に採用しない。

## 3. Token Passthrough禁止

MCP Clientから受け取ったAccess TokenをそのままUpstream APIへ転送しない。

```text
MCP Client
   ↓ MCP resource token
MCP Server
   ↓ separate upstream credential/token
Upstream API
```

MCP ServerはInbound tokenを自分自身のresourceとして検証する。
Upstream credentialは別に取得・管理する。

## 4. Least Privilege

万能scopeを避ける。

避ける:

```text
*
all
full-access
admin:*
```

可能なら操作面に対応したscopeへ分割する。

```text
read:orders
write:orders
delete:orders
```

高権限操作はstep-up authorizationや明示確認を検討する。

## 5. State Handle Security

State handleは認証情報ではない。

毎回以下を照合する。

```text
authenticated principal
+
state handle owner / tenant
```

推測可能な連番を避ける。
期限切れ・revocation・cleanupを設計する。

## 6. Secrets

Secretを以下へ置かない。

- Source code
- Tool description
- input/output schema description
- Tool result
- Resource
- Prompt
- URL query
- routing header
- application log

環境変数または適切なSecret Managerから取得する。

## 7. Input / Output Security

すべてのToolで以下を実施する。

- input validation
- authorization
- rate limiting / abuse protection
- output sanitization

LLMが入力する値はtrusted inputとして扱わない。

## 8. SSRF

Serverが外部URLをfetchする場合はSSRFを考慮する。

最低限:

- scheme allowlist
- hostname / IP validation
- private / loopback / link-local制限
- cloud metadata endpoint制限
- redirect再検証
- DNS rebinding / TOCTOU考慮
- outbound network policy
- response size制限
- timeout

## 9. Destructive Operations

削除、停止、送信、決済、権限変更などでは以下を検討する。

- 独立Tool
- narrow scope
- user confirmation
- idempotency
- audit log
- dry-run / preview（可能な場合）
- rollback可能性

## 10. Logging Security

Logへ以下を残さない。

- Access Token
- Refresh Token
- API key
- Password
- Session secret
- unnecessary full input/output
- unnecessary PII

必要な場合はfield-level redactionを行う。
