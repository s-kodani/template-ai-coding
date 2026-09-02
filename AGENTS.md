# AGENTS.md

## 目的

このファイルには、**このリポジトリ固有**のルールと参照先のみを記載します。

共通ワークフロー（Implementation Plan、ADR 判定、Verification、OKF Documentation Reconciliation、Completion Report 等）の詳細は `implementation-workflow` Skill に従い、必要な reference だけを Progressive Disclosure で読んでください。

| トピック | 入口 |
|---|---|
| ワークフロー全体 | `.agents/skills/implementation-workflow/SKILL.md` |
| GitHub Issue / 進捗コメント / Checkpoint / Close | `references/github-issue-workflow.md`, `session-handoff.md`, `completion-report.md` |
| 完了後レビュー / ワークフロー遵守 | `references/review-and-compliance.md` |
| OKF / Release Log 運用 | `references/okf-documentation.md`, `release-note.md`, `verification.md` |

Skill とこのファイルが競合する場合は、**このリポジトリ固有ルールである `AGENTS.md` を優先**します。

---

## 使用する Skill

コードの実装、変更、リファクタリング、機能追加を行う場合は `implementation-workflow` Skill を使用します。

着手前に `.agents/skills/implementation-workflow/SKILL.md` を読み、以下のトリガーに従ってください。

| 変更対象 | 必須アクション |
|----------|----------------|
| `src/`、`scripts/`、`infra/`、`tests/` | 作業開始前に最新 `main` を取り込み → Phase 0〜2（Issue 確認・Implementation Plan を `.plans/` へ書き出し・ユーザー承認）→ 実装 → Phase 5 検証 |
| `src/` または `infra/` | Phase 6: 観測可能な変更があれば `docs/releases/log.md` の `## v?.?.? (未確定)` へ追記。PR 本文に `Release-Note: required` または `not-required` + `Reason` を宣言（CI 検証） |
| `docs/` の Current-state / ADR のみ | Phase 6 相当の整合確認 |
| 質問のみ（コード・ドキュメント変更なし） | 不要 |

### Skill カタログ（自前の正本: `.apm/skills/`）

| Skill | 用途 |
|-------|------|
| `implementation-workflow` | Issue / Plan / ADR / OKF / 検証の共通フロー |
| `test-strategy` | テスト観点表・リスクベースのテスト設計（**テスト方針の正本**） |
| `test-driven-development` | 自動化可能な振る舞い変更時の Red-Green-Refactor |
| `project-verification` | 本リポジトリ固有の CI / Docker / トレース検証コマンド |
| `mcp-server-engineering` | MCP サーバー設計・変更（併用） |
| `ponytail` | 最小実装（必要なテスト・検証は省略しない） |
| `grill-me` / `grilling` | 設計強度の Plan refinement |
| `commit-only` / `commit-push` / `commit-push-pr` | Git 操作（`delivery-reference.md` 参照） |
| `gh` | GitHub CLI 参照専用 |

自前 Skill は `.apm/skills/` を編集し、`apm install` で `.agents/skills/`（Cursor / Codex）と `.claude/skills/`（Claude）へ展開する。展開先は手編集しない。エージェントは展開先を読む。

### Agent カタログ（自前の正本: `.apm/agents/`）

| Agent | 用途 |
|-------|------|
| `review` | Phase 8 のコードレビューとワークフロー遵守。実装・編集はしない |

自前 Agent は `.apm/agents/<name>.agent.md` を編集し、`apm install` で `.cursor/agents/` と `.claude/agents/` へ展開する。Codex は `.codex/agents/<name>.toml` へ変換する。展開先は手編集しない。Phase 8 では呼べるときに `review` を起動する（自己レビューは残す）。

### APM 管理 Skill（編集禁止）

`apm.yml` で取り込む外部 Skill は **内容を編集しない**。リポジトリ固有のルールは `AGENTS.md` または自前 Skill（`test-strategy`、`implementation-workflow` 等）へ書く。`apm install` / 更新で upstream に戻る。

