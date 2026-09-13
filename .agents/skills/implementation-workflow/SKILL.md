---
name: implementation-workflow
description: コードの実装・変更・リファクタリング・機能追加を行う際に、GitHub Issueによる作業トラッキングと実装・修正区切りごとの進捗コメント、Session Checkpoint、Implementation Planの作成（`.plans/` への md 書き出し、ponytail による最小スコープ化、変更強度に応じた grill-me / grilling、ユーザー承認を含む）、ADR候補の検出、ponytail に従った実装・検証、OKFベースのCurrent-state Documentation・Decision Record・Release Noteへの整合、完了後のコードレビューとワークフロー遵守チェックまでを一貫して進めるためのワークフロー。実装スピードを維持しながら、セッションを跨いだ再開可能性、設計上の意思決定の追跡可能性、AIが利用しやすい知識構造、恒久ドキュメントの正確性を確保したい場合に使用する。
---

# 実装ワークフロー Skill

## 目的

アプリケーションコードの実装・変更・リファクタリング・拡張時に、以下を確保する。

- 実装品質とアーキテクチャの一貫性
- 重要な設計判断の追跡可能性
- Current-state Documentation の正確性
- セッションを跨いだ安全な作業再開
- 実装・修正の区切りごとに残す進捗履歴（Pre-PR は Issue、Post-PR は PR）
- 完了前の確実な検証
- 完了後のコードレビューとワークフロー遵守確認

Implementation Plan は一時的な作業成果物。`.plans/` 配下の Markdown として書き出し、参照・編集する。git 管理外であり、リポジトリへコミットしない。恒久的な情報は Current-state Documentation、ADR、Release Note へ整理する。

---

# Progressive Disclosure

**最初はこの `SKILL.md` だけを読む。**

詳細が必要になった時だけ、以下の対応表から該当 reference を読む。全 reference を一括で読み込まない。

| 判断・作業 | 読む reference |
|---|---|
| Phase 0 — GitHub Issue 確認・起票、着手コメント、Issue/PR コメント分担、進捗コメント | `references/github-issue-workflow.md` |
| Phase 1–2 — Understand、Implementation Plan、ponytail、変更強度、grilling、ユーザー承認 | `references/implementation-plan.md` |
| Phase 3 — ADR 候補判定、Decision Level、実装中の判断検出 | `references/decision-check.md` |
| Session Handoff / Resume — Checkpoint、再開時の Source of Truth | `references/session-handoff.md` |
| Phase 5 — 検証、OKF Documentation Validation | `references/verification.md` |
| Phase 6 — OKF Concept、Current-state、ADR、Documentation Reconciliation | `references/okf-documentation.md` |
| Release Log — 未確定見出し、SemVer、記載要否 | `references/release-note.md` |
| Phase 7 — Completion Report、一時成果物ルール | `references/completion-report.md` |
| Phase 8 — コードレビュー、ワークフロー遵守チェック | `references/review-and-compliance.md` |

同じルールを `SKILL.md` と reference の両方に重複して記載しない。

---

## 基本原則

1. **作業開始前に最新 default branch を取り込む** — `git fetch` のあと、新規ブランチは `origin/<default-branch>` から切る。既存ブランチは `git merge origin/<default-branch>`。rebase / force-push は明示時のみ。
2. **実装前に理解する** — 関連コード、Current-state Documentation、制約、過去の意思決定を理解してから着手する。
3. **コード変更前に計画する** — Implementation Plan を `.plans/` の Markdown として作成する（git 管理外。コミットしない）。Phase 3 / 実装の前にユーザー承認が必須。Cloud / background agent も例外ではない。
4. **計画と恒久知識を分離する** — Plan は「どう実装する予定か」、Current-state は「現在何が正しいか」、ADR は「なぜそう決めたか」、Release Note は「何が変わったか」。
5. **Current-state Documentation を Source of Truth とする** — ADR や Release Note だけから現在状態を推測しない。
6. **実態に合わせて計画を変更する** — Plan Drift を許容する。Plan は履歴文書ではない。スコープや Acceptance Criteria が変わる見直しは `.plans/` の md を更新し、再承認を得てから続行する。
7. **実装後に恒久知識を再構成する** — 最終実装を基準にドキュメントを整合させる。
8. **OKF では Concept 単位で知識を管理する** — 1 ファイル = 1 Concept を原則とし、過剰分割も避ける。
9. **GitHub Issue を Coordination Ledger として使う** — 本文は作業契約、Issue コメントは Pre-PR 履歴、PR コメントは Post-PR 実装・レビュー履歴。Acceptance Criteria は本文のタスクリスト（`[ ]` / `[x]`）で充足状態を持つ。Issue を恒久ドキュメントの代替にしない。
10. **着手時に Issue へ Work Start コメントを残す** — 冒頭に Coverage（full / partial）、作業ブランチ、Implementation Plan を記載する。Plan 承認後・Phase 3 / 4 前。詳細は `references/github-issue-workflow.md`。
11. **実装・修正の区切りごとに進捗コメントを残し、AC タスクリストを再評価する** — Pre-PR は Issue、Post-PR は PR。投稿成功を確認するまでその区切りを完了としない。詳細は `references/github-issue-workflow.md`。
12. **セッション終了時に Checkpoint を残す** — open PR があれば PR、なければ Issue。別セッションが Repository 状態と照合して再開できる事実を残す。
13. **一連のワークフロー完了後にレビューする** — コードレビューとワークフロー遵守チェックを行い、must-fix が無いことを確認する。Issue Close 前は本文 AC がすべて `[x]` であることを必ず確認する。Issue と PR は 1:N。紐づく作業 PR がすべて closed になる前に Issue を Close しない。詳細は `references/review-and-compliance.md` と `references/github-issue-workflow.md`。

