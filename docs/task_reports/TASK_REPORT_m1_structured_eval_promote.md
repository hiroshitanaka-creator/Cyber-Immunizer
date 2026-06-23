# タスク完了報告 — M1 完成：CI 内 structured evaluate/promote ジョブ

## 概要
自律ループ（理念の本線）の CI 配線を完成させた。`.github/workflows/immunization_loop.yml` に
**structured-evaluate** と **structured-promote** の2ジョブを追加し、「LLM が構造化防御を提案 →
CI で評価 → Owner 承認時に本番昇格」を CI 内で完結できるようにした。**自動起動の挙動は不変**
（scheduled は noop、paid/promote は手動 dispatch オプトイン）。本タスクで API・live 実行・
workflow_dispatch 起動は行わない。

## 追加ジョブ
- **structured-evaluate**（needs: propose、`structured_rules_exists=='true'` で起動）
  - `evaluate_structured_rules_candidate.py --rules <artifact> --corpus-dir fixtures/realistic_corpus --soft-reject`
  - **読み取り専用・鍵なし・Docker 不要**（候補はコード実行でなく検証済みデータ＝固定評価器で解釈）
  - `passed_adoption_gate` を出力（promote の gating に使用）、fitness レポートを artifact 化
- **structured-promote**（needs: propose, persist-ledger, structured-evaluate）
  - 起動条件：**main 限定 ＋ `promote_approved=='true'`（Owner ゲート）＋ structured-evaluate 合格 ＋ propose 非失敗 ＋ ledger 整合**
  - `promote_structured_candidate.py --owner-approved`（自己再評価）→ `data/genome.json`（detector_mode を structured へ＋active_structured_rules_*）と `data/active_structured_rules.json` を main にコミット
  - **書込権限・鍵なし**（既存 promote と同じ最小権限分離）。main-drift チェック踏襲

## baseline 制御
dispatch 入力 `structured_baseline`（既定 false）を追加。**初回の構造化昇格**（genome がまだ legacy で
active structured 基準が無い）では true を指定して baseline モードで活性化。以降は false で
active structured 基準に対する改善ゲート（先のコミットで実装済みの `_active_structured_baseline`）が効く。

## 安全性（既存ガード踏襲）
- GEMINI_API_KEY は propose ジョブの paid ステップのみ。structured-evaluate / structured-promote には無し。
- structured-promote は main 限定＋Owner 明示承認が無ければ起動しない（本番 detector_mode は勝手に変わらない）。
- 構造化候補は raw-Python 経路（patch_exists）と排他。Docker 隔離は構造化では不要（データ評価）。

## 変更ファイル
- `.github/workflows/immunization_loop.yml`（propose 出力に `structured_rules_exists`、aggregate 検出、
  `structured_baseline` 入力、structured-evaluate / structured-promote 2ジョブ）
- `tests/test_workflow.py`（新ジョブの存在・gating・鍵スコープ検証 4件）
- `tests/test_repo_invariants.py`（contents:write 許可ジョブに structured-promote を追加）
- 本報告

## 後検証
- YAML 妥当。`pytest tests/test_workflow.py tests/test_ci_workflow.py tests/test_preflight_workflow.py tests/test_preflight_mode.py` green。
- `pytest tests/ -q` → **3023 passed**。`validate_state.py` → PASS。

## Which layer did this task advance?
- [x] Layer 1（自律ループの CI 完成：propose→evaluate→promote を構造化経路で一気通貫に）

## 残存（Owner ゲート）
- Owner が `mode=structured-gemini-paid-credit` ＋（初回）`structured_baseline=true` ＋ `promote_approved=true` で
  手動起動すると、**人間が書いていない構造化防御が CI で生成→評価→本番昇格**する（≤10回/時・無料枠）。
- 以降は `structured_baseline=false` で連続自己改善（M2 へ）。
