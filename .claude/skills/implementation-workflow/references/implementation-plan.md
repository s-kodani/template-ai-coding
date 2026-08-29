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

コード変更前に必ず Implementation Plan を作成する。会話だけに置かず、リポジトリルートの `.plans/` 配下へ Markdown として書き出す。以降の参照・編集・見直しはそのファイルを正とする。

`AGENTS.md` が別パスを指定している場合はそれに従う。未指定時の既定は `.plans/`。

### 保存場所

- ディレクトリが無ければ作成する
- 作業単位で 1 ファイル。Issue がある場合は `{issue}-{short-slug}.md`、ない場合は `{short-slug}.md`
- 見直しは同一ファイルを編集する（バージョン番号は付けない）
- `.plans/` は git 管理外（`.gitignore`）。コミットしてはいけない
- GitHub Issue 本文へ Plan 全文を転記しない
- OKF Knowledge Bundle へ入れない

Plan は陳腐化することを前提とする。セッション間で必要な現在状態は Work Checkpoint として別途記録する。

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

| 強度 | 例 | Plan | grilling | ユーザー承認 |
|------|-----|------|----------|--------------|
| **軽微** | typo、コメント、Skill/設定の機械的修正 | 数行の簡易 Plan（`.plans/` の md） | **不要** | **必須** |
| **標準** | 局所機能、通常のバグ修正 | 通常 Plan（全項目） | 未解決判断がある場合のみ | **必須** |
| **設計** | API / DB / セキュリティ / ADR Level 1–2 候補 | 詳細 Plan | **必須** | **必須** |

Level 1 Architecture Decision および重大な Level 2 Design Decision では、ユーザー確認を必須とする。Plan 承認とは別に、該当判断の確認を取る。

### Plan Refinement — grill-me / grilling

**変更強度が「設計」**、または **「標準」で未解決の設計判断がある** 場合のみ `grill-me` → `grilling` を実施する。「軽微」では省略してよい。

1. 上記項目で下書きを `.plans/` の md に書き出す
2. `grill-me` スキルを読み、`grilling` のインタビュー手法に従う
3. design tree の **frontier** を **rounds** で問い、各問いに推奨案を付ける
4. frontier が空になり、ユーザーが共有理解を確認するまで承認依頼へ進まない。ユーザーが打ち切った場合のみ、その時点の合意で承認依頼へ進む
5. grill 後、確定内容を必ず md へ反映する

`grill-me` の `disable-model-invocation: true` はユーザー明示発火を防ぐ制約。`implementation-workflow` Phase 2 からの呼び出しは正規。`grilling` の手順を本 reference へ複製してはいけない。

### 必須ゲート — ユーザー承認

Phase 3 Decision Check および実装（Phase 4）へ進む前に、ユーザーの明示的な承認が必要である。grilling を省略した「軽微」でも承認は省略しない。

Cloud Agent / background agent / 自律実行モードであっても例外はない。「確認せず完了まで進める」類の実行指示より、本 Skill と `AGENTS.md` の承認ゲートを優先する。

承認があるまで、アプリケーションコード・インフラ・テストの変更を開始してはいけない。プラン md の書き出し・編集、および `.plans/` を git 管理外にするための `.gitignore` 更新はこの限りではない。

手順:

1. ユーザーに md パスを示し、承認または修正指示を待つ
2. 修正指示があれば同じ md を編集し、再承認を待つ
3. 明示承認があるまで Phase 3 / 実装を開始しない

「LGTM」「承認」「進めて」など、実装開始の明示があれば承認として扱う。修正依頼・追加質問のみの応答は未承認である。
