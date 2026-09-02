# Version and Sources

このreferenceは、MCP仕様・SDK・deprecated機能・互換性を判断するときだけ読む。

## Source of Truth

以下の優先順位で確認する。

1. MCP公式Specification
2. MCP公式Security Best Practices
3. 使用する公式SDKのドキュメント / migration guide
4. MCP Inspector / Conformance関連の公式情報
5. 対象Host固有の公式ドキュメント
6. 既存Repositoryの制約
7. その他の記事・Sample

古いBlog、Stack Overflow、古いGitHub Sampleだけを根拠に判断しない。

## 公式入口

- MCP Specification: `https://modelcontextprotocol.io/specification/`
- MCP Blog: `https://blog.modelcontextprotocol.io/`
- MCP GitHub organization: `https://github.com/modelcontextprotocol`

作業時点のstable specificationを必ず再確認する。

## Skill作成時点の基準

2026-08-22時点で、stable specificationは `2026-07-28`。

このversionでは主に以下が導入・変更されている。

- Stateless protocol core
- Handshake / protocol-level sessionの廃止
- Self-describing requests
- `Mcp-Method` / `Mcp-Name` によるheader routing
- Cacheable / deterministic list responses
- Multi Round-Trip Requests (MRTR)
- Authorization hardening
- Extensions framework
- Tasks extension
- Full JSON Schema 2020-12 for Tools
- Formal deprecation policy

ただしこのファイルのversion値を将来も固定的に信用してはならない。

## SDK Gate

作業開始時に必ず記録する。

```text
Target MCP specification:
Language:
SDK:
SDK version:
Transport:
Target hosts:
Legacy versions required:
```

公式SDKが対象protocol versionをサポートしていることを確認する。

可能な限りTier 1 SDKを優先する。
Skill作成時点ではTypeScript / Python / Go / C#がTier 1。

## Compatibility

複数protocol versionを扱う場合は以下を確認する。

- Schema feature差分
- Transport差分
- Session / initialization差分
- Structured output差分
- Authorization差分
- Client capability差分
- Deprecated feature依存

互換性対応を暗黙に実装しない。
「どのversionを何のためにサポートするか」を明記する。

## Deprecation

新規設計でdeprecated featureを原則採用しない。
既存実装に含まれる場合は、最新Specificationで状態とmigration pathを確認する。

2026-07-28系ではRoots、Sampling、Logging、legacy HTTP+SSEなどの扱いが変更・deprecated対象になっているため、記憶ではなく必ず公式仕様を確認する。
