# Cyber-Immunizer Offline-Sample Dry-run / Promote Separation Design

> **このドキュメントは Phase 2-D の設計・仕様文書です。**
> Phase 2-D は design-only です。実装コード・workflow変更・API接続は行いません。

---

## Purpose

- offline-sample を CI smoke test / dry-run / evaluation 用経路として安全に扱う
- offline-sample の成功を、そのまま promote 承認と誤認しない
- dry-run artifact と promote-eligible artifact を明確に分離する
- Phase 2-D では設計・仕様・監査テストのみを追加し、実装は行わない

---

## Problem statement

以下のリスクを本設計で明記し、防止する。

- offline-sample が成功しただけで promote 可能と誤解される
- CI smoke test の candidate artifact が promote artifact と混同される
- read-only CI と write権限 promote job が混同される
- offline-sample patch が Human Owner 承認なしに昇格される
- dry-run result が adoption gate / promote gate を通過したものとして扱われる

---

## Definitions

### offline-sample

リポジトリ内に固定された検証用サンプルパッチ。
APIキー不要。
Gemini APIを呼ばない。
CI smoke test / local dry-run / boundary verification 用。

**offline-sampleの成功はpromote承認ではない。**

### dry-run

候補生成・apply・evaluateまでは行うが、以下を行わない実行。

- core/detector.py の上書き
- data/genome.json の更新
- data/evolution_history.json への昇格記録
- git commit
- git push
- promote_candidate.py の実行
- write権限jobでのgenerated code実行

dry-run はデフォルトで non-promotable である。
dry-run artifact は promote artifact ではない。

### promote

Human Owner承認後に、検証済みcandidateを正式な世代として昇格する操作。
promoteはdry-runとは別経路であり、明示的な承認・検証・監査記録が必要。

promoteには Human Owner approval が必要である。
promoteには GPT Audit Gate APPROVE が必要である。

---

## Separation model

以下の3経路を明確に分ける。

### 1. CI smoke path

目的:
- repositoryの基礎健全性確認
- offline-sample patchのapply/evaluate境界確認
- AST policy / fitness / soft-reject動作確認

制約:
- read-only（contents: write なし）
- GEMINI_API_KEY なし（CIにはGEMINI_API_KEYを渡さない）
- live_model_enabled=true にしない
- promote_candidate.py 実行なし
- git push なし
- data/genome.json 更新なし
- data/evolution_history.json 更新なし
- data/api_usage_ledger.json 変更なし

**CI smoke testはpromoteを実行しない。**
**CI smoke artifactをpromoteに使おうとした場合はBLOCKする。**

### 2. Dry-run evaluation path

目的:
- candidateの評価
- adoption gate / regression / AST policy の事前確認
- Human OwnerがPromote判断するための材料を作る

制約:
- dry-run artifact は non-promotable by default
- dry-run result をそのまま昇格証拠として扱わない
- promoteには別途 Human Owner approval が必要
- dry-run artifact には `promote_eligible=false` 相当の扱いを想定する

**dry-run artifactはpromote artifactではない。**
**dry-runはデフォルトでnon-promotableである。**

### 3. Promote path

目的:
- Human Owner承認済みcandidateのみを正式昇格する

制約:
- explicit approval required（Human Owner approval 必須）
- GPT Audit Gate APPROVE 必須
- promote前にAST policy / fitness / regressionを再確認する
- promote artifact はdry-run artifactと区別する
- write権限jobでは未検証generated codeを実行しない（generated codeはwrite権限jobで実行しない）
- data/api_usage_ledger.json はpromote対象に含めない
- promote後は evolution_history に監査記録を残す

---

## Safety invariants

以下の安全境界は Phase 2-D でも Phase 3 以降でも維持する。

- offline-sampleの成功はpromote承認ではない
- CI smoke testはpromoteを実行しない
- dry-run artifactはpromote artifactではない
- dry-runはデフォルトでnon-promotableである
- promoteにはHuman Owner承認が必要である
- promoteにはGPT Audit Gate APPROVEが必要である
- generated codeをwrite権限jobで実行しない
- GEMINI_API_KEYをCIに渡さない
- live_model_enabled=trueにしない（Phase 2-D中は維持）
- data/api_usage_ledger.jsonを変更しない
- data/evolution_history.jsonへの昇格記録はpromote pathのみ
- all-block / all-allow / regression failure / AST policy failure はpromote不可
- 不明・欠損・曖昧なartifactはfail-closed

---

## Future CLI / workflow design

将来実装する場合の設計案を記載する。
**Phase 2-Dでは実装しない。workflow変更は行わない。**

### 現行コマンド（変更しない）

```bash
python scripts/propose_mutation.py --offline-sample --json
python scripts/apply_mutation.py --patch .cyber_immunizer/mutation_patch.json --base core/detector.py --out .cyber_immunizer/candidate_detector.py --json
python scripts/evaluate_candidate.py --candidate .cyber_immunizer/candidate_detector.py --json --soft-reject
```

### 将来案（Phase 2-D では未実装）

```bash
# dry-run promote eligibility確認（non-promotable, Human Owner確認用）
python scripts/mark_promote_candidate.py --candidate-report .cyber_immunizer/evaluation_report.json --dry-run

# promote eligibility付与（Human Owner approval必須）
python scripts/mark_promote_candidate.py --candidate-report .cyber_immunizer/evaluation_report.json --apply --human-owner-approved
```

設計方針（将来実装時の参考）:
- dry-run default（デフォルトはnon-promotable）
- promote eligibilityは明示的に付与する
- promote eligibility付与にはHuman Owner approvalが必要
- CIではpromote eligibilityを付与しない
- workflow変更はPhase 2-Dでは行わない

---

## Required future audit fields

将来artifactやhistoryに記録すべき項目として以下を記載する。
Phase 2-D では未実装。

- source_mode: offline-sample / live-model / rollback / backtrack
- execution_path: ci-smoke / dry-run / promote
- promote_eligible: true / false
- human_owner_approval: 承認者・日時
- audit_gate_decision: APPROVE / REQUEST CHANGES / BLOCK
- ast_policy_ok: true / false
- regression_passed: true / false
- passed_adoption_gate: true / false
- candidate_hash: candidateのSHA-256等
- detector_hash: 現行detector hashとの対比
- created_from_commit: どのcommitから生成されたか
- artifact_type: dry-run / promote-candidate
- timestamp: ISO 8601形式

---

## Failure handling

以下の場合はpromote不可（fail-closed）。

- promote_eligible がないartifactはpromote不可
- promote_eligible=false のartifactはpromote不可
- Human Owner承認がないartifactはpromote不可
- audit_gate_decision が APPROVE でないartifactはpromote不可
- artifact schema不明・欠損・破損はfail-closed
- CI smoke artifactをpromoteに使おうとした場合はBLOCK

---

## Non-goals

Phase 2-Dでは以下を実施しない。

- workflow変更（.github/workflows は変更しない）
- promote_candidate.py変更
- propose_mutation.py変更
- apply_mutation.py変更
- evaluate_candidate.py変更
- rollback/backtrack実装
- API接続
- Gemini API呼び出し
- live_model_enabled=true への変更
- GEMINI_API_KEY使用
- generated codeのwrite権限job実行
- 自動promote
- 自動commit / git push
- data/api_usage_ledger.json の変更
- data/genome.json の変更
- data/evolution_history.json の変更

---

*このドキュメントは Project Cyber-Immunizer の Phase 2-D 設計文書です。*
*Phase 2-D: design-only — 実装・workflow変更・API接続は行いません。*
*作成日: 2026-05-26*
