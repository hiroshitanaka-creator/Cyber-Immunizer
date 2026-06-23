# タスク完了報告 — 整合性ゲート是正＋M1 オフライン自己進化ループ＋SSOT 同期

## 概要
理念（自律的に自己進化し続けるデジタル免疫システム）の本線へ向け、自律ループが信頼できるための
**整合性ゲート（Codex P2 4件）を是正**し、**M1 のオフライン自己進化サイクル**（propose→evaluate→promote
を API 無しで end-to-end）を実証・回帰テスト化した。あわせて main に残っていた **SSOT ズレ（ledger 15
件 vs project_state 14件）を同期**した。Owner 承認タスク（public）。本番 `detector_mode` は legacy のまま。
**3012 passed / validate_state PASS。API・live設定変更・workflow_dispatch なし。**

## 整合性ゲート（Codex P2 4件）
1. **false-green 封じ**（`scripts/evaluate_structured_rules_candidate.py`）：外部コーパスは
   attack に `expected_blocked=true` が1件以上・benign に `expected_blocked=false` が1件以上・
   regression が1件以上を要求（positive-label ベース）。kind だけの存在判定を廃止。
2. **自己昇格が canonical を壊さない**（`scripts/promote_structured_candidate.py`、案1 decouple）：
   `generation`/`best_score`/`current_detector_hash` を不変のまま、
   `detector_mode` と `active_structured_rules_{path,hash,score,promoted_at}` を記録。
   `evolution_history` への generation 追記を廃止。即ロールバック（`detector_mode=legacy`）維持。
3. **証拠の再現性**：`fixtures/realistic_corpus/all_cases.json`（6 tier 連結）をコミット。
   `cli.structured_eval --corpus .../all_cases.json` で再現可能に。整合テスト追加。
4. **誤検知除去**（`fixtures/structured_rules/realistic_baseline.json`）：広すぎる裸 `&&` を
   `&& cat `/`&& rm ` に限定。`counterfactual_requests.json` に無害な `A && B` を追加。
   検知は 100%/0% 維持（TN 16→17）。

## M1 — オフライン自己進化サイクル（API 不要の本線実証）
`tests/test_evolution_cycle_offline.py`：propose(`--structured-rules --offline-sample`)→
evaluate(adoption gate)→promote(decoupled) を end-to-end で実行し、稼働検出器が structured へ
切替・レガシー系統不変を確認。live 版は step1 を `--gemini-paid-credit` に差し替えるだけ
（Owner ゲート＋`.github` 配線は次段）。

## SSOT 同期（14→15）
2026-06-23T10:44 の 15件目 primary-model paid 成功（Owner 実行）を反映：
`data/project_state.json`（count＋run_15_triage＋note）、`docs/PROJECT_STATE.md`、
sync テスト（`_EXPECTED...=15`、doc-shows-15）を更新。機械証拠＝ledger 優先。

## 変更ファイル
- scripts: `evaluate_structured_rules_candidate.py` / `promote_structured_candidate.py`
- fixtures: `structured_rules/realistic_baseline.json` / `realistic_corpus/counterfactual_requests.json` /
  `realistic_corpus/all_cases.json`(新)
- data/docs SSOT: `data/project_state.json` / `docs/PROJECT_STATE.md` /
  `docs/value_validation/REALISTIC_DETECTION_RESULTS.md`
- tests: `test_evaluate_structured_rules_candidate.py` / `test_promote_structured_candidate.py` /
  `test_realistic_ruleset.py` / `test_project_state_sync.py` / `test_evolution_cycle_offline.py`(新)
- 本報告

## 後検証
- `python -m pytest tests/ -q` → **3012 passed**
- `python scripts/validate_state.py` → PASS
- `cli.structured_eval`（all_cases.json）→ tp_rate 1.0 / fp_rate 0.0

## Which layer did this task advance?
- [x] Layer 1（自律ループの整合性堅牢化＋M1 オフライン経路の実証）
- 一部 Current-State SSOT 同期（14→15）

## 残存（次段・Owner ゲート）
- M1 の live 配線（`.github/workflows/immunization_loop.yml` に structured モード追加、FROZEN・Owner 承認）
- live paid 自己進化の実走（Owner 点火、≤10回/時）
- 本番 `detector_mode` の structured 切替（`docs/PRODUCTION_DETECTOR_FLIP_DESIGN.md` 案1）