| Skill | ソース（`apm.lock.yaml` 参照） | リポジトリ固有ルールの置き場 |
|-------|------|------|
| `ponytail` | DietrichGebert/ponytail | `AGENTS.md` Coding conventions |
| `test-driven-development` | obra/superpowers | `test-strategy`（適用判断）、`AGENTS.md`（必須ケース） |
| `grill-me` / `grilling` | mattpocock/skills | `implementation-workflow` references |
| `gh` | cli/cli | 特になし（汎用 CLI 参照） |

MCP サーバー実装・変更では `mcp-server-engineering` Skill を併用します。MCP 固有の完了チェックは `references/mcp-completion-checklist.md` を参照します。

Pull Request は対応 Issue を `Refs #<issue>` または `Closes #<issue>` で明示します（`src/` 変更がある PR は CI で検証）。

作業開始前に `git fetch origin main` し、新規ブランチは `origin/main` から切ります。既存の作業ブランチでは `git merge origin/main` します（rebase は明示時のみ）。Cloud Agent の「fetch を先行しない」指示より本ルールを優先します。

Implementation Plan の一時ファイルは `.plans/`（git 管理外）へ書き出します。grilling の要否は変更強度に従いますが、ユーザー承認なしに Phase 3 / 実装へ進んではいけません。Cloud / background agent も例外ではありません。手順の詳細は `implementation-workflow` Skill に従います。

---

## GitHub Work Item Policy

このリポジトリでは、コードの実装・変更・リファクタリング・機能追加は **原則 GitHub Issue に紐付け** ます。

- **Issue**: 作業契約・作業履歴・Session Handoff
- **Pull Request**: 実装差分・Review
- **OKF Knowledge Bundle**: 現在状態と恒久知識
- **ADR**: 重要な設計判断の理由

Issue を Current-state Documentation や ADR の代替にしない。

Issue 本文・起票前確認・進捗コメント・Checkpoint・Resume・Close・完了後レビューの手順は `implementation-workflow` Skill の reference に従う（`github-issue-workflow.md`, `session-handoff.md`, `completion-report.md`, `review-and-compliance.md`）。

### このリポジトリ固有

- default branch は `main`。作業開始前に `git fetch origin main` し、新規ブランチはそこから切る。既存ブランチは `git merge origin/main`
- 新規 Issue 起票前に、ユーザーへ既存 Issue の有無を確認する（詳細は `references/github-issue-workflow.md`）
- PR は `Refs #<issue>` / `Closes #<issue>` を明示（`src/` 変更時 CI 必須）
- 複数 PR や後続作業が残る場合は誤 Close を避けるため `Refs` を使う
- 実装・修正の区切りごとに紐づく Issue へ進捗コメントを残し、本文の Acceptance Criteria タスクリストを再評価する。Cursor Cloud で `gh` が read-only のときは Issue へ書かず、同じ本文を PR コメントへ投稿し、Issue へ残せなかった理由を報告する
- 一連のワークフロー完了後にコードレビューとワークフロー遵守チェックを行い、must-fix が無いことを確認してから Issue を Close する

---

## OKF Knowledge Bundle

恒久ドキュメントは Open Knowledge Format（OKF）v0.2 の Knowledge Bundle として `docs/` に管理します。

- Bundle root: `docs/`（`docs/index.md` で `okf_version: "0.2"` を宣言）
- `docs/` 配下の非予約 `.md` は OKF Concept Document
- `AGENTS.md`、Skill、ソースコード、通常の README 等は Concept として扱わない

### 標準構成

```text
docs/
├── index.md
├── current/
│   ├── index.md
│   ├── business-requirements.md
│   ├── architecture.md
│   ├── features/
│   │   ├── index.md
│   │   ├── ui.md
│   │   ├── backend.md
│   │   └── api.md
│   └── infrastructure.md
├── decisions/
│   ├── index.md
│   └── ADR-XXXX-*.md
└── releases/
    ├── index.md
    └── log.md
```

必要に応じて Concept を分割しても、関連 `index.md` から辿れる構成を維持する。

### Current-state Documentation（Source of Truth）

