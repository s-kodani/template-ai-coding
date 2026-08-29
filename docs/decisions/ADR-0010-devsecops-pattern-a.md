---
type: Decision Record
title: "ADR-0010: DevSecOps パターンA（OSS Shift Left）"
description: Ruff/Bandit/uv audit/gitleaks/Trivy と pre-commit による最小 OSS 中心のセキュリティ検証。
tags: [decision, devsecops, ci, security]
status: stable
decision_status: accepted
generated:
  at: "2026-08-29T08:00:00Z"
  by: process:cursor-agent
---

# ADR-0010: DevSecOps パターンA（OSS Shift Left）

## 背景

リポジトリはローカル検証向けスタックであり、当初 CI は OKF 検証のみだった。依存関係の lock 未コミット、PR 時の自動テスト・lint・脆弱性スキャンがなく、API キー等を扱う構成上、Shift Left なセキュリティゲートが必要になった。

SaaS 統合（Snyk / SonarCloud 等）は運用コストと外部依存が増えるため、まず OSS と GitHub 標準機能で最小構成を採用する。

## 決定

**パターンA** — 最小・OSS・`uv` 親和の DevSecOps を 3 フェーズで導入する。

### Phase 1 — CI 基盤

| 要素 | 内容 |
|---|---|
| CI | `.github/workflows/ci.yml`: `ruff check`, `pytest`, `docker compose build` |
| Lock | `uv.lock` をコミットし CI で `uv sync --frozen` |
| 更新 | Dependabot（pip / GitHub Actions、週次） |
| OKF | 既存 `.github/workflows/okf.yml` は維持 |

### Phase 2 — セキュリティスキャン

| ツール | 対象 | CI |
|---|---|---|
| Ruff `S` / `B` / `TRY` | Python lint（セキュリティ関連） | quality ジョブ |
| Bandit | Python SAST | security ジョブ |
| `uv audit` | Python SCA（OSV） | security ジョブ |
| gitleaks | シークレット | security ジョブ |
| Trivy | Docker イメージ（CRITICAL/HIGH、未修正のみ失敗、`scanners: vuln`） | build-and-scan ジョブ |
| pre-commit | ローカル Shift Left | `ruff` / gitleaks / bandit |

Bandit は `tests/` を除外し、`B101`（assert）は dev 向けのため skip する。

### Phase 3 — ガバナンス

- 本 ADR で方針を記録
- [インフラ](/current/infrastructure.md) に CI/CD・検証コマンドを追記
- `.github/CODEOWNERS` でセキュリティ関連パスを保護
- [Release Log](/releases/log.md) に未確定変更として記録

### 採用しなかったもの（Out of Scope）

- CodeQL / Snyk 等の SaaS 統合
- Branch protection（リポジトリ設定、手動）
- Checkov / Hadolint（Compose/Dockerfile 専用 lint は Trivy で当面十分）

## 許容基準と SLA

| 種別 | 基準 |
|---|---|
| Trivy | CRITICAL / HIGH かつ修正版あり → CI 失敗。`ignore-unfixed: true` |
| uv audit | 既知 CVE 検出時は CI 失敗。Dependabot PR で週次対応 |
| gitleaks | 検出時は CI 失敗。`.env.example` のプレースホルダは許容 |
| Bandit / Ruff S | 検出時は CI 失敗。誤検知は `# nosec` / 設定で抑制（理由を PR に記載） |

## 代替案

- **パターンB（GitHub ネイティブ）**: CodeQL + Dependabot のみ — Bandit/Trivy の粒度が不足
- **パターンC（SaaS 統合）**: Snyk + SonarCloud — 小規模ローカルスタックには過剰

## 理由

既存の `uv` / `ruff` / GitHub Actions 運用と整合し、追加 SaaS なしで PR ゲートとローカル pre-commit を両立できる。Trivy はベースイメージ由来の CVE も可視化しつつ、未修正のみで失敗させノイズを抑える。

## 結果

- PR / `main` push で品質・セキュリティ・ビルドが自動検証される
- 開発者は `uv run pre-commit run --all-files` でローカル検証可能
- 依存更新は Dependabot が週次 PR を起票
- 詳細な実行手順は [インフラ](/current/infrastructure.md) の CI/CD 節を参照
