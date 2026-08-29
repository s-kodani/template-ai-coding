# Implementation Plan

Phase 1（Understand）と Phase 2（Plan）の詳細。

## Phase 1: Understand — 現在状態の理解

Implementation Plan 作成前に以下を確認する。

1. `AGENTS.md` などのリポジトリ固有ルール
2. 関連ソースコード
3. 関連する Current-state Documentation
4. 関連する既存 ADR
5. アーキテクチャ上の制約とシステム境界
6. 影響を受けるモジュール、API、データ、インフラ、外部連携
7. 既存のテスト・検証手段
8. OKF を採用している場合は、Knowledge Bundle の `index.md` と関連 Concept の cross-link

### OKF での探索順序

1. Bundle root の `index.md`
2. 関連ディレクトリの `index.md`
3. 関連 Concept Document
4. Concept からリンクされた関連 Concept
5. 必要な場合のみ Decision Record や Release Log

全ドキュメントを無条件に読み込まない。`index.md` による Progressive Disclosure を優先する。

git bundle では Concept 本文の cross-link を辿れる。Knowledge Catalog 経由では `LookupContext` がリンクを辿らないため、参照先 Concept を明示的に指定する。

ADR は判断理由の履歴であり、現在状態は Current-state Documentation を優先する。

---

## Phase 2: Implementation Plan — 実装計画の作成

コード変更前に必ず Implementation Plan を作成する。会話または一時作業コンテキストに置き、明示的な依頼がない限りファイル化・コミットしない。

GitHub Issue を使用していても、Plan 全文を Issue 本文へ転記しない。

### 必須項目

| 項目 | 内容 |
|------|------|
| Goal | 何を実現するか |
| Current State | 既存実装・ドキュメント・ADR から判明したこと |
| Scope | 影響する機能、モジュール、API、データ、インフラ、外部連携、ドキュメント |
| Implementation Approach | 主要な変更方針、順序、互換性、移行方針 |
| Files / Components | 主な変更対象 |
| Decision Candidates | ADR が必要になりうる設計判断 |
| Documentation Impact | 更新が必要になりうる OKF Concept、`index.md`、ADR、Release Log |
| Risks / Open Questions | 技術的不確実性、互換性、セキュリティ、性能、運用リスク |
| Verification | Test、Lint、Build、Migration、手動確認など |

Phase 5 では `project-verification` Skill を読み、変更種別に応じた検証コマンドを実行する。

### Change Intensity — 変更強度

| 強度 | 例 | Plan | grilling |
|------|-----|------|----------|
| **軽微** | typo、コメント、Skill/設定の機械的修正 | 数行の簡易 Plan | **不要** |
| **標準** | 局所機能、通常のバグ修正 | 通常 Plan（全項目） | 未解決判断がある場合のみ |
| **設計** | API / DB / セキュリティ / ADR Level 1–2 候補 | 詳細 Plan | **必須** |

Level 1 Architecture Decision および重大な Level 2 Design Decision では、ユーザー確認を必須とする。

### Plan Refinement — grill-me / grilling

**変更強度が「設計」**、または **「標準」で未解決の設計判断がある** 場合のみ `grill-me` → `grilling` を実施する。「軽微」では省略してよい。

1. Plan 下書きを作成する
2. `grill-me` スキルを読み、`grilling` のインタビュー手法に従う
3. design tree の **frontier** を **rounds** で問い、各問いに推奨案を付ける
4. frontier が空になり、ユーザーが共有理解を確認するまで Phase 3 / 実装へ進まない
5. grill 後、Plan を更新する

`grill-me` の `disable-model-invocation: true` はユーザー明示発火を防ぐ制約。`implementation-workflow` Phase 2 からの呼び出しは正規。`grilling` の手順を本 reference へ複製してはいけない。