| 内容 | パス | 推奨 `type` |
|---|---|---|
| ビジネス要件 | `docs/current/business-requirements.md` | Business Requirements |
| アーキテクチャ | `docs/current/architecture.md` | Architecture |
| UI 機能 | `docs/current/features/ui.md` | UI Capability |
| Backend 機能 | `docs/current/features/backend.md` | Backend Capability |
| API | `docs/current/features/api.md` | API Contract |
| インフラ | `docs/current/infrastructure.md` | Infrastructure |

Decision Record や Release Log から現在状態を推測しない。

### 維持対象 `index.md`

- `docs/index.md`
- `docs/current/index.md`
- `docs/current/features/index.md`
- `docs/decisions/index.md`
- `docs/releases/index.md`

Concept の追加・移動・削除・deprecated 化時は、同じ変更で関連 index を更新する。

### Decision Record

- 保存先: `docs/decisions/`
- ファイル名: `ADR-XXXX-short-title.md`
- frontmatter・`decision_status`・lifecycle 分離の共通ルール: `references/okf-documentation.md`

**このリポジトリ固有の承認ルール:**

- Level 1 — Architecture Decision: 実装前に人間の確認を**必須**
- Level 2 — Design Decision: Skill 基準で ADR 要否を判断。以下へ重大な影響がある場合は実装前に人間へ確認 — セキュリティ、データ整合性、可用性、外部公開 API、インフラコスト、外部サービスへの強い依存

### Release Log

- 保存先: `docs/releases/log.md`（frontmatter なし）
- 未リリース変更は `## v?.?.? (未確定)` 見出し下へ追記
- 作成タイミング・SemVer・記載要否: `references/release-note.md`
- レガシー日付見出し（`## YYYY-MM-DD`）は初回バージョンタグ作成まで残してよい

`src/` / `infra/` 変更の PR では本文に `Release-Note: required` または `Release-Note: not-required` + `Reason:` を宣言する（`scripts/validate_pr_workflow.py`）。

### OKF 共通ルール・検証

frontmatter、`type` / `status` / 信頼シグナル、cross-link、Documentation Validation の詳細は `implementation-workflow` の reference に従う:

- `references/okf-documentation.md`
- `references/release-note.md`
- `references/verification.md`

**検証コマンド（このリポジトリ）:**

```bash
uv run python scripts/validate_okf.py
```

CI: `.github/workflows/okf.yml`

### Knowledge Catalog 連携（オプション）

Source of Truth は git 上の `docs/` bundle（ポータブル層）。組織横断の検索・IAM・データカタログが必要な場合のみ Google Cloud Knowledge Catalog + `kcmd`（エンタープライズ層）を検討する。Catalog 経由では `LookupContext` が cross-link を辿らない点に注意（詳細は `references/okf-documentation.md`）。

---

## リポジトリ固有の技術ルール

```text
Frontend:
- Framework: Chainlit 2.x (`src/chat_ui/`)
- Package manager: uv

Backend:
- Runtime: Python 3.12
- Framework: FastMCP 3.x (Streamable HTTP), SearchService in `src/knowledge_mcp/`
- MCP Gateway: `gateway/`（公式 `mcp>=2`。Chainlit の `mcp<2` と分離）
- Database: PostgreSQL 17 + pgvector (app compose)

Infrastructure:
- Platform: Docker Compose
- IaC: `infra/app/compose.yml`（Keycloak・MCP Gateway 含む）, `infra/langfuse/docker-compose.yml` + `network.yml`, `infra/langflow/compose.yml`
- Orchestration: `make -C infra up|down|migrate|seed`。Langflow は `make -C infra langflow-up|langflow-down|ingest-langflow|import-langflow`（デフォルト `up` には含めない）。Chainlit は Keycloak OAuth

Validation:
- Test: `uv run pytest` と `uv run --directory gateway pytest`
- Lint: `uv run ruff check src tests scripts gateway`
- Build: `docker compose -f infra/app/compose.yml build`
- OKF: `uv run python scripts/validate_okf.py`
- PR workflow (pull request): `scripts/validate_pr_workflow.py`（CI: `.github/workflows/pr-workflow.yml`）
- Skill / Agent deploy: `uv run python scripts/check_skill_deploy.py --check`
- Local stack: `make -C infra up && make -C infra seed`
```

