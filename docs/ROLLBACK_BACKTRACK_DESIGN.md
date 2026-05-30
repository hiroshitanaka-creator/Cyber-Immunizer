<!--
AI_DOC_META
status: HISTORICAL
scope: rollback and backtrack design background.
use_for:
  - understanding rollback/backtrack concepts
  - checking design intent for future recovery mechanisms
  - reviewing whether future recovery work matches the original design
do_not_use_for:
  - claiming rollback/backtrack automation is implemented
  - changing promote behavior without a dedicated implementation PR
related:
  - docs/EVOLUTION_HISTORY_AUDIT.md
  - docs/PHASE_2_PLAN.md
last_reviewed: 2026-05-30
AI_DOC_META_END
-->
# Cyber-Immunizer Rollback / Backtrack Design

> **このドキュメントは Phase 2-B の設計文書です。**  
> 実装コード・workflow・API設定には触れません。  
> rollback / backtrack の自動化は Phase 2 では実装しません（design-only）。

---

## Purpose

- `core/detector.py` の退化・誤昇格・fitness低下・regression破壊に備える
- API未接続の Phase 2 で、将来実装前に安全境界を固定する
- Human Owner の承認なく過去世代へ戻ることを防ぐ設計を定義する

---

## Definitions

### Rollback

直近または指定世代の昇格を取り消し、過去世代へ戻す操作。

例: 世代3の昇格後にregressionが失敗した場合、世代2へ戻す。

### Backtrack

複数世代にわたる停滞・退化・adoption failureが続いた場合に、過去最高世代へ戻る操作。

例: 世代3〜6でbest_scoreが更新されず、世代2が歴代最高の場合、世代2へ戻す。

---

## Files in scope

rollback / backtrack の対象になり得るファイル:

- `core/detector.py`
- `data/genome.json`
- `data/evolution_history.json`

---

## Files out of scope

絶対に巻き戻してはいけないもの:

- `data/api_usage_ledger.json`
- `docs/AUDIT_CHARTER.md`
- `.github/workflows/*`
- GitHub Secrets
- billing / API key / external account state

特に `data/api_usage_ledger.json` は、実API利用の監査証跡であるため、rollback/backtrackで巻き戻してはならない。

---

## Rollback trigger conditions

以下を候補として記載する。実装時はこのリストを起点に Human Owner が判断する。

- promote後にregressionが失敗した
- false positive が急増した
- all-block detector化した（全リクエストをブロックする状態）
- all-allow detector化した（全リクエストを許可する状態）
- detector hash が期待値と一致しない
- Human Owner が明示的にrollbackを要求した
- GPT Audit Gate がBLOCKを出した

---

## Backtrack trigger conditions

以下を候補として記載する。実装時はこのリストを起点に Human Owner が判断する。

- N世代連続でbest_scoreが更新されない
- fitness scoreが連続低下した
- regression維持に失敗した
- adoption gateの連続失敗
- 新規適応により過去の防御性能が退化した
- Human Ownerが明示的にbacktrackを要求した

---

## Safety invariants

rollback / backtrack 実装時に必ず遵守すること:

- generated codeをwrite権限jobで実行しない
- rollback候補もAST policyを通す
- rollback後もfitness/regressionを再実行する
- rollback/backtrackはdry-runをデフォルトにする
- API usage ledgerは巻き戻さない
- rollback/backtrackはHuman Owner承認なしにcommitしない
- promote jobが未検証artifactを信用してはならない
- rollback対象のdetector hashを検証する
- rollback後のdetector hashを記録する

---

## Future CLI design

将来実装する場合のCLI案を記載する。**Phase 2-B では実装しない。**

```bash
# 指定世代へdry-run（デフォルト）
python scripts/rollback_generation.py --to-generation 2 --dry-run

# 過去最高世代へdry-run
python scripts/rollback_generation.py --to-best --dry-run

# Human Owner承認後の実適用（--dry-runなし）
python scripts/rollback_generation.py --to-generation 2 --apply
```

設計方針:

- デフォルトは必ずdry-run
- `--apply` はHuman Owner承認後のみ
- `--apply`時も事前にAST policy / fitness / regressionを通す
- API usage ledgerは変更しない
- 実装時はGPT Audit Gateレビュー必須

---

## Required audit log fields

rollback/backtrack実行時に将来記録すべき項目:

- `action_type`: rollback / backtrack
- `rollback_reason`
- `from_generation`
- `to_generation`
- `previous_detector_hash`
- `restored_detector_hash`
- `previous_best_score`
- `restored_best_score`
- `fitness_before`
- `fitness_after`
- `regression_result`
- `human_owner_approval`
- `audit_gate_decision`
- `timestamp`
- `commit_sha`

---

## Non-goals

以下はこのPhase 2-Bでは実装しない（design-only）。

- rollback CLI実装（`scripts/rollback_generation.py` は作成しない）
- workflow変更
- automatic rollback（自動rollback）
- automatic backtrack（自動backtrack）
- API実行
- Gemini呼び出し
- `live_model_enabled=true`
- `data/api_usage_ledger.json` の修正
- promoteロジック変更

---

## Related documents

- [`docs/PHASE_2_PLAN.md`](./PHASE_2_PLAN.md) — Phase 2 計画文書（rollback/backtrack設計文書化は Phase 2-B タスク）
- [`docs/PHASE_1_BASELINE.md`](./PHASE_1_BASELINE.md) — Phase 1 完了状態の固定記録
- [`docs/AUDIT_CHARTER.md`](./AUDIT_CHARTER.md) — GPT Audit Gate 憲章
- [`data/evolution_history.json`](../data/evolution_history.json) — 進化履歴（rollback時の参照元）
- [`data/genome.json`](../data/genome.json) — ゲノム設定（世代・スコア管理）

---

*このドキュメントは Project Cyber-Immunizer の Phase 2-B rollback/backtrack 設計を記録します。*  
*作成日: 2026-05-26*  
*ステータス: design-only（実装なし）*