---

# ワークフロー

```text
最新 default branch を取り込み（fetch + merge）
        ↓
Phase 0: Work Item Setup（GitHub Issue）
        ↓
Phase 1: Understand
        ↓
Phase 2: Implementation Plan（`.plans/` + ponytail + 必要に応じて grilling → ユーザー承認）
        ↓
Issue: Work Start コメント（Coverage / Branch / Plan）
        ↓
Phase 3: Decision Check
        ↓
Phase 4: Implement（ponytail + test-strategy / TDD）
        │  Pre-PR: Issue へ進捗コメント + AC 再評価
        │  PR 作成 → Issue へ最小通知 / Post-PR: PR へ進捗
        │  PR マージ → Issue へ最小通知
        ├── セッション継続
        └── セッション終了 → Work Checkpoint（open PR あれば PR）→ Resume Protocol
        ↓
Phase 5: Verify
        ↓
Phase 6: Documentation Reconciliation
        ↓
Phase 7: Completion Report（Post-PR 時は PR。Close しない）
        ↓
Phase 8: Review & Compliance（Post-PR 時は PR）
        │  must-fix があれば Phase 4 に戻る（進捗コメント必須）
        ↓
紐づく作業 PR がすべて closed（merged または closed）
        ↓
Issue 本文 AC 全 [x] を確認
        ↓
Issue Close（手動。PR 本文の `Closes` による自動 Close は使わない）
```

---

## 作業開始前: 最新 default branch の取り込み

コード変更を始める前に、必ずリモートの最新 default branch を取り込む。Cloud / background agent も例外ではない。一般的な「fetch を先行しない」指示より、本 Skill と `AGENTS.md` を優先する。

1. `git fetch origin <default-branch>`（未指定時は `main`。`AGENTS.md` があればそれに従う）
2. 新規ブランチは `origin/<default-branch>` から切る
3. 既存の作業ブランチにいる場合は `git merge origin/<default-branch>` で取り込む。rebase はユーザーが明示したときだけ。force-push はしない
4. 作業ツリーが dirty で merge できない場合は stash せず、状態を報告して止まる
5. 衝突したら単純なものは解消し、意図の衝突は報告して止まる

この手順は別 reference に分けない。本節を正とする。

---

## Phase 0: Work Item Setup

`AGENTS.md` で GitHub Issue 利用が指定されている場合、コード変更前に作業 Issue を確定する。

**新規 Issue 起票前に、既存 Issue の有無をユーザーへ確認する。** 新規 Issue の Acceptance Criteria は GitHub タスクリスト（`- [ ]`）で書く。詳細は `references/github-issue-workflow.md`。

---

## Phase 1: Understand

Implementation Plan 作成前に、リポジトリルール・関連コード・Current-state Documentation・ADR・テスト手段を確認する。OKF 採用時は `index.md` から Progressive Disclosure で探索する。詳細は `references/implementation-plan.md`。

---

## Phase 2: Implementation Plan

