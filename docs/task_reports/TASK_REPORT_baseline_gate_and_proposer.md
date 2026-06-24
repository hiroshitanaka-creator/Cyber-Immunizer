# タスク完了報告 — 実点火triage後：baseline adoption floor の現実化 ＋ proposer 強化

## 概要
初回 ignition（runs #71-74）で、自律ループは設計どおり完走したが、構造化候補が3回連続で
adoption gate に落ち circuit breaker が trip した。原因は「未知ティア（holdout/drift）に
**100%** を要求する floor」が、現行 legacy 本番（現実脅威 0% 検知）より明確に優秀な候補すら
永久に却下する構造的な壁だったこと。Owner 判断（「両方」）に基づき、(1) **baseline floor の
現実化** と (2) **proposer プロンプト強化** を実装。あわせて ignition で生じた SSOT ドリフトを
同期し main を green に戻した。本タスクで API・live 実行・workflow_dispatch なし。

## Owner 判断（確認済み）
- 発動時：paid 自動拒否（既実装）。失敗の定義：昇格失敗すべて（既実装）。
- 今回：**floor 修正 ＋ proposer 強化の両方**。

## 変更ファイル
- `scripts/evaluate_structured_rules_candidate.py`
  - baseline_mode のとき、**未知ティアのみ** floor を緩和：
    `min_holdout_pass_rate_baseline` / `min_drift_pass_rate_baseline`（genome、既定0.5）を適用。
  - **誤検知安全（counterfactual・max_fp_rate）・regression・latency は baseline でも厳格維持**。
  - 新 genome キーを `_validate_genome_thresholds` の range 検証対象に追加。
  - report に `baseline_mode` / `min_holdout_pass_rate_applied` / `min_drift_pass_rate_applied` を追加（監査可能化）。
- `data/genome.json`：`min_holdout_pass_rate_baseline: 0.5`、`min_drift_pass_rate_baseline: 0.5` を追加。
- `scripts/propose_mutation.py`：`_build_structured_rules_prompt` を強化。
  - カテゴリ拡張（path traversal / SQLi / XSS / command injection に加え SSRF・XXE・SSTI・NoSQL/LDAP）、
    各カテゴリ複数署名、難読化（大文字小文字・URL/二重エンコード・コメント分断）への留意、
    **precision 重視（無害リクエストに過剰マッチしない）**。防御署名のみ・exploit payload 禁止は維持。
- SSOT 同期（ignition runs 反映）：
  - `data/project_state.json`：primary-model success 15→**19**、note に runs #71-74 ＋ breaker trip ＋
    baseline floor 方針を追記。
  - `docs/PROJECT_STATE.md`：count 15→19、runs #71-74 行追加、機械証拠の記述更新。
  - `tests/test_project_state_sync.py`：`_EXPECTED_PRIMARY_MODEL_PAID_CREDIT_SUCCESS_RECORDS` 15→19。
  - `tests/test_circuit_breaker.py`：`test_committed_state_file_is_valid` に変更（稼働中は trip し得るため
    untripped を前提にしない。trip と counter/threshold の整合のみ検証）。
- テスト追加：
  - `tests/test_evaluate_structured_rules_candidate.py`：`TestBaselineGeneralizationFloor`
    （baseline は holdout floor を緩和して昇格／非 baseline は厳格1.0で却下／**baseline でも fp 安全は緩めない**／
    新 genome キーの range 検証）。
  - `tests/test_structured_rules_live.py`：proposer プロンプトが網羅性＋precision＋防御限定を要求することを検証。

## 設計の要点（理念整合）
- holdout/drift は「未知への汎化を**測る指標**」。単発静的ルールに100%を課すと指標が pass/fail の壁になり、
  現行(0%)を上回る前進すら却下されてしまう。baseline は「現実的フロア」に緩和し、まず未知へ前進した
  最初の検出器を稼働させる。
- **monotonic 改善は維持**：generation 2+ は baseline ではないため厳格 floor ＋ active structured score
  超過（parity guard）が必要。世代を追うごとに汎化が上がる ratchet は壊れない。
- **安全は不変**：誤検知（counterfactual・max_fp）・regression（既知攻撃網羅）・latency は緩めない。

## 後検証
- `pytest tests/ -q` → **3073 passed**（baseline floor 4件＋proposer 1件追加。ignition で red 化した
  circuit_breaker / project_state 2件を green 化）。`validate_state.py` → **PASS**。
- 新挙動スモーク：partial-holdout(0.5) 候補が baseline で昇格 / 非 baseline で却下、を CLI で確認。

## Which layer did this task advance?
- [x] Layer 3 — AI Operation Control（自律昇格の判定基準を、理念どおり「未知へ前進し続ける」方向に
  正しく機能させる修正。安全フロアは維持）。
- 補足：これにより次の ignition では「現行を上回る最初の構造化検出器」が昇格し得る。

## 残存・次アクション
- circuit breaker は現在 **trip 中**。本 PR マージ後、Owner が原因解消を確認のうえ
  `python scripts/circuit_breaker.py --reset` → 再 ignition（`structured-gemini-paid-credit` +
  `structured_baseline=true` + `promote_approved=true`）。
- baseline 既定 floor 0.5 は genome で調整可能（Owner 制御）。