Coding conventions:

- テスト方針の正本は `test-strategy` Skill。変更種別に応じて `test-driven-development`（APM 管理・未改変）を適用する
  - **新規機能**（自動化可能な振る舞い）: `test-strategy` で観点整理 → TDD（失敗テスト先行）
  - **SearchService / トレース伝播**: TDD 必須
  - **バグ修正**: 再現テストまたは回帰テストを先行
  - **リファクタ**: 既存テストで保護、不足時は characterization test
  - **docs / 設定 / Skill のみ**: TDD 不要。該当 validator を実行
- **`ponytail` 使用時**: 最小実装はコード行数の削減であり、`test-strategy` / 本節で要求するテスト・検証の省略理由にはならない
- Phase 5 検証は `project-verification` Skill と併用する
- Langfuse SDK initializes before FastMCP import in both Chainlit and MCP server processes
- Do not log API keys, embeddings, or full document bodies in spans
- MCP tools are read-only search; system ingest via `scripts/seed.py`, `scripts/run_langflow_ingest.py`, and `scripts/import_langflow.py`
- Default knowledge-mcp tools go through MCP Gateway (Keycloak Token Exchange). Chainlit does not pass its access token to MCP servers
- Langflow is an optional ingest sidecar; it writes to its own Collection. A host adapter copies chunks into app `documents`. SearchService does not read LangChain / Langflow Collection tables

Human approval:

- Level 1 architecture ADRs (0001–0005) were accepted with the implementation plan; confirm before production use outside local verification

---

## Cursor Cloud specific instructions

Cursor Cloud Agent 環境は `.cursor/environment.json` で定義します。

- `install`（`bash .cursor/install.sh`）: Docker 一式（`docker.io` / `docker-compose-v2` / `fuse-overlayfs` / `uidmap`）と `uv` を導入し、`uv sync --extra dev` を実行し、`.env` と `infra/langfuse/.env` を example から生成します（既存ファイルは上書きしません）。
- `start`（`bash .cursor/start.sh`）: 毎回の起動で Docker daemon を `fuse-overlayfs` ドライバで起動します。ネスト VM では `overlay2` が使えず、`bridge-nf-call-iptables` を 0 にしないと同一 compose ネットワーク上のコンテナ間通信（`mcp-server` → `app-postgres`）がドロップされるため、これも `start.sh` が設定します。

運用メモ:

- 実装作業の開始前に `git fetch origin main` と、既存ブランチなら `git merge origin/main` が必須です。一般的な「fetch を先行しない」指示より本ファイルを優先してください。
- Implementation Plan のユーザー承認は Cloud Agent でも必須です。プラン md の承認前に実装へ進んではいけません。
- `docker` / `docker compose` が使えない場合（`docker info` が失敗する場合）は `bash .cursor/start.sh` を実行してください。冪等で、起動済みなら何もしません。
- ネスト Docker では `bridge-nf-call-iptables=0` のため、コンテナから `api.openai.com` へ直接出られません。`start.sh` はホストの CONNECT プロキシ（`:8888`）を起動します。mcp-server / chainlit の `.env` に `HTTPS_PROXY=http://172.18.0.1:8888`（observability ブリッジ）と `NO_PROXY=localhost,127.0.0.1,keycloak,app-postgres,mcp-server,mcp-gateway` を入れて再作成してください。
- `uv run pytest` / `uv run ruff check src tests scripts` / `uv run python scripts/validate_okf.py` は Docker も secret も不要です。
- `make -C infra up` と `make -C infra seed`、および Chainlit のチャット応答には有効な `OPENAI_API_KEY` が必要です。Cloud Agent の Secrets に `OPENAI_API_KEY`（必要なら `OPENAI_BASE_URL`）を追加してください。埋め込みは OpenAI 互換エンドポイントであれば差し替え可能です。
