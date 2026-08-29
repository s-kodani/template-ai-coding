# Completion Report

Phase 7 と一時成果物ルール。

## Phase 7: Completion Report — 完了報告

実装完了時は以下を報告する。

### Changes

実際に何を実装したか。

### Verification

実行した検証と結果。実行していない検証を成功済みと報告してはいけない。

### Documentation

関連する恒久ドキュメントの更新状況。

### GitHub Issue

GitHub Issue を使用している場合は、最終コメントとして以下を残す。

- 実際に完了した Changes
- Verification 結果
- 作成・更新した ADR / OKF Concept
- Release Log（`## v?.?.? (未確定)` への追記、またはタグ確定時の見出し置換）
- 残課題がある場合はその Issue への分離状況
- 関連 PR / commit

Acceptance Criteria を満たし、必要な恒久知識への昇格が完了したことを確認してから Issue を Close する。

例:

```text
Documentation
- Business requirements: no change
- Architecture: updated
- UI/backend concepts: updated
- Infrastructure: no change
- ADR: ADR-0014 added
- Release log: updated under `## v?.?.? (未確定)`（または tag finalized to `vX.Y.Z`）
- OKF index: updated
- OKF validation: passed
```

---

## Temporary Artifact Rule — 一時成果物ルール

以下は原則コミットしない。

- Implementation Plan（`.plans/` 配下の md。git 管理外）
- Scratch Note
- 中間案
- 破棄した Design Draft
- Intermediate Reasoning
- 陳腐化した Implementation Approach

Implementation Plan は会話だけに置かず `.plans/` へ書き出すが、リポジトリへコミットしてはいけない。`AGENTS.md` が別パスを指定している場合は、そのディレクトリも git 管理外とする。

恒久的な価値がある情報だけを、Current-state Documentation、ADR、Release Note へ昇格させる。

OKF を採用していても、一時的な Implementation Plan を Knowledge Bundle へ入れてはいけない。

GitHub Issue の Checkpoint コメントは作業履歴として残して構わないが、恒久的な Architecture / Business / API knowledge の Source of Truth にはしない。最終的に残すべき知識は OKF Concept、ADR、Release Log へ昇格させる。