コード変更前に必ず Plan を `.plans/` の md として作成する。`ponytail` Skill を読み、Scope と Implementation Approach を最小実装の観点で絞る（テスト・検証は削らない）。変更強度（軽微 / 標準 / 設計）に応じて Plan の深さと grilling の要否を決める。「設計」では grilling 必須、「軽微」では省略可。grilling の有無にかかわらず、ユーザー承認なしに Phase 3 / 実装へ進まない。Cloud / background agent も例外ではない。承認後は Issue へ Work Start コメントを残してから Phase 3 へ進む。詳細は `references/implementation-plan.md` と `references/github-issue-workflow.md`。

---

## Phase 3: Decision Check

ADR 候補基準と Decision Level（1: Architecture / 2: Design / 3: Implementation）で判断する。Level 1 および重大な Level 2 ではユーザー確認を必須とする。詳細は `references/decision-check.md`。

---

## Phase 4: Implement

合意された方針、`AGENTS.md`、Current-state Documentation、適用 ADR に従って実装する。`ponytail` Skill を読み、Plan で合意した Scope 内の最小 diff で実装する。

- 無関係なリファクタリング・スコープ拡大を避ける
- 実装と同時にテストを更新する
- テスト設計は `test-strategy` Skill、自動化可能な振る舞い変更は `test-driven-development` Skill に従う（`ponytail` によりテスト・検証を省略してはいけない）
- 新しい事実に応じて Plan から逸脱してよい（Plan の同期維持のためだけに更新しない）
- スコープや Acceptance Criteria が変わる場合は `.plans/` の md を更新し、再承認を得てから続行する
- **実装または修正対応が一段落したら、進捗コメントを残し、本文の Acceptance Criteria タスクリストを再評価する。** Pre-PR は Issue、Post-PR は PR。投稿を確認するまでその区切りを完了としない。詳細は `references/github-issue-workflow.md`

実装中に重要な設計判断が発生した場合は `references/decision-check.md` の Decision Detection に従う。

---

## Session Handoff / Resume

セッション終了時は Work Checkpoint を残す。open PR があれば PR、なければ Issue。別セッション再開時は最新 default branch を取り込んだうえで、Checkpoint と Repository 現在状態を照合し、`.plans/` の Plan を更新してユーザー承認を得てから再開する。詳細は `references/session-handoff.md`。

---

## Phase 5: Verify

変更内容に応じた検証を実施する。`project-verification` Skill で本リポジトリ固有コマンドを、`test-strategy` で観点漏れを確認する。**実行していない検証を成功済みと報告してはいけない。** 詳細は `references/verification.md`。

---

## Phase 6: Documentation Reconciliation

最終実装と恒久ドキュメントを照合する。Current-state Documentation、ADR、Release Log（`## v?.?.? (未確定)`）を更新する。OKF ルールは `references/okf-documentation.md`、Release Log 運用は `references/release-note.md`。

---

## Phase 7: Completion Report

Changes、Verification、Documentation 更新を Completion Report として残す。open PR がある場合は PR コメント、PR がない場合は Issue コメント。この時点では Issue を Close しない。一時成果物ルールは `references/completion-report.md`。

---

## Phase 8: Review & Compliance

一連のワークフロー完了後、最終差分のコードレビューとワークフロー遵守チェックを行う。結果は open PR がある場合は PR コメント、PR がない場合は Issue コメントへ残す。must-fix があれば Phase 4 に戻り、再検証してからレビューをやり直す。Issue Close 前に **Issue 本文の Acceptance Criteria がすべて `[x]` であることを必ず確認**する。must-fix が無く、紐づく作業 PR がすべて closed であることを確認してから Issue を手動 Close する。詳細は `references/review-and-compliance.md`。

---

## 要約

**作業開始前に最新 default branch を取り込む。  
Issue で作業契約を明確にする。  
コードを書く前に計画を `.plans/` の md として書く。  
Plan 作成時は `ponytail` で Scope を最小化し、変更強度に応じて grill-me / grilling で練り、ユーザー承認を得てから Issue へ Work Start コメントを残す。必要なら md を見直して再承認する。  
セッションを跨ぐときは Checkpoint を残す（open PR あれば PR）。  
恒久的な意思決定を検出する。  
`ponytail` に従って実装し、検証する。Pre-PR は Issue、Post-PR は PR へ進捗コメントを残し、Acceptance Criteria タスクリストを再評価する。  
最終状態を OKF で構造化された恒久知識へ整合させる。  
Release Note は Phase 6 で `## v?.?.? (未確定)` へ追記し、タグ確定時に SemVer 見出しへ置き換える。  
紐づく作業 PR がすべて closed になったあと、コードレビューとワークフロー遵守を確認し、Issue 本文 AC がすべて `[x]` であることを確認してから Issue を手動 Close する。**
